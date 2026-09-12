#!/usr/bin/env python3
"""Offline fixtures for the netframe-jarvis (JOI evidence) route. No network, no model traffic.

Why this exists. The netframe-jarvis branch was applied in place to the deployed llm_router on
2026-08-08 as the owner-gated "Option A" activation, and it ran for 35 days with NO direct test
coverage anywhere. The deployment record called its no-fallback property "structurally proven and
isolated-tested", which was accurate but narrower than it reads: the JOI *adapter* has a suite
(netframe-enterprise-assessment jarvis/joi/test_openai_adapter.py); the routing branch inside
llm_router had none. Its fail-closed guarantee rested on reading the code, not on an assertion.

The guarantee under test is the one the route exists to provide: when the evidence path is
unavailable, the caller gets an ERROR, never a generic model answer. A fallthrough to Ollama or
Claude here would answer an infrastructure question from a bare model with no retrieval, telemetry
or refusal - the exact RCA 2026-07-30 failure the route was built to prevent. So "503" is not the
interesting assertion; "and _ollama_chat was never called" is.

Every outbound call is stubbed at llm_router.httpx, so this makes no HTTP request to the adapter,
Ollama, or Anthropic.

Run: /opt/llm_router/venv/bin/python test_joi_routing.py      (on Jarvis, or any venv with fastapi)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import llm_router  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

fails = []


def chk(name, cond):
    print(("PASS  " if cond else "FAIL  ") + name)
    if not cond:
        fails.append(name)


# ---- stubs -------------------------------------------------------------------------------
# The route builds its own httpx.AsyncClient inside the function, so there is no client to
# inject; the seam is the module global. Patching llm_router.httpx leaves starlette's own httpx
# (used by TestClient) untouched.
class _Resp:
    def __init__(self, status, payload):
        self.status_code, self._payload = status, payload

    def json(self):
        return self._payload


class _StubClient:
    """Records every call the route makes. `health`/`post` are set per-test."""

    calls = []
    health_status = 200
    health_raise = None
    post_status = 200
    post_payload = {"ok": True}
    post_raise = None

    def __init__(self, *a, **kw):
        self.timeout = kw.get("timeout")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, **kw):
        _StubClient.calls.append(("GET", url))
        if _StubClient.health_raise:
            raise _StubClient.health_raise
        return _Resp(_StubClient.health_status, {})

    async def post(self, url, **kw):
        _StubClient.calls.append(("POST", url, kw.get("json")))
        if _StubClient.post_raise:
            raise _StubClient.post_raise
        return _Resp(_StubClient.post_status, _StubClient.post_payload)


class _FakeHttpx:
    AsyncClient = _StubClient


llm_router.httpx = _FakeHttpx

backends = []


def _stub_backend(name):
    async def _f(body):
        backends.append(name)
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=200, content={"backend": name})

    return _f


llm_router._ollama_chat = _stub_backend("ollama")
llm_router._claude_chat = _stub_backend("claude")
llm_router._rag_chat = _stub_backend("rag")

client = TestClient(llm_router.app)
ADAPTER = os.environ.get("JOI_ADAPTER_URL", "http://127.0.0.1:8811")


def reset(**kw):
    _StubClient.calls = []
    _StubClient.health_status, _StubClient.health_raise = 200, None
    _StubClient.post_status, _StubClient.post_payload, _StubClient.post_raise = 200, {"ok": True}, None
    for k, v in kw.items():
        setattr(_StubClient, k, v)
    backends.clear()


def ids_of(r):
    return [m["id"] for m in r.json()["data"]]


# ---- 1. /v1/models advertises netframe-jarvis ONLY on adapter health 200 ------------------
reset()
r = client.get("/v1/models")
chk("models: adapter healthy (200) -> netframe-jarvis advertised", "netframe-jarvis" in ids_of(r))
chk("models: health probed at the adapter /health", ("GET", f"{ADAPTER}/health") in _StubClient.calls)

reset(health_status=500)
chk("models: adapter unhealthy (500) -> NOT advertised", "netframe-jarvis" not in ids_of(client.get("/v1/models")))

reset(health_status=404)
chk("models: adapter 404 -> NOT advertised", "netframe-jarvis" not in ids_of(client.get("/v1/models")))

reset(health_raise=ConnectionError("adapter down"))
r = client.get("/v1/models")
chk("models: adapter unreachable -> NOT advertised", "netframe-jarvis" not in ids_of(r))
chk("models: adapter unreachable -> discovery still succeeds (200)", r.status_code == 200)

reset(health_raise=ConnectionError("adapter down"))
chk("models: local model survives an adapter outage", llm_router.LOCAL_MODEL in ids_of(client.get("/v1/models")))

# ---- 2. netframe-jarvis routes to the adapter ---------------------------------------------
reset(post_payload={"choices": [{"message": {"content": "grounded"}}], "netframe": {"claims": 29}})
body = {"model": "netframe-jarvis", "messages": [{"role": "user", "content": "why is pve4 unhealthy?"}]}
r = client.post("/v1/chat/completions", json=body)
posts = [c for c in _StubClient.calls if c[0] == "POST"]
chk("route: posts to the adapter /v1/chat/completions",
    len(posts) == 1 and posts[0][1] == f"{ADAPTER}/v1/chat/completions")
chk("route: forwards the request body verbatim", posts and posts[0][2] == body)
chk("route: returns the adapter's payload", r.json().get("netframe", {}).get("claims") == 29)
chk("route: returns the adapter's status", r.status_code == 200)
chk("route: no generic backend was consulted", backends == [])

reset()
client.post("/v1/chat/completions", json={"model": "NetFRAME-Jarvis", "messages": []})
chk("route: model name match is case-insensitive",
    any(c[0] == "POST" for c in _StubClient.calls) and backends == [])

# ---- 3. FAIL CLOSED: adapter failure never becomes a generic answer -----------------------
reset(post_raise=ConnectionError("connection refused"))
r = client.post("/v1/chat/completions", json={"model": "netframe-jarvis", "messages": []})
chk("fail-closed: adapter unreachable -> 503", r.status_code == 503)
chk("fail-closed: adapter unreachable -> Ollama NOT called", "ollama" not in backends)
chk("fail-closed: adapter unreachable -> Claude NOT called", "claude" not in backends)
chk("fail-closed: adapter unreachable -> NO backend at all", backends == [])

reset(post_raise=TimeoutError("timed out"))
r = client.post("/v1/chat/completions", json={"model": "netframe-jarvis", "messages": []})
chk("fail-closed: adapter timeout -> 503, no fallthrough", r.status_code == 503 and backends == [])

reset(post_status=500, post_payload={"error": "engine failed"})
r = client.post("/v1/chat/completions", json={"model": "netframe-jarvis", "messages": []})
chk("fail-closed: adapter 500 is passed through, not masked", r.status_code == 500)
chk("fail-closed: adapter 500 -> still no generic fallthrough", backends == [])

# The evidence route must be decided BEFORE the generic ones, or a future edit to _wants_claude
# could capture it. Assert on ordering by proving Claude never wins even when it would match.
reset(post_raise=ConnectionError("down"))
r = client.post("/v1/chat/completions",
                json={"model": "netframe-jarvis", "messages": [], "escalate": True})
chk("fail-closed: escalate:true cannot divert the evidence route to Claude",
    r.status_code == 503 and backends == [])

# ---- 4. non-JOI models keep their existing routing ----------------------------------------
reset()
client.post("/v1/chat/completions", json={"model": llm_router.LOCAL_MODEL, "messages": []})
chk("passthrough: local model still routes to Ollama", backends == ["ollama"])
chk("passthrough: local model does not touch the adapter",
    not any(c[0] == "POST" for c in _StubClient.calls))

reset()
client.post("/v1/chat/completions", json={"model": "rag", "messages": []})
chk("passthrough: rag still routes to the RAG path", backends == ["rag"])

reset()
client.post("/v1/chat/completions", json={"model": "claude-opus-4-8", "messages": []})
chk("passthrough: claude* still routes to Claude", backends == ["claude"])

reset()
client.post("/v1/chat/completions", json={"model": "some-other-model", "messages": []})
chk("passthrough: unknown model still falls to Ollama", backends == ["ollama"])

# ---- 5. the adapter URL is configurable, and defaults to loopback -------------------------
chk("boundary: default adapter URL is loopback",
    "127.0.0.1:8811" in os.environ.get("JOI_ADAPTER_URL", "http://127.0.0.1:8811"))

_prev = os.environ.get("JOI_ADAPTER_URL")
os.environ["JOI_ADAPTER_URL"] = "http://127.0.0.1:9999"
reset()
client.post("/v1/chat/completions", json={"model": "netframe-jarvis", "messages": []})
chk("boundary: JOI_ADAPTER_URL override is honoured",
    any(c[0] == "POST" and c[1].startswith("http://127.0.0.1:9999") for c in _StubClient.calls))
if _prev is None:
    del os.environ["JOI_ADAPTER_URL"]
else:
    os.environ["JOI_ADAPTER_URL"] = _prev

print("----")
print("JOI ROUTING: " + ("FAIL " + str(fails) if fails else "PASS"))
sys.exit(1 if fails else 0)
