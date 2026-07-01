#!/usr/bin/env python3
"""
llm_router.py — NetFRAME hybrid inference router (Jarvis)

OpenAI-compatible /v1/chat/completions endpoint that routes requests to
local Ollama (Qwen2.5 72B, 2x RTX 6000) by default, and escalates to the
Claude API when local model confidence is low.

Status: inactive until Jarvis's 2x RTX 6000 are installed. Safe to deploy
now — it will simply route everything to Claude until OLLAMA_URL responds.
"""

import math
import os
import time
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# --- Configuration -----------------------------------------------------
# All values overridable via environment so this runs the same in dev,
# systemd, or a container without editing code.
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:72b")
CLAUDE_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")
CLAUDE_URL = "https://api.anthropic.com/v1/messages"

# Confidence threshold below which we escalate to Claude instead of
# trusting the local model's answer. Tune this after collecting real
# logprob distributions from Ollama in production.
CONFIDENCE_THRESHOLD = float(os.environ.get("CONFIDENCE_THRESHOLD", "0.55"))

app = FastAPI(title="NetFRAME LLM Router")

# Running counters for the /stats endpoint. In-memory only — resets on
# restart. Good enough for a homelab dashboard; swap for Prometheus
# counters later if you want history across restarts.
stats = {
    "requests_total": 0,
    "routed_local": 0,
    "routed_claude": 0,
    "errors": 0,
}


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: Optional[str] = None
    messages: list[ChatMessage]
    max_tokens: int = 1024
    temperature: float = 0.7


def _confidence_from_logprobs(logprobs: list[float]) -> float:
    """
    Convert a list of token logprobs from Ollama into a single 0-1
    confidence score. We take the mean per-token probability rather than
    the raw logprob sum, so response length doesn't bias the score.
    """
    if not logprobs:
        return 0.0
    probs = [math.exp(lp) for lp in logprobs]
    return sum(probs) / len(probs)


async def _call_ollama(req: ChatRequest) -> tuple[str, float]:
    """Query local Ollama and return (response_text, confidence)."""
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [m.model_dump() for m in req.messages],
        "options": {"temperature": req.temperature},
        "stream": False,
        # logprobs isn't in every Ollama build's public API; if this
        # field is unsupported it's silently ignored by the server.
        "logprobs": True,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
        resp.raise_for_status()
        data = resp.json()

    text = data.get("message", {}).get("content", "")
    logprobs = data.get("logprobs", [])
    confidence = _confidence_from_logprobs(logprobs) if logprobs else 1.0
    return text, confidence


async def _call_claude(req: ChatRequest) -> str:
    """Escalate to the Claude API. Used both as fallback and when Ollama
    is unreachable (e.g. GPUs not installed yet)."""
    if not CLAUDE_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="ANTHROPIC_API_KEY not set — cannot escalate to Claude",
        )

    headers = {
        "x-api-key": CLAUDE_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": req.max_tokens,
        "messages": [m.model_dump() for m in req.messages],
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(CLAUDE_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    return "".join(
        block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
    )


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest):
    """
    OpenAI-compatible endpoint. Tries Ollama first; falls back to Claude
    if Ollama is unreachable OR its confidence is below threshold.
    """
    stats["requests_total"] += 1
    started = time.time()

    source = "claude"
    text = ""

    try:
        text, confidence = await _call_ollama(req)
        if confidence >= CONFIDENCE_THRESHOLD:
            source = "ollama"
        else:
            # Low confidence local answer — don't return it, escalate instead.
            text = await _call_claude(req)
    except (httpx.ConnectError, httpx.TimeoutException):
        # Ollama not up yet (e.g. GPUs not installed) — this is the
        # expected path until the 2x RTX 6000 are seated in Jarvis.
        text = await _call_claude(req)
    except Exception:
        stats["errors"] += 1
        raise

    stats["routed_local" if source == "ollama" else "routed_claude"] += 1

    return {
        "id": f"chatcmpl-{int(started * 1000)}",
        "object": "chat.completion",
        "created": int(started),
        "model": OLLAMA_MODEL if source == "ollama" else CLAUDE_MODEL,
        "netframe_routed_to": source,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
    }


@app.get("/health")
async def health():
    """Liveness/readiness probe. Reports whether Ollama is reachable so
    Homepage/Uptime Kuma can show router state, not just process state."""
    ollama_up = False
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            ollama_up = resp.status_code == 200
    except Exception:
        ollama_up = False

    return {
        "status": "ok",
        "ollama_reachable": ollama_up,
        "claude_configured": bool(CLAUDE_API_KEY),
    }


@app.get("/stats")
async def get_stats():
    """Routing counters since last restart — surface on the dashboard."""
    return stats


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8090)
