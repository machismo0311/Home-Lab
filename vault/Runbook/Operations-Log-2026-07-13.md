# Operations Log, 2026-07-13

**Tags:** #log #ops #changelog

Focused record of the operational changes made on 2026-07-13. Detail lives in the linked runbooks and repos; this is the index of what changed.

---

## Infrastructure

- **Ares off-box backup built.** Encrypted `restic` to Randy `bulk` pool, daily 04:00 (systemd user timer), works over wired or wifi, staleness alert to Discord. Full detail and restore steps: [[Runbook/Ares-Backup-Restore]].
- **`192.168.1.1` orphan cleanup.** pve3/pve4 (and pve5 already) had a stale hardcoded `gateway 192.168.1.1`; corrected to `192.168.10.1`. Verified no bogus `192.168.1.1` remains on any node, LXC, VM, or in OPNsense. The only legitimate `192.168.1.1` is the FirstNet hotspot on WAN2.
- **RKE2 control-plane gateways verified** (`rke2-cp1/2/3` all on `192.168.10.1`, read via hostNetwork pods since those VMs lack SSH/guest-agent).
- **WAN2 / FirstNet failover** progressed (MR7400 on OPNsense WAN2). Finish is pinned. Detail: [[Runbook/WAN-Failover-FirstNet-MR7400-Plan-2026-07-12]].

## Documentation and repos

- **Network topology rewritten to v2.0** (dual-WAN edge correction, RKE2 section, Randy `bulk` + Jarvis `tank`/`scratch`, DNS HA; US Letter; no em dashes). Published in `Home-Lab/topology/`; private pipeline repo `netframe-topology` reconciled to match. See [[project-netframe-topology]] (memory).
- **GitHub forensic audit** across all 10 repos: full-history secret scan, source-of-truth, docs/hygiene/formatting/cross-repo. Findings remediated or pinned; internal IPs deliberately kept public (already in the topology), vault public WAN IP + MAC addresses redacted, placeholder curl creds normalized, one stale branch deleted and two preserved as PRs, LICENSE + SECURITY.md added to the public repos.

## Security and git hardening

- **SSH commit signing** enabled globally (key `~/.ssh/id_ed25519`); all commits now sign and verify locally. GitHub-side signing-key registration is pinned.
- **gitleaks pre-commit hook** installed on dotfiles and Home-Lab (`.githooks/`, `core.hooksPath=.githooks`, run `.githooks/install-hooks.sh` per clone; bypass `git commit --no-verify`). Binary at `~/.local/bin/gitleaks`.
- **CLAUDE.md files made private** (untracked from the public repos, gitignored, kept local so Claude Code still reads them). See [[project-claude-md-private]] (memory).
- **Scrutiny InfluxDB token** redacted from the `netframe-monitoring-stack` repo HEAD; rotation pinned.

## Open items (pinned, when home)

See [[Runbook/Production-Readiness-Checklist-2026-07-10]] section 7:
1. Install `qemu-guest-agent` on RKE2 VMs (201/202/203).
2. Register the SSH signing key on GitHub (Verified badge).
3. Rotate the Scrutiny InfluxDB token on CT103.
4. Confirm the Ares backup password is stored in Vaultwarden (disaster-recovery dependency).

## Open PRs (your review)

- Home-Lab PR #5: netlab r3 redundant path + automated OSPF failover CI test.
- Manstuffco PR #1: Cloudflare Workers configuration.
