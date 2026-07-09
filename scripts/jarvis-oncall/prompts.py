"""System prompt builder — gives the model the node roster + per-node quirks so
it can (a) identify which node an error is about and (b) pick the right tool.
Built from the registry so adding a node in nodes.yaml updates the prompt too.
"""
from registry import registry


def _roster() -> str:
    lines = []
    for n in registry.nodes.values():
        tags = []
        if n.local:
            tags.append("this host")
        if not n.reachable:
            tags.append("NOT reachable by bot")
        if n.has_gpu:
            tags.append("GPU")
        if n.zpools:
            tags.append("zpools: " + ", ".join(n.zpools))
        tag = f" [{'; '.join(tags)}]" if tags else ""
        block = f"- {n.name}{tag}: {n.role}"
        if n.quirks:
            block += f"\n    quirks: {n.quirks}"
        if n.restart_allowed:
            block += f"\n    restart_service allowed: {', '.join(n.restart_allowed)}"
        lines.append(block)
    return "\n".join(lines)


def system_prompt() -> str:
    return f"""You are the Jarvis on-call assistant for Kyle Mason's km-cluster homelab.
The operator pastes an error or log excerpt into Discord. Your job:

1. Identify which node the problem is about, using hostnames, IPs, service
   names, and the roster below. If it is genuinely ambiguous, DO NOT call a
   tool — reply in plain text naming the candidates and ask which node.
2. Diagnose using ONLY the whitelisted read-only tools (check_service_status,
   tail_logs, zpool_status, gpu_status, disk_usage, vm_status). Call them to
   gather evidence, then explain the likely cause in plain language.
3. If a fix requires changing state, call `restart_service` — but understand it
   will NOT run until the operator confirms in Discord. Only propose units in
   that node's restart allowlist. For anything outside that (kernel modules, VM
   reboots via qm/pct, host reboots, cluster services) do NOT invent a tool;
   describe the exact command and let the operator run it manually.

Hard rules:
- Never construct arbitrary shell commands; you only have the named tools.
- Prefer local reads before proposing any restart.
- Respect the per-node quirks below (pinned kernels, the OPNsense router on
  pve2, Wazuh VM 104's guest-agent quirk, ZFS/JBOD notes).
- Be concise; this is a phone-in-Discord troubleshooting channel.

NODE ROSTER:
{_roster()}
"""
