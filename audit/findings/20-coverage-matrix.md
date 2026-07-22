# 20 — Monitoring / Backup Coverage Matrix (Phase 2)

**Scan:** 2026-07-22, read-only. ✅ verified active · ❌ absent · UNK not verifiable read-only.
Prom-target column from Prometheus `/targets` (15/15 up); agent columns from `systemctl is-active`.

| Node | Wazuh agent | Promtail→Loki | node-exporter | Prom target UP | Guests backed up <25h |
|---|---|---|---|---|---|
| pve1* | ✅ | ✅ | ✅ | ✅ | ❌ **no backup job** (CT103 Pi-hole, CT104) |
| pve2 | ✅ | ✅ | ✅ | ✅ | ✅ VM100 |
| pve3 | ✅ | ✅ | ✅ | ✅ | ✅ CT101/102/106/107 |
| pve4 | ✅ | ✅ | ✅ | ✅ | ✅ CT103, VM202 |
| pve5 | ✅ | ✅ | ✅ | ✅ | ✅ CT105/108, VM110/203 |
| QuarkyLab | ✅ | ✅ | ✅ | ✅ | ✅ VM104 |
| Jarvis | ✅ | ✅ | ✅ | ✅ | n/a (no guests) |
| Randy | ✅ | ✅ | ✅ | ✅ | n/a (storage host) |

\*pve1 standalone.

## Reading the matrix
- **Agent coverage is complete** — Wazuh + Promtail + node-exporter active on **all 8 nodes**,
  and Prometheus is actually scraping all of them (15/15 targets up). The "exporter up but
  Prometheus silently not scraping" mismatch (the column the spec flags as HIGH) is **clean**.
- **The one ❌ is pve1's guests** — the primary Pi-hole (CT 103) and old homepage (CT 104) have
  **no backup** (F-B1, `22-storage-backup.md`). Every cluster guest is covered.
- **Scrutiny** (drive health): collectors documented on Randy(43)/QuarkyLab(7)/Jarvis(1) →
  ~50 drives; not independently re-counted this pass (InfluxDB-backed, needs Scrutiny UI). Marked
  **UNK** — recommend confirming Scrutiny flagged `mpathv` (it should have SMART data on the dying
  ST4000NM0023).
- **Ansible inventory** membership per node: not cross-checked live (playbooks scanned in Phase 1);
  marked UNK for this matrix.

## Highest-value gaps (→ backlog)
1. pve1 guests not backed up (HIGH).
2. No **PBS-backup-stale** alert rule — a missed backup wouldn't page (see `24-observability.md`).
3. Verify Scrutiny caught the dying `mpathv` drive (SMART should predate the ZFS fault).
