# 24 — Observability (Phase 2)

**Scan:** 2026-07-22, read-only, from inside CT 103 on **pve4** (stack location confirmed).
Raw: `audit/live/observability.txt`. Prometheus/Grafana/Loki localhost-only (F-03 hardening).

## Stack location — confirmed (and documents the Phase 1 staleness)
- **Grafana + Prometheus + Loki = LXC 103 on pve4** (`.183`), moved there 2026-07-16. Live-confirmed
  (`pct exec 103` on pve4 serves :9090/:3000). Repo topology/README still say pve3 → see
  `11-contradictions.md` S-Grafana.
- **No Alertmanager** — alerting is Grafana unified alerting → Discord (matches CLAUDE.md).

## Prometheus
- **Targets: 15 UP / 0 DOWN** ✅. No blind spots from broken scrapes — the "exporter running but
  Prometheus not scraping" failure mode is **not** present.
- **Alerting rules in Prometheus: 0** — expected; the alert rules live in **Grafana**.
- **ZFS health metrics present for ALL 5 pools** (`node_zfs_zpool_state`, `node_zfs_pool_health`,
  `node_zfs_pool_capacity_percent` cover `bulk, datastore, scratch, tank, workspace`). The custom
  textfile collector is exporting (`node_textfile_mtime_seconds` = 44 series). **So the stack has
  the data to detect the degraded `bulk` pool.**

## ✅ RESOLVED by parallel AAR — the alert path DID have a gap (NF-INC-2026-07-22)
**Update (mid-audit):** a concurrent session's `vault/Runbook/AAR-2026-07-22-Backup-Verify-Scheduler-and-DS4246-Drive.md`
independently diagnosed this exact drive and answers the question below. The direct
`ZfsPoolDegraded` signal did **not** surface it; instead the degraded state was **masked for
~71h**: the `backup-verify` job runs as an **Ares user cron**, Ares (a laptop) **suspends
overnight**, and user crontab has **no catch-up** → 3 nightly runs silently dropped, freezing
the `backup_verify_*` metric at 2026-07-19 16:55. `BackupVerifyReportStale` fired; once the job
was reinstated, `overall_pass` flipped 1→0 exposing the FAULTED `mpathv`. **This is a real
alerting blind spot, now being fixed** (Persistent systemd user timer + role hardening,
distinguishing "dead job" from "failing check"). My independent finding (live `zpool status`)
corroborates theirs. **G1/R-02 is confirmed as a genuine gap, already under remediation.**

## 🟠 (original open item, retained for the record) — did the ZfsPoolDegraded alert fire for `bulk`?
This is the decisive observability question and I **could not verify it read-only**: Grafana's
alert-state API requires authentication (the unauthenticated call returns an empty rule set, not
ground truth), and I will not hunt for credentials (H3). Two possibilities:
1. **It fired** → check the Discord `discord-alerts` (infra) channel for a ZfsPoolDegraded /
   `bulk` notification dated ~last 3 days. If present, the pipeline works and this is just a
   pending drive-replacement.
2. **It did NOT fire** → there is a real alerting gap (rule threshold, Grafana eval, or Discord
   contact-point broken) and a CRITICAL degraded pool went **silent** — the exact "silenced real
   problem" failure the spec warns about.

**Action (Kyle):** confirm the Discord channel received the alert. If not, the alert-delivery
path needs fixing — a degraded pool that doesn't page is worse than no monitoring, because it
reads as "all green." (The 2026-07-16 AAR already noted "zero alerts fire: Grafana was on the
dead node" — a reminder this pipeline has a history of silent gaps.)

## Alert-rule coverage (from CLAUDE.md, not live-readable without creds)
Documented Grafana rules: InstanceDown, PiholePrimaryDown, PiholeSecondaryDown, **ZfsPoolDegraded**,
GpuTempHigh, GpuMemoryHigh, DiskAlmostFull, LowMemory, UPS. Gaps vs failure modes this lab can
actually hit:

| Failure mode | Rule exists? | Notes |
|---|---|---|
| ZFS degraded | ✅ ZfsPoolDegraded | **verify it fired for `bulk` now** (above) |
| Node down | ✅ InstanceDown | targets 15/15 up |
| DNS down | ✅ Pihole primary/secondary | blackbox probes .177/.178 |
| Disk full / low mem | ✅ DiskAlmostFull / LowMemory | |
| GPU temp/mem | ✅ GpuTempHigh / GpuMemoryHigh | |
| UPS on battery | ✅ UPS | PeaNUT/NUT feed |
| **PBS backup stale >25h** | ❓ not listed | **gap** — no rule that a guest missed backup |
| **PBS verify failed** | ❓ not listed | **gap** |
| **Cert expiry (step-ca)** | ❓ not listed | **gap** |
| **10G link down / flap** | ❓ not listed | **gap** (see pve3 NIC-hang history) |
| **Cluster quorum lost** | ❓ not listed | **gap** (no pve-exporter) |

→ Feeds `30-gap-analysis.md`: **prometheus-pve-exporter** (quorum/backup-task/guest metrics) and
**backup-stale / cert-expiry alert rules** are the cheapest wins given the stack already exists.

## Grafana provisioning & backup (from repo)
- Config-as-code in private repo `machismo0311/netframe-monitoring-stack` (CLAUDE.md) — good; not
  live-verified this pass.
- Grafana CT 103 is in the nightly PBS LXC job (verified §22, backup 07-22 06:00Z) ✅.
