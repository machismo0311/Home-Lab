# Monitoring & Alerting — Grafana → Discord (2026-07-10)

**Tags:** #runbook #monitoring #alerting #grafana #prometheus #discord
**Related:** [[Infrastructure/Services & VMs]] · [[Runbook/DNS-HA-OPNsense-Resilience-2026-07-10]]
**Config-as-code:** private repo `machismo0311/netframe-monitoring-stack` (secrets redacted → Vaultwarden)

Added real alerting on top of the existing (metrics-only) Prom/Grafana/Loki stack. Metrics were collected but **nothing paged** — now they do.

## Architecture
- Stack: `pve3 CT 103` (`.183`), docker-compose project `grafana` — Grafana `:3000`, Prometheus `:9090`, Loki `:3100`, InfluxDB, Scrutiny, **blackbox `:9115`** (added 2026-07-10).
- **Alerting = Grafana v13 Unified Alerting → native Discord contact points.** No Alertmanager (fewer moving parts; Grafana has native Discord).
- **Two Discord channels:**
  - `discord-alerts` ← infra alerts (routed by label `notify=infra`)
  - `discord-ups` ← UPS alerts (root receiver; pre-existing, verified delivering)
- Grafana admin + InfluxDB creds: **moved to `600` `/opt/grafana/.env` (2026-07-10)**, compose uses `${VAR}` (repo `ct103/.env.example`). Discord webhook lives in Grafana's DB + Vaultwarden. Still inline: peanut-ups basic-auth in `prometheus.yml` (Prometheus can't env-interpolate scrape secrets — keep file `600`/use `password_file`).

## Alert rules (8)
| Rule | Fires | Sev | Channel |
|---|---|---|---|
| InstanceDown | target `up==0` 2m | crit | discord-alerts |
| PiholePrimaryDown | `.177` DNS fails 2m | crit | discord-alerts |
| PiholeSecondaryDown | `.178` DNS fails 2m | warn | discord-alerts |
| ZfsPoolDegraded | pool not ONLINE 5m | crit | discord-alerts |
| GpuTempHigh | GPU >87°C 5m | warn | discord-alerts |
| GpuMemoryHigh | GPU mem >90% 10m | warn | discord-alerts |
| DiskAlmostFull | root FS >90% 10m | warn | discord-alerts |
| LowMemory | avail <8% 10m | warn | discord-alerts |
| UPS battery low | charge <50% 2m | — | discord-ups |
| UPS runtime low | runtime <300s 1m | — | discord-ups |

Verified end-to-end: test alerts delivered to both channels; all rules `health=ok`.

## Exporters added this session
- **blackbox_exporter** (CT 103): `dns_ok` module queries `github.com` A-record against `.177`+`.178` → `probe_success`. Scrape job `pihole-dns` in `prometheus.yml`; targets carry `pihole=primary|secondary` labels. This detects the **DNS service** being down (host `up` alone wouldn't, since failover hides it).
- **ZFS pool textfile collector** on Randy/QuarkyLab/Jarvis: `/usr/local/sbin/zfs-pool-textfile.sh` + `zfs-pool-textfile.timer` (5 min) → writes `node_zfs_pool_health{pool=...}` (0=ONLINE 1=DEGRADED 2=SUSPENDED 3=other) to `/var/lib/prometheus/node-exporter/zfs_pool.prom` (Debian node_exporter default textfile dir). Covers pool-level RAIDZ health (drive SMART is separately covered by Scrutiny). Pools: Randy `bulk`+`datastore`, QuarkyLab `workspace`, Jarvis `tank`+`scratch`.

## Prometheus targets (job → count)
`proxmox-nodes` (8× node_exporter :9100), `peanut-ups` (.148:8081, both UPS units `tripplite`+`midatlantic`), `pihole-dns` (blackbox, 2), `prometheus` (self). Prometheus datasource UID in Grafana: `cfpgp47i5fk00b`.

## Add a new alert (via API)
`POST /api/v1/provisioning/alert-rules` (folderUID `infra-alerts`, ruleGroup `infra`, label `notify=infra`), 3-stage data: query A (Prometheus expr, instant) → reduce B (last) → threshold C. See existing rules in the config repo for the exact JSON shape.

## GPU collector (Phase 3, 2026-07-10)
`nvidia-smi → node_exporter textfile` on QuarkyLab + Jarvis: `/usr/local/sbin/nvidia-gpu-textfile.sh` + `nvidia-gpu-textfile.timer` (1 min) → `nvidia_gpu_{utilization_percent,memory_used_bytes,memory_total_bytes,temperature_celsius,power_watts}{gpu,name}`. Chose nvidia-smi-textfile over DCGM/container (fewer moving parts; GPUs run native, not passed to VMs). Alerts: GpuTempHigh >87°C, GpuMemoryHigh >90% (memory pressure = SLURM-vs-inference/transcode contention signal).

## Still open
- (done 2026-07-10) CT 103 compose secrets → `.env`; peanut basic-auth in prometheus.yml still inline.
- Optional: provisioning volume mount on Grafana so alerting is file-provisioned (currently API-created, persisted in `grafana-data`).
