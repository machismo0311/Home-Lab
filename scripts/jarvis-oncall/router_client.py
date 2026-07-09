"""Client for Jarvis's llm_router (OpenAI-compatible /v1/chat/completions).

Sends the conversation plus the whitelisted tool schemas and returns the
assistant text and any tool_calls the model requested. Relies on the additive
tools/tool_choice passthrough added to llm_router.py.
"""
import os

import httpx

ROUTER_URL = os.environ.get("ROUTER_URL", "http://127.0.0.1:8000") + "/v1/chat/completions"
# Default to the local 72B; set ROUTER_MODEL=claude-opus-4-8 (needs the router's
# ANTHROPIC_API_KEY) for the most reliable tool-calling.
ROUTER_MODEL = os.environ.get("ROUTER_MODEL", "qwen2.5:72b")
ROUTER_MAX_TOKENS = int(os.environ.get("ROUTER_MAX_TOKENS", "1500"))
ROUTER_TIMEOUT = int(os.environ.get("ROUTER_TIMEOUT", "600"))


async def complete(messages: list[dict], tools: list[dict] | None = None) -> dict:
    """Return the assistant message dict: {content, tool_calls?}."""
    body = {
        "model": ROUTER_MODEL,
        "messages": messages,
        "max_tokens": ROUTER_MAX_TOKENS,
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = "auto"
    async with httpx.AsyncClient(timeout=ROUTER_TIMEOUT) as c:
        r = await c.post(ROUTER_URL, json=body)
        r.raise_for_status()
        data = r.json()
    return data["choices"][0]["message"]
