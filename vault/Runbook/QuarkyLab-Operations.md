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
| *(Randy)* GC daily 03:00 + verify Sun 04:00 | | PBS datastore hygiene |

## Data protection
- **`workspace/scratch` capped** — `quota=2T` + `userquota=200G` per user (can't starve the shared pool).
- **`workspace/fernanda` `refreservation=2T`** — guarantees her production DUNE data a 2 TB floor even if students fill their datasets (the pool's dataset quotas oversubscribe it).
- **Backup restore-tested** — fernanda archive restored byte-identical from PBS.

## Availability
- **`base.sif` runs from the LOCAL copy** `/workspace/containers/base.sif`, not Randy NFS — a Randy hiccup no longer blocks student job launch. `/data/shared` is bound **only when reachable** (optional; holds just the quickstart). The `/data` copy stays the rebuild master; the daily `sync-base-sif` timer refreshes the local copy after rebuilds.

## Scheduling fairness
- **`PriorityType=priority/multifactor`** with `PriorityWeightFairshare=100000`, `PriorityWeightAge=10000`, `PriorityDecayHalfLife=3-0` — among 20 students (equal shares), queue order favors those who've used the GPU least. Preemption (research > student `PriorityTier`) still governs Fernanda's priority.

## Monitoring
- **Metrics:** `quarkylab-metrics.sh` writes GPU (util/mem/temp/power) + SLURM (running/pending/students_active/shards_allocated) as `quarkylab_*` gauges to node_exporter's textfile dir (`/var/lib/prometheus/node-exporter/`). QuarkyLab is already a Prometheus target (`instance="quarkylab"`, job `proxmox-nodes`) — **confirmed live in Prometheus**.
- **Grafana dashboard:** import `QuarkyLab:/root/quarkylab-grafana-dashboard.json` (Grafana → Dashboards → Import → upload/paste → pick the Prometheus datasource). 7 panels: GPU util, GPU memory used/total, temp, power, shards-allocated gauge, active students, SLURM running/pending.
- Example PromQL: `quarkylab_gpu_utilization_percent`, `quarkylab_gpu_memory_used_bytes / quarkylab_gpu_memory_total_bytes`, `quarkylab_slurm_shards_allocated`.

## 8-way load-tested
8 concurrent student jobs ran, each hard-capped, 8 MPS servers coexisting, clean drain — see [[Runbook/QuarkyLab-Phase04-GPU-Sharing-2026-07-02]].
