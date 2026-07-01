# llm_router.py

FastAPI, OpenAI-compatible hybrid inference router for Jarvis. Routes chat
completions to local Ollama by default, escalating to the Claude API when
local confidence is low or Ollama is unreachable.

**Status:** code complete, **inactive in production** — Jarvis's 2x RTX 6000
aren't seated yet. Safe to deploy today: with no GPUs, every request just
falls through to Claude until Ollama comes up.

## Why hybrid instead of local-only or cloud-only

- **Local-only** would mean every low-confidence answer from a 72B model
  goes out as-is, with no way to catch it.
- **Cloud-only** defeats the point of having 2x RTX 6000 sitting idle in
  the rack.
- **Hybrid** uses local inference for the common case (free, private, fast)
  and reserves the Claude API call for the cases where the local model is
  genuinely unsure — measured via mean token-probability from Ollama's
  logprobs, not just a static ruleset.

## Deploy

```bash
mkdir -p /opt/llm-router && cd /opt/llm-router
git clone https://github.com/machismo0311/Home-Lab.git /tmp/hl
cp /tmp/hl/llm-router/{llm_router.py,requirements.txt} .

python3 -m venv venv
./venv/bin/pip install -r requirements.txt

cat > .env <<'EOF'
OLLAMA_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:72b
ANTHROPIC_API_KEY=          # pull from Vaultwarden, never commit this
CLAUDE_MODEL=claude-sonnet-4-6
CONFIDENCE_THRESHOLD=0.55
EOF
chmod 600 .env

sudo useradd -r -s /usr/sbin/nologin llmrouter
sudo chown -R llmrouter:llmrouter /opt/llm-router

sudo cp llm-router.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now llm-router
```

> **What this does:** creates a dedicated `llmrouter` service account rather
> than running as root, isolates the API key in a `.env` file with `600`
> permissions instead of hardcoding it, and runs the process under systemd
> so it survives reboots and restarts automatically on crash — same pattern
> used for every other persistent service in this repo.

## Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /v1/chat/completions` | OpenAI-compatible chat completion, hybrid-routed |
| `GET /health` | Liveness probe; reports whether Ollama is actually reachable |
| `GET /stats` | Routing counters (local vs. Claude, error count) since last restart |

## Tuning

`CONFIDENCE_THRESHOLD` (default `0.55`) is a starting guess, not a measured
value. Once Ollama is live on the RTX 6000s, log real confidence scores for
a week of traffic and pick a threshold from the actual distribution rather
than trusting this default.
