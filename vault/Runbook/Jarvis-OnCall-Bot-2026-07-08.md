# Jarvis On-Call Discord Bot — Runbook

**Node:** Jarvis (Dell PowerEdge R730, service tag DWG7HH2)
**Status:** 🟡 Built & committed 2026-07-08 — pending deploy on Jarvis
**Author:** Kyle Mason (NetFRAME homelab)
**Source:** `Home-Lab/scripts/jarvis-oncall/` (see its `README.md`)
**Related:** [[Runbook/Jarvis-LLM-Platform-2026-07-05]] · [[Infrastructure/Proxmox Cluster]] · [[Infrastructure/Services & VMs]] · [[Runbook/Security-VLAN-Segmentation-Phased-2026-07-03]]

---

## 1. What it is

A Discord bot that runs on **Jarvis** so any km-cluster node can be troubleshot
remotely: paste an error/log excerpt into Discord and the bot identifies the
node, diagnoses it via Jarvis's `llm_router` (Ollama-first / Claude-fallback),
runs **read-only diagnostics over SSH**, and — for state-changing fixes —
proposes the exact command and waits for explicit confirmation before running it.

Reuses the existing low-priv **`monitor`** user (from the NetFRAME health daemon,
see [[Runbook/Cluster-Health-Fixes-2026-07-07]]) for SSH; Jarvis itself is checked
locally.

## 2. Architecture

- **Python `discord.py`**, systemd service `jarvis-oncall` on Jarvis.
- **Node registry** (`nodes.yaml`) maps node → SSH host/role/quirks/restart
  allowlist, so tools are node-agnostic and adding a node needs no code change.
- Forwards messages to **`llm_router` `:8000`** with the whitelisted tool schemas.
  This required an **additive tool-calling passthrough** in `llm_router.py`
  (Ollama native + Anthropic conversion; `tool_use` → OpenAI `tool_calls`) —
  no-tools callers (Open WebUI, RAG) are unaffected.
- **Agentic loop:** model calls tools → bot runs the read-only ones as `monitor`
  → feeds results back → model analyzes and answers. Live `🔧` progress posted.

## 3. Security model (non-negotiable)

- Answers **only** `ALLOWED_USER_ID` (allowlist-of-one), in DMs or one
  `CHANNEL_ID`; everyone else ignored + audit-logged.
- **No raw shell** — the model may only name whitelisted tools; each validates
  its target node first.
- **Read-only** tools run free: `check_service_status`, `tail_logs`,
  `zpool_status`, `gpu_status`, `disk_usage`, `vm_status`.
- **`restart_service`** is the ONLY state-changing tool. Confirm-and-execute:
  bot posts `sudo systemctl restart <unit>` + node and waits for an explicit
  `yes`/`do it` (60 s) before running via **command-exact NOPASSWD sudo**.
  Refuses any unit outside that node's allowlist and any unreachable node —
  without prompting. `corosync` / `pve-cluster` / `sshd` deliberately excluded.
- Token + IDs live in `/opt/jarvis-oncall/.env` (chmod 600, token from
  Vaultwarden), never in git.
- Every diagnostic run and executed command → `/var/log/jarvis-oncall/audit.jsonl`.

## 4. Restart allowlist (per node)

| Node | Allowed `restart_service` units |
|---|---|
| Jarvis | llm_router, ollama, netframe-monitor, netframe-report-web, gpu-fan-control |
| QuarkyLab | slurmctld, slurmd, munge |
| Randy | proxmox-backup, proxmox-backup-proxy, jellyfin, zfs-zed |
| pve2 | pveproxy, pvedaemon, pvestatd *(OPNsense VM 100 is restarted via `qm`, not here)* |
| pve3 | pveproxy, pvedaemon, pvestatd, nut-server, nut-monitor |
| pve4 / pve5 | pveproxy, pvedaemon, pvestatd |

> **pve1** (standalone Mac Mini / Pi-hole) is registered but `reachable: false`
> — it has no `monitor` user, so the bot cannot reach it until one is provisioned.

## 5. Deploy checklist (on Jarvis)

1. `rsync` `Home-Lab/scripts/jarvis-oncall/` → `/opt/jarvis-oncall/`; create venv,
   `pip install -r requirements.txt`.
2. **Redeploy the router:** `systemctl restart llm_router` (additive change,
   safe for existing callers); confirm `curl -s localhost:8000/health`.
3. Install the two sudoers examples on the **remote** nodes (Jarvis needs none):
   `sudoers.d-jarvis-oncall-readonly.example` (zpool/qm/pct reads) and
   `sudoers.d-jarvis-oncall.example` (the restart allowlist). `visudo -c`.
   Ensure `monitor` can read journals (group `systemd-journal`/`adm`).
4. `install -m600 .env.example /opt/jarvis-oncall/.env`, then set `DISCORD_TOKEN`
   (Vaultwarden), `ALLOWED_USER_ID` (your Discord user ID), optional `CHANNEL_ID`.
   For most reliable tool-calling set `ROUTER_MODEL=claude-opus-4-8` (needs the
   router's `ANTHROPIC_API_KEY`); default is the local 72B.
5. `install -m644 jarvis-oncall.service /etc/systemd/system/`; `daemon-reload`;
   `systemctl enable --now jarvis-oncall`; `journalctl -u jarvis-oncall -f`.

## 6. Smoke tests (post-deploy)

- DM the bot an error → expect node identification + `🔧` read-only diagnostics
  + analysis.
- Trigger a restart proposal → expect the confirm prompt; reply `no` (verify
  nothing runs), then reply `yes` on a safe unit (e.g. `jellyfin` on Randy) and
  confirm `audit.jsonl` records `confirmed` + `executed_mutation`.

## 7. Notes / TODO

- Local model runs at `OLLAMA_NUM_CTX=8192`; tool output is capped at 1800 chars
  each and the loop at 4 tool rounds to fit context.
- Provision a `monitor` user on pve1 if Pi-hole coverage is wanted.
- Consider adding it to PBS-relevant monitoring once in production.
