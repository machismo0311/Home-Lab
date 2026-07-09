# ⚙️ QuarkyLab — Operations & Go-Live Hardening
**Tags:** #runbook #quarkylab #ops #monitoring #slurm #zfs
**Related:** [[Runbook/QuarkyLab-Phase04-GPU-Sharing-2026-07-02]] · [[Infrastructure/QuarkyLab Storage]] · [[Runbook/QuarkyLab-Account-Onboarding]] · [[Runbook/QuarkyLab-Student-Quickstart]]

The reliability/observability layer added around the student environment (2026-07-02).

## Scheduled services (systemd timers on QuarkyLab)
| Timer | When | Does |
|---|---|---|
| `pbs-workspace-backup.timer` | daily 01:30 | back up `workspace/{students,researchers,fernanda}` → Randy PBS (`host/quarkylab-workspace`) |
| `scratch-purge.timer` | daily 04:30 | delete `/workspace/scratch/*/` files >14 days (`scratch-purge.sh`) |
| `sync-base-sif.timer` | daily 05:00 | refresh local `/workspace/containers/base.sif` from `/data` master (`sync-base-sif.sh`) |
| `quarkylab-metrics.timer` | every 30 s | publish GPU/SLURM metrics to node_exporter (`quarkylab-metrics.sh`) |
| `quarkylab-researcher-alert.timer` | every 60 s | Discord ping on a researcher's first login / SLURM job (`quarkylab-researcher-alert.sh`) |
| `ac-snapshot.timer` | daily 23:55 | snapshot `ac -pd` + `ac -p` connect time → `/var/log/account/snapshots/YYYY-MM-DD.txt` (`ac-snapshot.sh`) |
| *(Randy)* GC daily 03:00 + verify Sun 04:00 | | PBS datastore hygiene |

## Data protection
- **Storage & backup on VLAN 30** (2026-07-02) — NFS `/data` and the PBS workspace backup now use Randy `192.168.30.187`; the node is dual-homed (cluster/management on VLAN 1). See [[Runbook/VLAN30-Migration-Report-2026-07-02]].
- **`workspace/scratch` capped** — `quota=2T` + `userquota=200G` per user (can't starve the shared pool).
- **`workspace/fernanda` `refreservation=2T`** — guarantees her production DUNE data a 2 TB floor even if students fill their datasets (the pool's dataset quotas oversubscribe it).
- **Backup restore-tested** — fernanda archive restored byte-identical from PBS.

## Availability
- **`base.sif` runs from the LOCAL copy** `/workspace/containers/base.sif`, not Randy NFS — a Randy hiccup no longer blocks student job launch. `/data/shared` is bound **only when reachable** (optional; holds just the quickstart). The `/data` copy stays the rebuild master; the daily `sync-base-sif` timer refreshes the local copy after rebuilds.

## Scheduling fairness
- **`PriorityType=priority/multifactor`** with `PriorityWeightFairshare=100000`, `PriorityWeightAge=10000`, `PriorityDecayHalfLife=3-0` — among 20 students (equal shares), queue order favors those who've used the GPU least. Preemption (research > student `PriorityTier`) still governs the researcher's priority.

## Monitoring
- **Metrics:** `quarkylab-metrics.sh` writes GPU (util/mem/temp/power) + SLURM (running/pending/students_active/shards_allocated) as `quarkylab_*` gauges to node_exporter's textfile dir (`/var/lib/prometheus/node-exporter/`). QuarkyLab is already a Prometheus target (`instance="quarkylab"`, job `proxmox-nodes`) — **confirmed live in Prometheus**.
- **Grafana dashboard: IMPORTED & live** → `http://192.168.10.183:3000/d/quarkylab-gpu/quarkylab-gpu-cluster` (uid `quarkylab-gpu`, 7 panels: GPU util, GPU memory used/total, temp, power, shards-allocated gauge, active students, SLURM running/pending). Source JSON kept at `QuarkyLab:/root/quarkylab-grafana-dashboard.json`. Grafana is docker in pve3 LXC103; re-import via `pct exec 103 -- curl -u admin:<pw> -XPOST localhost:3000/api/dashboards/db -d @payload`.
- Example PromQL: `quarkylab_gpu_utilization_percent`, `quarkylab_gpu_memory_used_bytes / quarkylab_gpu_memory_total_bytes`, `quarkylab_slurm_shards_allocated`.

## Researcher-activity alerts (2026-07-08)
`quarkylab-researcher-alert.sh` (systemd `quarkylab-researcher-alert.timer`, 60 s poll) fires a **Discord** ping the **first time** any real user does either of:
- **logs in over SSH** — parsed from sshd `Accepted` lines via `journalctl -u ssh --since @<watermark> -g 'Accepted'` (catches LAN, Headscale, and Cloudflare-tunnel/localhost sources), or
- **submits a SLURM job** — union of `squeue` + `sacct`, tracked by max numeric JobID.

- **Who counts:** non-admin human accounts only — students, researchers, and `fernanda` (uid 1000–59999). **Excluded:** `kyle`, `machismo`, `root`, and **`monitor`** (the NetFRAME health daemon SSHes in every 15 min → would be constant noise).
- **Once per event:** watermarks in `/var/lib/quarkylab-alert/{last_jobid,last_login_epoch}`, **seeded to "now" at install** so only *future* activity alerts (no history replay).
- **Webhook:** root-only `/etc/quarkylab-alert.conf` (`DISCORD_WEBHOOK=…`, mode `600`, **kept out of git** — same house Discord channel as the NUT/Grafana UPS alerts). If the webhook is empty the script still `logger -t qlab-alert` to the journal.
- **Modes:** `--seed` (reset watermarks to now), `--test` (send a test ping). Install seeds watermarks + enables the timer.
- Script `/usr/local/sbin/quarkylab-researcher-alert.sh`; units `/etc/systemd/system/quarkylab-researcher-alert.{service,timer}`. **Installed, detection-replay tested, and Discord delivery confirmed 2026-07-08.**
- **Webhook live (2026-07-09):** real Discord webhook written to `/etc/quarkylab-alert.conf`; `--test` ping delivered (exit 0, journal `qlab-alert` confirmed). Alerting is fully active — no longer log-only.

## Accounting & activity monitoring (2026-07-09)
Process accounting was previously absent (`ac` not installed → connect time had to be reconstructed from `last`/wtmpdb durations). Now installed and running.

- **`acct` 6.6.4-8 installed** — `acct.service` enabled + active; accounting writes to `/var/log/account/pacct`. Gives real per-user connect time **and** per-command history.
- **Commands:** `ac -p` (total connect hrs/user), `ac -pd` (per-user, per-day), `sa -u` (every command + who ran it), `lastcomm <user>` (chronological command log for a user).
- **Daily snapshot:** `ac-snapshot.timer` (23:55, `Persistent=true`) → `/usr/local/sbin/ac-snapshot.sh` writes dated `ac -pd` + `ac -p` to `/var/log/account/snapshots/YYYY-MM-DD.txt` (640), pruning snapshots >400 days. Durable per-day connect record even after `wtmp` rotates.
- **Caveat — connect time ≠ shell time:** `ac`/`ac -pd` count any session that holds a login open, so **VPN / VS Code Remote-SSH** sessions inflate the hours (e.g. kieron showed 27 h via `ac -p` vs ~1 h 22 m of true interactive shell in `last`). Use `ac -pd` for *which days / trends*; use `last` durations for real human interactive time.
- **pacct baseline:** the raw command log was reset 2026-07-09 11:23 (cleared install-time self-test entries) — so `lastcomm`/`sa` have **no records before that timestamp** by design (not data loss). Connect-time history (wtmp-based) was unaffected.

## 8-way load-tested
8 concurrent student jobs ran, each hard-capped, 8 MPS servers coexisting, clean drain — see [[Runbook/QuarkyLab-Phase04-GPU-Sharing-2026-07-02]].
