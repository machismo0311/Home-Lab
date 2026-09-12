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
import json
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
    """A stubbed httpx response.

    IMPORTANT: this models the REAL collaborator contract, not a convenient one. The original
    fixture always returned a dict from .json(), which made it structurally impossible to
    reproduce the 2026-09-12 production failure: Open WebUI sends stream=true, the adapter
    answers text/event-stream, and .json() on `data: {...}` raises. A stub whose .json() cannot
    fail can never catch a .json() defect. So when a raw body is supplied, .json() parses it for
    real and is allowed to raise for real.
    """

    def __init__(self, status, payload=None, raw=None, content_type="application/json"):
        self.status_code = status
        self._payload = payload
        self._raw = raw
        self.headers = {"content-type": content_type}
        self.closed = False

    def json(self):
        if self._raw is not None:
            return json.loads(self._raw)        # raises JSONDecodeError on SSE, as production did
        return self._payload

    async def aiter_raw(self, chunk_size=None):
        body = self._raw if self._raw is not None else json.dumps(self._payload).encode()
        # Chunked deliberately: a single-yield stub would hide a generator that closes its
        # client after the first chunk.
        for i in range(0, len(body), 64):
            _StubClient.client_closed_during_stream |= _StubClient.closed_clients > 0
            yield body[i:i + 64]

    async def aread(self):
        return self._raw if self._raw is not None else json.dumps(self._payload).encode()

    async def aclose(self):
        self.closed = True
        _StubClient.closed_responses += 1


class _Req:
    def __init__(self, method, url, json=None):
        self.method, self.url, self.json = method, url, json


class _StubClient:
    """Records every call the route makes. `health`/`post` are set per-test."""

    calls = []
    health_status = 200
    health_raise = None
    post_status = 200
    post_payload = {"ok": True}
    post_raise = None
    # streaming knobs
    stream_raw = None                 # bytes -> served as the streaming body
    stream_content_type = "text/event-stream"
    stream_status = 200
    # lifecycle instrumentation (section 7: the generator must own client/response lifetime)
    closed_clients = 0
    closed_responses = 0
    client_closed_during_stream = False

    def __init__(self, *a, **kw):
        self.timeout = kw.get("timeout")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def aclose(self):
        _StubClient.closed_clients += 1

    def build_request(self, method, url, **kw):
        return _Req(method, url, json=kw.get("json"))

    async def send(self, request, stream=False, **kw):
        _StubClient.calls.append(("SEND", request.url, request.json, stream))
        if _StubClient.post_raise:
            raise _StubClient.post_raise
        return _Resp(_StubClient.stream_status, raw=_StubClient.stream_raw,
                     content_type=_StubClient.stream_content_type)

    async def get(self, url, **kw):
        _StubClient.calls.append(("GET", url))
        if _StubClient.health_raise:
            raise _StubClient.health_raise
        return _Resp(_StubClient.health_status, {})

    async def post(self, url, **kw):
        _StubClient.calls.append(("POST", url, kw.get("json")))
        if _StubClient.post_raise:
            raise _StubClient.post_raise
        # FAITHFUL COLLABORATOR CONTRACT: the adapter decides its response format from the
        # REQUEST BODY, not from how httpx was invoked. If the caller asked for stream=true it
        # answers text/event-stream even when the router used a buffering .post(). That is
        # precisely the production shape, and it is what makes the pre-fix 503 reproducible:
        # the unfixed branch calls .json() on an SSE body.
        if (kw.get("json") or {}).get("stream"):
            return _Resp(_StubClient.stream_status, raw=_StubClient.stream_raw,
                         content_type=_StubClient.stream_content_type)
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


SSE_BODY = (
    b'data: {"id": "chatcmpl-joi-x", "object": "chat.completion.chunk", "created": 1, '
    b'"model": "netframe-jarvis", "choices": [{"index": 0, "delta": {"role": "assistant"}, '
    b'"finish_reason": null}]}\n\n'
    b'data: {"id": "chatcmpl-joi-x", "object": "chat.completion.chunk", "choices": '
    b'[{"index": 0, "delta": {"content": "pve4 is I/O bound"}, "finish_reason": null}]}\n\n'
    b'data: {"netframe": {"intent": "health.explain", "claims": 29, "engine_ms": 58.5}}\n\n'
    b'data: [DONE]\n\n'
)


def reset(**kw):
    _StubClient.calls = []
    _StubClient.health_status, _StubClient.health_raise = 200, None
    _StubClient.post_status, _StubClient.post_payload, _StubClient.post_raise = 200, {"ok": True}, None
    _StubClient.stream_raw, _StubClient.stream_status = SSE_BODY, 200
    _StubClient.stream_content_type = "text/event-stream"
    _StubClient.closed_clients = _StubClient.closed_responses = 0
    _StubClient.client_closed_during_stream = False
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

# ---- 6. STREAMING (the 2026-09-12 live Open WebUI failure) --------------------------------
# Open WebUI sends stream=true. The adapter honours it and answers text/event-stream. The
# original branch called _r.json() on that body unconditionally, the first byte is 'd' from
# "data: {", and the resulting JSONDecodeError surfaced to the operator as
# "503 evidence path unavailable: Expecting value: line 1 column 1 (char 0)".
OWUI = lambda **kw: dict({"model": "netframe-jarvis", "stream": True,
                          "messages": [{"role": "user", "content": "Why is pve4 unhealthy?"}]}, **kw)

# T1 - STREAMING SUCCESS
reset()
r = client.post("/v1/chat/completions", json=OWUI())
chk("T1 stream: router returns 200, not 503", r.status_code == 200)
chk("T1 stream: Content-Type is text/event-stream",
    r.headers.get("content-type", "").startswith("text/event-stream"))
chk("T1 stream: SSE bytes forwarded verbatim, not JSON-decoded", r.content == SSE_BODY)
chk("T1 stream: terminator preserved", r.content.rstrip().endswith(b"data: [DONE]"))
chk("T1 stream: grounded payload survives the proxy", b"health.explain" in r.content)
chk("T1 stream: Ollama NOT called", "ollama" not in backends)
chk("T1 stream: Claude NOT called", "claude" not in backends)
chk("T1 stream: adapter reached via streaming send(), not buffering post()",
    any(c[0] == "SEND" and c[3] is True for c in _StubClient.calls))
chk("T1 stream: stream flag forwarded to the adapter unchanged",
    any(c[0] == "SEND" and (c[2] or {}).get("stream") is True for c in _StubClient.calls))

# T1b - CLIENT LIFETIME (section 7). The generator must own the client; a naive
# `async with httpx.AsyncClient()` closes it before the body is drained.
chk("T1b lifetime: client was NOT closed while chunks were still being yielded",
    _StubClient.client_closed_during_stream is False)
chk("T1b lifetime: response closed exactly once after the stream ended",
    _StubClient.closed_responses == 1)
chk("T1b lifetime: client closed exactly once after the stream ended",
    _StubClient.closed_clients == 1)

# T2 - NON-STREAMING REGRESSION
reset()
r = client.post("/v1/chat/completions",
                json={"model": "netframe-jarvis", "stream": False,
                      "messages": [{"role": "user", "content": "hi"}]})
chk("T2 stream=false: still the plain JSON path", r.status_code == 200
    and r.headers.get("content-type", "").startswith("application/json"))
chk("T2 stream=false: uses buffering post(), not send()",
    any(c[0] == "POST" for c in _StubClient.calls) and not any(c[0] == "SEND" for c in _StubClient.calls))
chk("T2 stream=false: no generic backend", backends == [])

# T3 - ADAPTER ERROR BEFORE THE RESPONSE IS COMMITTED
reset(stream_status=500)
r = client.post("/v1/chat/completions", json=OWUI())
chk("T3 stream: adapter non-2xx before commit -> fail closed, not a 200 stream",
    r.status_code != 200)
chk("T3 stream: no generic fallback on adapter error", backends == [])
chk("T3 stream: client and response both released on the error path",
    _StubClient.closed_clients == 1 and _StubClient.closed_responses == 1)

reset(post_raise=ConnectionError("adapter down"))
r = client.post("/v1/chat/completions", json=OWUI())
chk("T3b stream: adapter unreachable -> 503", r.status_code == 503)
chk("T3b stream: unreachable adapter reaches no generic backend", backends == [])

# T4 - FALLBACK GUARD UNDER STREAMING
reset()
r = client.post("/v1/chat/completions", json=OWUI(escalate=True))
chk("T4 stream: escalate:true cannot divert the streaming evidence route to Claude",
    r.status_code == 200 and backends == [])

reset(post_raise=TimeoutError("timed out"))
r = client.post("/v1/chat/completions", json=OWUI())
chk("T4b stream: timeout -> error, never a generic completion",
    r.status_code == 503 and backends == [])

# T5 - CONTENT-TYPE GUARD: the adapter must not be trusted to be JSON just because we asked
# for a stream. Whatever it sends is proxied as-is; it is never silently re-parsed.
reset(stream_content_type="application/json", stream_raw=b'{"ok": true}')
r = client.post("/v1/chat/completions", json=OWUI())
chk("T5 stream: adapter's own Content-Type is preserved, not overridden",
    r.headers.get("content-type", "").startswith("application/json"))
chk("T5 stream: body still forwarded byte-for-byte", r.content == b'{"ok": true}')
chk("T5 stream: no generic backend regardless of content type", backends == [])

reset(stream_content_type="text/plain", stream_raw=b"not json at all")
r = client.post("/v1/chat/completions", json=OWUI())
chk("T5b stream: a non-JSON, non-SSE body does NOT raise a decode error",
    r.status_code == 200 and r.content == b"not json at all")
chk("T5b stream: and still reaches no generic backend", backends == [])

print("----")
print("JOI ROUTING: " + ("FAIL " + str(fails) if fails else "PASS"))
sys.exit(1 if fails else 0)
