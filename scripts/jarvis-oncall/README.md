# Jarvis On-Call — Discord troubleshooting bot

Paste an error/log from any km-cluster node into Discord; the bot identifies the
node, asks Jarvis's `llm_router` to diagnose it, runs **read-only** diagnostics
over SSH, and — for state-changing fixes — proposes the exact command and waits
for your explicit confirmation before running it.

Runs on **Jarvis** as a systemd service. SSHes to other nodes as the low-priv
`monitor` user (reused from the NetFRAME health daemon); Jarvis is checked
locally.

## Status
- **Phase 1 (done):** node registry, `llm_router` tool-calling passthrough,
  authenticated bot skeleton.
- **Phase 2 (done):** the six read-only tools execute over SSH (`executors.py`)
  in an agentic loop — the model calls tools, the bot runs them as `monitor`,
  feeds results back, and the model analyzes. Progress is posted live (`🔧 …`).
- **Phase 3 (done):** `restart_service` confirm-and-execute. The bot posts the
  exact `sudo systemctl restart <unit>` + target node and **waits for an explicit
  `yes`/`do it`** (60s) before running it via scoped NOPASSWD sudo. Refuses any
  unit outside the node's `restart:` allowlist, and refuses unreachable nodes —
  without ever prompting. Timeout / any non-affirmative reply = cancelled.

## Read-only tools (Phase 2)
`check_service_status`, `tail_logs`, `zpool_status`, `gpu_status`, `disk_usage`,
`vm_status` — each validates the node (reachable? has GPU? has pools?) before
running a fixed absolute-path argv via `ssh.py`. Root-requiring reads (`zpool`,
`qm`, `pct`) use `sudo -n`; install `sudoers.d-jarvis-oncall-readonly.example`
on the remote nodes. Tool output is capped at 1800 chars to fit the local
model's 8192-token context.

## Files
| File | Purpose |
|---|---|
| `bot.py` | discord.py client; author-ID + channel allowlist; router round-trip |
| `router_client.py` | calls `llm_router` `/v1/chat/completions` with tool schemas |
| `tools.py` | whitelisted tool schemas + read-only/mutating classification |
| `registry.py` / `nodes.yaml` | node registry — add a node here, no code change |
| `prompts.py` | system prompt (node roster + per-node quirks) built from the registry |
| `ssh.py` | the only place the bot shells to nodes — argv only, never LLM strings |
| `audit.py` | append-only JSONL audit → `/var/log/jarvis-oncall/audit.jsonl` |
| `jarvis-oncall.service` | systemd unit |

## Security model
- Answers **only** `ALLOWED_USER_ID`; everyone else is ignored and logged.
- Listens in DMs with that user and/or one `CHANNEL_ID`.
- The model can only name a whitelisted tool — never a raw shell string.
- Read-only tools run without confirmation; `restart_service` requires an
  explicit Discord confirmation (Phase 3) and is limited to each node's
  `restart:` allowlist in `nodes.yaml`.
- Secrets live in `/opt/jarvis-oncall/.env` (chmod 600), never in git.

## The llm_router change
`llm_router.py` gained an **additive** `tools`/`tool_choice` passthrough:
requests without `tools` behave exactly as before; requests with `tools` get
native tool-calling (forwarded to Ollama; converted to Anthropic tools for the
Claude path, with returned `tool_use` surfaced as OpenAI `tool_calls`).
**Redeploy the router** after pulling this change:
```bash
ssh jarvis 'systemctl restart llm_router && curl -s localhost:8000/health'
```

## Deploy (on Jarvis)
```bash
sudo mkdir -p /opt/jarvis-oncall && sudo chown root:root /opt/jarvis-oncall
sudo rsync -a ~/Home-Lab/scripts/jarvis-oncall/ /opt/jarvis-oncall/   # (from Ares: rsync to jarvis:)
cd /opt/jarvis-oncall
python3 -m venv venv && venv/bin/pip install -r requirements.txt
sudo install -m600 .env.example /opt/jarvis-oncall/.env   # then edit: token + your user ID
sudo mkdir -p /var/log/jarvis-oncall
sudo install -m644 jarvis-oncall.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now jarvis-oncall
journalctl -u jarvis-oncall -f
```

### `.env` (from Vaultwarden)
Set `DISCORD_TOKEN` (Vaultwarden), `ALLOWED_USER_ID` (your Discord user ID —
Developer Mode → right-click your name → Copy User ID), and optionally
`CHANNEL_ID`. For the most reliable tool-calling set `ROUTER_MODEL=claude-opus-4-8`
(needs the router's `ANTHROPIC_API_KEY`); otherwise it uses the local 72B.

## Sudoers to install (per remote node)
Two generated example files list the **exact** commands the bot runs (Jarvis is
local/root and needs neither):
- `sudoers.d-jarvis-oncall-readonly.example` — root-requiring **reads**
  (`zpool status *`, `qm list`, `pct list`).
- `sudoers.d-jarvis-oncall.example` — the **restart_service** allowlist, one
  command-exact `systemctl restart <unit>` per allowed unit per node.

Install the matching block on each node and `visudo -c` to validate. Editing a
node's `restart:` list in `nodes.yaml` means regenerating/adjusting its sudoers
block to match.
