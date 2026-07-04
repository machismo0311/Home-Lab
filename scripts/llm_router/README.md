# llm_router — OpenAI-compatible hybrid router (Jarvis)

FastAPI service that presents an **OpenAI-compatible** `/v1/chat/completions` API and routes between:

- **Local (default):** Ollama serving **Qwen2.5 72B** on Jarvis's 2× RTX 6000 (tensor-split).
- **Claude escalation/fallback:** the Anthropic API via the official SDK (`claude-opus-4-8`, adaptive thinking).

## Routing
- Default → local Ollama (`qwen2.5:72b`).
- → **Claude** when: the request body has `"escalate": true`, the requested `model` starts with `claude`, **or** the local Ollama call fails (auto-fallback).
- Claude is enabled only when `ANTHROPIC_API_KEY` is set; otherwise Claude requests return `503` and the router serves local-only.

> The original spec called for logprob-confidence routing, but Ollama does not expose per-token logprobs — escalation is by explicit flag / model / failure instead. Streaming (`"stream": true`) is not yet implemented; requests are served non-streamed.

## Deploy (as installed on Jarvis 2026-07-04)
- Code: `/opt/llm_router/llm_router.py` (venv at `/opt/llm_router/venv`).
- Env: `/etc/llm_router.env` (chmod 600) — see `llm_router.env.example`.
- Service: `/etc/systemd/system/llm_router.service` (`systemctl enable --now llm_router`).
- Listens on `0.0.0.0:8000` (Jarvis `192.168.10.31:8000` / `192.168.30.31:8000`).

```bash
python3 -m venv /opt/llm_router/venv          # needs python3-venv (apt)
/opt/llm_router/venv/bin/pip install -r requirements.txt
install -m600 llm_router.env.example /etc/llm_router.env   # then edit
install -m644 llm_router.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now llm_router
```

## Enabling Claude fallback
Add `ANTHROPIC_API_KEY=sk-ant-...` to `/etc/llm_router.env`, then `systemctl restart llm_router`.
`/health` will then report `"claude_enabled": true`.

## Endpoints / smoke test
```bash
curl -s localhost:8000/health              # {status, ollama, claude_enabled, ...}
curl -s localhost:8000/v1/models
curl -s localhost:8000/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"local","messages":[{"role":"user","content":"hello"}],"max_tokens":32}'
# force Claude (needs key):
#   -d '{"escalate":true, ...}'   or   -d '{"model":"claude-opus-4-8", ...}'
```
First local request cold-loads the 72B (~47 GB → both GPUs, ~40 s); subsequent requests are fast while resident.
