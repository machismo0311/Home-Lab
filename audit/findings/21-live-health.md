# 21 — Live Node Health (Phase 2)

**Scan:** 2026-07-22 ~14:00 EDT from Ares, read-only SSH. All 8 nodes reachable.
Raw: `audit/live/<node>.txt`, `<node>-supp.txt`.

## Cluster: 7/7 Quorate ✅
`pvecm status` = Nodes 7, Quorate Yes, Total votes 7/7 (pve2-5 + QuarkyLab + Jarvis + Randy).
pve1 is standalone (not a member) — correct per CLAUDE.md.

## Per-node

| Node | PVE | Kernel (running) | Uptime | Failed units | Pending apt | Holds | reboot-req |
|---|---|---|---|---|---|---|---|
| pve1* | **9.1.9** | 7.0.0-3-pve | 3d22h | **openipmi FAILED** | **133** | — | no |
| pve2 | 9.2.3 | 7.0.12-1-pve | 3d22h | none | 73 | — | yes |
| pve3 | 9.2.3 | 7.0.12-1-pve | 3d22h | none | 74 | — | yes |
| pve4 | 9.2.3 | 7.0.12-1-pve | 3d22h (load ~5) | none | 73 | — | yes |
| pve5 | 9.2.3 | 7.0.12-1-pve | 3d22h | none | 74 | — | yes |
| QuarkyLab | 9.2.3 | **6.14.11-9-pve** (pinned ✅) | 11d11h | none | 94 | **nvidia-* + kernel HELD** | yes |
| Jarvis | 9.2.3 | **6.14.11-9-pve** (pinned ✅) | 7d22h (load ~2) | none | 74 | **kernel HELD** | yes |
| Randy | 9.2.3 | 7.0.12-1-pve | 7d23h | none | 63 | wazuh-agent HELD | yes |

\*pve1 = standalone Mac Mini (Pi-hole/homepage host), not km-cluster.

## Findings
- **F-H1 · MEDIUM — Kernel-pin holds are INTACT (verified good).** QuarkyLab holds the full
  `nvidia-*` driver stack **and** `proxmox-kernel-6.14.11-9-pve-signed`/`proxmox-default-kernel`;
  Jarvis holds the kernel packages; both run `6.14.11-9-pve`. The exact "silent hold removal"
  risk the spec worried about is **not present**. (Note: Jarvis holds the *kernel* but not the
  `nvidia-*` packages the way QuarkyLab does — a driver-only apt upgrade could DKMS-rebuild; low
  risk since the kernel is held, but worth mirroring QuarkyLab's fuller hold set.)
- **F-H2 · MEDIUM — Patch lag across the fleet.** 63–94 pending upgrades per cluster node,
  **133 on pve1**, and every cluster node has `reboot-required`. Not urgent, but the fleet is a
  couple of kernel/security cycles behind. pve1 (standalone, 9.1.9) is the most behind.
- **F-H3 · LOW — `openipmi.service` FAILED on pve1.** LSB init failure; pve1 is a Mac Mini with
  no BMC, so OpenIPMI has nothing to bind — cosmetic, but it's a persistent failed unit. Mask it
  or leave documented.
- **F-H4 · INFO — pve4 load ~5** sustained. Consistent with its role (Grafana/Prom/Loki CT 103 +
  RKE2 cp2 VM 202). Memory healthy (23Gi avail). No action.
- Disk headroom healthy everywhere (root 12–36% used). Memory healthy on all nodes.
- **NTP:** all nodes report clock present; no obvious skew (uptimes/timestamps consistent).

See `22-storage-backup.md` for the Randy `bulk` **DEGRADED pool (CRITICAL)** — the top finding.
