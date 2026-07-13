# 🧭 Operations and Onboarding

> **Operator:** Kyle Mason (`machismo`) · **Cluster:** km-cluster · 7-node PVE 9.2.3
> **Purpose:** how NetFRAME is run day to day · **Last Updated:** 2026-07-12

**Tags:** #operations #onboarding #reference

> [!NOTE] **Audience:** a new operator (or a reviewer) who needs to run this cluster, not just read about it. It covers how to get in, where things live, the routine, the common procedures, and the rules you do not break. Deep procedures live in the linked runbooks.

---

## Orientation (read first)
Start with [[Architecture Overview]] for the system and [[00 - Homelab MOC]] for the full index. The design reasoning is in the [[ADR/README|decision records]], and the resilience posture is in [[High Availability/High Availability MOC]]. This document is the operator's entry point that ties them together.

## Access
- **Local and remote reach:** SSH uses the aliases in `~/.ssh/config` (`pve2`..`pve5`, `randy`, `quarkylab`, `jarvis`, plus BMC and switch hosts). Remote access is the self-hosted Headscale tailnet; once on it, the same LAN addresses resolve.
- **Web consoles:** Proxmox on any node at `:8006`, Proxmox Backup Server on Randy at `:8007`, Grafana and the service UIs behind the Nginx Proxy Manager.
- **Credentials:** everything is in Vaultwarden. Nothing is hardcoded, and nothing sensitive is committed to git.
- **OPNsense:** SSH is disabled by design. Emergency access is the serial console via `qm terminal 100` from pve2. The config is backed up nightly, encrypted, to a private repo, and a cold restore is documented.

## Where everything lives
Node, IP, and service tables are in the Home-Lab CLAUDE.md and [[Infrastructure/Services & VMs]]. The short version: pve2 runs OPNsense, pve3 runs the core service containers (DNS, proxy, monitoring, secrets, VPN), pve4 and pve5 round out the cluster, the two R730s carry GPU work, and Randy carries storage and backups.

## Daily operations
Follow [[Runbook/Daily Operations]]. The essentials each day: confirm all nodes are up and quorate, confirm the monitoring stack is green and no alerts are open in Discord, and confirm last night's backups ran. Monitoring is the primary signal; you should learn about a problem from an alert, not from a user.

## Common procedures
- **Reboot a node safely:** confirm which guests have `onboot=1` and which have a working guest agent for graceful shutdown (notably OPNsense VM 100 and Wazuh VM 104). Reboot, then confirm quorum and that guests came back. Details and node-specific gotchas are in [[Runbook/Recovery Procedures]].
- **Restore from backup:** Proxmox Backup Server on Randy holds per-guest restore points from the nightly jobs. Restore a container or VM from the PBS UI or the CLI.
- **Respond to an alert:** the alert names the failing target. Check it against the dashboards, then follow [[Runbook/Recovery Procedures]]. Logs are in Loki.

## Non-negotiable safety rules
- **pve2 and OPNsense network changes are high-risk** (a past change caused an outage). Keep the Ares wired management leg connected during any pve2 or OPNsense work, and verify a change before trusting it.
- **GPU node kernels are pinned.** QuarkyLab and Jarvis run kernel `6.14.11-9-pve` for the NVIDIA 550 stack. Never upgrade the kernel or change the GRUB default on these nodes. See [[ADR/0010-gpu-node-kernel-pinning]].
- **Do not hard power-cycle Wazuh VM 104.** It corrupts the indexer. It now has a guest agent for graceful shutdown; use that.
- **Keep PBS storage for pve-node backups on Randy's VLAN 1 address** (`.10.187`). A prior VLAN 30 repoint silently broke node backups.
- **Secrets go to Vaultwarden, never into git or a config file.**
- **DNS is HA.** Two Pi-hole instances answer; do not assume a single resolver when troubleshooting.

## When something breaks
Look at monitoring first (Grafana and the Discord alerts), then work the relevant runbook: [[Runbook/Recovery Procedures]] for node and service recovery, [[Runbook/Production-Readiness-Checklist-2026-07-10]] for the current state of known gaps. This is a single-operator lab, so the runbooks are the escalation path.

## Key references
- [[00 - Homelab MOC]] · [[Architecture Overview]] · [[ADR/README]] · [[High Availability/High Availability MOC]]
- [[Runbook/Daily Operations]] · [[Runbook/Recovery Procedures]] · [[Runbook/Production-Readiness-Checklist-2026-07-10]]
