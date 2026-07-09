#!/usr/bin/env python3
"""llm_router — OpenAI-compatible hybrid router for Jarvis.

Routes:
  model="rag"        → RAG over the Home-Lab vault (retrieve → ground local model)
  model="claude*" /
    "escalate":true  → Claude API (Anthropic), if ANTHROPIC_API_KEY is set
  anything else      → local Ollama (Qwen2.5 72B); auto-falls back to Claude on failure

Escalation is by flag/model/failure (Ollama exposes no logprobs, so no confidence
routing). Streaming (`"stream": true`) is not implemented — requests are served
non-streamed.
"""
import os
import json
import time
import uuid
import logging

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("llm_router")

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
LOCAL_MODEL = os.environ.get("LOCAL_MODEL", "qwen2.5:72b")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-4-8")
HOST = os.environ.get("LLM_ROUTER_HOST", "0.0.0.0")
PORT = int(os.environ.get("LLM_ROUTER_PORT", "8000"))
MAX_TOKENS_DEFAULT = int(os.environ.get("LLM_ROUTER_MAX_TOKENS", "16000"))
# Cap the local context so the 72B's KV cache fits in 48GB VRAM (else it spills to CPU).
OLLAMA_NUM_CTX = int(os.environ.get("OLLAMA_NUM_CTX", "8192"))

# --- Claude fallback (optional) ---
CLAUDE_ENABLED = bool(os.environ.get("ANTHROPIC_API_KEY"))
_aclient = None
if CLAUDE_ENABLED:
    try:
        from anthropic import AsyncAnthropic

        _aclient = AsyncAnthropic()
    except Exception as e:
        log.warning("Anthropic SDK unavailable (%s); Claude fallback disabled", e)
        CLAUDE_ENABLED = False

# --- RAG index (optional; built by rag_ingest.py) ---
RAG_DIR = os.environ.get("RAG_DIR", "/opt/llm_router")
RAG_EMBED_MODEL = os.environ.get("RAG_EMBED_MODEL", "nomic-embed-text")
RAG_TOPK = int(os.environ.get("RAG_TOPK", "5"))
RAG_ENABLED = False
_rag_emb = None
_rag_docs = None
try:
    import numpy as np

    _rag_emb = np.load(os.path.join(RAG_DIR, "rag_embeddings.npy"))
    with open(os.path.join(RAG_DIR, "rag_index.json"), encoding="utf-8") as fh:
        _rag_docs = json.load(fh)
    RAG_ENABLED = _rag_emb.shape[0] == len(_rag_docs) > 0
    log.info("RAG index loaded: %d chunks", len(_rag_docs))
except Exception as e:
    log.info("RAG disabled (%s)", e)

app = FastAPI(title="llm_router", version="1.1")


def _wants_claude(model: str, body: dict) -> bool:
    if body.get("escalate") is True:
        return True
    return isinstance(model, str) and model.lower().startswith("claude")


def _text_of(content) -> str:
    if isinstance(content, list):
        return "".join(p.get("text", "") for p in content if isinstance(p, dict))
    return content or ""


def _messages_to_anthropic(messages: list[dict]) -> tuple[str, list[dict]]:
    """Split system out and convert an OpenAI-style message list (including
    assistant tool_calls and role='tool' results) to Anthropic message blocks."""
    system_parts, conv = [], []
    for m in messages:
        role = m.get("role")
        content = _text_of(m.get("content", ""))
        if role == "system":
            system_parts.append(content)
        elif role == "tool":
            conv.append({"role": "user", "content": [{
                "type": "tool_result",
                "tool_use_id": m.get("tool_call_id", ""),
                "content": content,
            }]})
        elif role == "assistant" and m.get("tool_calls"):
            blocks = [{"type": "text", "text": content}] if content else []
            for tc in m["tool_calls"]:
                fn = tc.get("function", {})
                raw = fn.get("arguments", "{}")
                try:
                    args = json.loads(raw) if isinstance(raw, str) else raw
                except Exception:
                    args = {}
                blocks.append({"type": "tool_use", "id": tc.get("id", ""),
                               "name": fn.get("name", ""), "input": args})
            conv.append({"role": "assistant", "content": blocks})
        elif role in ("user", "assistant"):
            conv.append({"role": role, "content": content})
    return "\n\n".join(system_parts), conv


def _oa_tools_to_anthropic(tools: list[dict]) -> list[dict]:
    out = []
    for t in tools or []:
        fn = t.get("function", t) if isinstance(t, dict) else {}
        out.append({
            "name": fn.get("name"),
            "description": fn.get("description", ""),
            "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
        })
    return out


def _oa_tool_choice_to_anthropic(tc):
    if tc in (None, "auto"):
        return {"type": "auto"}
    if tc == "required":
        return {"type": "any"}
    if tc == "none":
        return None
    if isinstance(tc, dict) and tc.get("type") == "function":
        return {"type": "tool", "name": tc["function"]["name"]}
    return {"type": "auto"}


def _ollama_tool_calls(raw) -> list[dict] | None:
    """Normalize Ollama /api/chat tool_calls to OpenAI shape (args as a string)."""
    if not raw:
        return None
    out = []
    for i, tc in enumerate(raw):
        fn = tc.get("function", {}) if isinstance(tc, dict) else {}
        args = fn.get("arguments", {})
        if not isinstance(args, str):
            args = json.dumps(args)
        out.append({
            "id": tc.get("id") or f"call_{i}_{uuid.uuid4().hex[:8]}",
            "type": "function",
            "function": {"name": fn.get("name", ""), "arguments": args},
        })
    return out


def _last_user(messages: list[dict]) -> str:
    for m in reversed(messages):
        if m.get("role") == "user":
            c = m.get("content", "")
            if isinstance(c, list):
                c = "".join(p.get("text", "") for p in c if isinstance(p, dict))
            return c
    return ""


async def _ollama_chat(body: dict) -> JSONResponse:
    """Local generation via Ollama's native /api/chat with a bounded context
    (keeps the 72B fully on GPU), reshaped to an OpenAI chat.completion."""
    msgs = []
    for m in body.get("messages", []):
        role = m.get("role")
        if role not in ("system", "user", "assistant", "tool"):
            continue
        msg = {"role": role, "content": _text_of(m.get("content", ""))}
        # Preserve the tool-calling round-trip (Ollama /api/chat understands these).
        if role == "assistant" and m.get("tool_calls"):
            msg["tool_calls"] = m["tool_calls"]
        if role == "tool" and m.get("name"):
            msg["tool_name"] = m["name"]
        msgs.append(msg)
    num_predict = int(body.get("max_tokens") or 1024)
    payload = {
        "model": LOCAL_MODEL, "messages": msgs, "stream": False,
        "options": {"num_ctx": OLLAMA_NUM_CTX, "num_predict": num_predict},
    }
    if body.get("tools"):
        payload["tools"] = body["tools"]
    async with httpx.AsyncClient(timeout=600) as c:
        r = await c.post(f"{OLLAMA_URL}/api/chat", json=payload)
        r.raise_for_status()
        d = r.json()
    pin, pout = d.get("prompt_eval_count", 0), d.get("eval_count", 0)
    out_msg = d.get("message", {}) or {}
    message = {"role": "assistant", "content": out_msg.get("content", "")}
    tool_calls = _ollama_tool_calls(out_msg.get("tool_calls"))
    finish = "stop"
    if tool_calls:
        message["tool_calls"] = tool_calls
        finish = "tool_calls"
    return JSONResponse({
        "id": "chatcmpl-" + uuid.uuid4().hex,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": LOCAL_MODEL,
        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
        "usage": {"prompt_tokens": pin, "completion_tokens": pout, "total_tokens": pin + pout},
    })


async def _embed(text: str) -> list[float]:
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(f"{OLLAMA_URL}/api/embeddings",
                         json={"model": RAG_EMBED_MODEL, "prompt": "search_query: " + text})
        r.raise_for_status()
        return r.json()["embedding"]


async def _rag_chat(body: dict) -> JSONResponse:
    if not RAG_ENABLED:
        raise HTTPException(503, "RAG index not built (run rag_ingest.py)")
    query = _last_user(body.get("messages", []))
    q = np.asarray(await _embed(query), dtype=np.float32)
    q /= (np.linalg.norm(q) + 1e-9)
    sims = _rag_emb @ q
    idx = np.argsort(-sims)[:RAG_TOPK]
    context = "\n\n".join(f"[{_rag_docs[i]['source']}]\n{_rag_docs[i]['text']}" for i in idx)
    sys_prompt = (
        "You are the NetFRAME homelab assistant. Answer the question using ONLY the "
        "context below, drawn from the homelab documentation. Cite the [source] file(s) "
        "you used. If the answer is not in the context, say you don't know.\n\n"
        "CONTEXT:\n" + context
    )
    conv = [m for m in body.get("messages", []) if m.get("role") != "system"]
    new_body = dict(body)
    new_body.pop("escalate", None)
    new_body["messages"] = [{"role": "system", "content": sys_prompt}] + conv
    return await _ollama_chat(new_body)


async def _claude_chat(body: dict) -> JSONResponse:
    if not CLAUDE_ENABLED:
        raise HTTPException(503, "Claude fallback not configured (ANTHROPIC_API_KEY unset)")
    system, conv = _messages_to_anthropic(body.get("messages", []))
    max_tokens = int(body.get("max_tokens") or MAX_TOKENS_DEFAULT)
    kwargs = dict(model=CLAUDE_MODEL, max_tokens=max_tokens, messages=conv)
    if system:
        kwargs["system"] = system
    if body.get("tools"):
        # Forced tool use is incompatible with extended thinking, and tool loops
        # must preserve thinking blocks — so we run tools without thinking.
        kwargs["tools"] = _oa_tools_to_anthropic(body["tools"])
        choice = _oa_tool_choice_to_anthropic(body.get("tool_choice"))
        if choice:
            kwargs["tool_choice"] = choice
    else:
        kwargs["thinking"] = {"type": "adaptive"}
    resp = await _aclient.messages.create(**kwargs)

    text_parts, tool_calls = [], []
    if resp.stop_reason == "refusal":
        text_parts.append("[Claude declined to respond to this request.]")
    else:
        for b in resp.content:
            if b.type == "text":
                text_parts.append(b.text)
            elif b.type == "tool_use":
                tool_calls.append({"id": b.id, "type": "function",
                                   "function": {"name": b.name, "arguments": json.dumps(b.input)}})
    message = {"role": "assistant", "content": "".join(text_parts)}
    finish = "stop"
    if tool_calls:
        message["tool_calls"] = tool_calls
        finish = "tool_calls"
    return JSONResponse({
        "id": "chatcmpl-" + uuid.uuid4().hex,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": CLAUDE_MODEL,
        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
        "usage": {"prompt_tokens": resp.usage.input_tokens,
                  "completion_tokens": resp.usage.output_tokens,
                  "total_tokens": resp.usage.input_tokens + resp.usage.output_tokens},
    })


@app.get("/health")
async def health():
    ollama_ok = False
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            ollama_ok = (await c.get(f"{OLLAMA_URL}/api/tags")).status_code == 200
    except Exception:
        pass
    return {
        "status": "ok",
        "ollama": ollama_ok,
        "local_model": LOCAL_MODEL,
        "claude_enabled": CLAUDE_ENABLED,
        "claude_model": CLAUDE_MODEL if CLAUDE_ENABLED else None,
        "rag_enabled": RAG_ENABLED,
        "rag_chunks": len(_rag_docs) if RAG_ENABLED else 0,
    }


@app.get("/v1/models")
async def models():
    data = [{"id": LOCAL_MODEL, "object": "model", "owned_by": "ollama"}]
    if RAG_ENABLED:
        data.append({"id": "rag", "object": "model", "owned_by": "llm_router"})
    if CLAUDE_ENABLED:
        data.append({"id": CLAUDE_MODEL, "object": "model", "owned_by": "anthropic"})
    return {"object": "list", "data": data}


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    model = body.get("model", LOCAL_MODEL)
    if isinstance(model, str) and model.lower() == "rag":
        return await _rag_chat(body)
    if _wants_claude(model, body):
        return await _claude_chat(body)
    try:
        return await _ollama_chat(body)
    except Exception as e:
        log.warning("Ollama failed (%s); escalating to Claude", e)
        if CLAUDE_ENABLED:
            return await _claude_chat(body)
        raise HTTPException(502, f"Ollama error and no Claude fallback: {e}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=HOST, port=PORT)
