# 🎛️ QuarkyLab Phase 04 — GPU Sharing (RTX 8000)
**Tags:** #runbook #quarkylab #slurm #gpu #cuda #ml
**Related:** [[Compute/Dell R730 - ML Node]] · [[Infrastructure/QuarkyLab Storage]] · [[Infrastructure/Proxmox Cluster]] · [[00 - Homelab MOC]]

---

## Status: ✅ DONE & VALIDATED — 2026-07-02 maintenance window

Turns on GPU access for the multi-tenant student SLURM environment: students share the single **Quadro RTX 8000 (48 GB)** via `gres/shard`, researchers/Fernanda get the whole card, and Fernanda is guaranteed priority via preemption. No driver/kernel changes (pin on `6.14.11-9-pve` / NVIDIA `550.163.01` untouched).

> [!NOTE] Why shard, not MIG or MPS
> RTX 8000 is Turing → **no MIG**. MPS would need `EXCLUSIVE_PROCESS` compute mode, disrupting Fernanda's full-card use. `gres/shard` keeps the card in Default mode and lets multiple student jobs co-schedule. Trade-off: shard is **soft** VRAM sharing (no hard per-job cap) — see Follow-ups.

---

## What changed

### `/etc/slurm/gres.conf` (new)
```
NodeName=QuarkyLab Name=gpu   Type=rtx8000 File=/dev/nvidia0
NodeName=QuarkyLab Name=shard Count=8
```

### `/etc/slurm/slurm.conf`
| Line | Value |
|---|---|
| `GresTypes` | `gpu,shard` |
| NodeName QuarkyLab | added `Gres=gpu:rtx8000:1,shard:8` |
| `PreemptType` | `preempt/partition_prio` |
| `PreemptMode` | `REQUEUE` |
| `AccountingStorageTRES` | `gres/gpu,gres/shard` |
| PartitionName research | added `PriorityTier=100` |
| PartitionName student | added `PriorityTier=1` |

`cgroup.conf` unchanged — **`ConstrainDevices=yes` was already set**, and it is the real enforcement gate (a job with no GPU GRES is denied `/dev/nvidia*` in its cgroup).

### `/etc/slurm/job_submit.lua` (student jobs)
- Added **`--nv`** to the `apptainer exec` wrapper (binds host driver libs → CUDA works in-container).
- **Auto-injects `--gres=shard:1`** (`tres_per_node=gres/shard:1`) when a student requests no GRES.
- **Rejects** student whole-GPU requests: *"Students may not request whole GPUs. Use --gres=shard:N."*

Backups: `/etc/slurm.bak.<ts>/`, `job_submit.lua.bak.<ts>`.

---

## Validation results (all passed)

| Test | Result |
|---|---|
| `sinfo` GRES | `gpu:rtx8000:1,shard:rtx8000:8` on both partitions ✓ |
| research `--gres=gpu:1` | `CUDA_VISIBLE_DEVICES=0`, RTX 8000 visible ✓ |
| research `--gres=shard:2` | GPU shared, visible ✓ |
| **no GRES** | `No devices found.`, `CVD=[]` — **denied** ✓ |
| student default job (no gres) | auto `gres/shard=1`; in-container `torch.cuda.is_available()=True`, RTX 8000, 47.8 GB ✓ |
| student `--gres=gpu:1` | **rejected** at submit ✓ |
| **preemption** | student shard job RUNNING → fernanda `gpu:1` submitted → student REQUEUED, fernanda RUNNING ✓ |

---

## How it works (operations)

- **Students** (`student` partition, default): just `sbatch job.sh`. They automatically get one shard (~6 GB soft), run inside the container with `--nv`, isolated (no net, own home, `/data/shared` RO, `/scratch`). Ask for more with `--gres=shard:N`. `studentqos` caps them at 1 running job → up to 8 students share the 8 shards.
- **Researchers / Fernanda** (`research` partition): `--gres=gpu:1` for the whole card (bypass the container wrapper). `--gres=shard:N` also available.
- **Fernanda guarantee:** research `PriorityTier=100` > student `PriorityTier=1` with `preempt/partition_prio` + `REQUEUE`. When she submits `gpu:1`, SLURM requeues student shard jobs to free the card; they restart automatically when she finishes. No static reservation needed (the old Phase-02 "permanent reservation" item is satisfied this way).

> [!WARNING] REQUEUE, not SUSPEND
> GPU preemption uses **REQUEUE** deliberately — a SUSPENDed CUDA process keeps its VRAM, so it wouldn't actually free the card. Requeue kills+requeues the student job, releasing the GPU.

---

## Rollback
```bash
latest=$(ls -d /etc/slurm.bak.* | tail -1)
rm -f /etc/slurm/gres.conf
cp -a "$latest"/. /etc/slurm/
systemctl restart slurmctld slurmd
```

---

## Follow-ups (optional)
- **Phase 04b — hard VRAM caps (investigated 2026-07-02 → DEFERRED, soft-share accepted):** `gres/shard` is soft — a co-scheduled student can OOM the GPU (mitigated today by 8 shards + `MaxJobsPerUser=1`). A true per-job cap needs MPS + `CUDA_MPS_PINNED_DEVICE_MEM_LIMIT`, but the MPS binaries (`nvidia-cuda-mps-control`/`-server`) are **absent on both host and container**. Options to get them, none free:
  - **(a) host CUDA-toolkit install** — ❌ rejected: fights the `apt-mark hold` on the 48 nvidia/cuda pkgs protecting the 550 driver pin.
  - **(b) rebuild `base.sif` + per-job in-container MPS** (unique pipe dir in `/scratch`, `CUDA_MPS_PINNED_DEVICE_MEM_LIMIT=0=6G`) — viable, ~40 min, but relies on concurrent per-user MPS servers (Turing supports it; needs careful testing).
  - **(c) drop the two MPS binaries on host from a CUDA runfile** (no apt → pin-safe) + one host MPS server in Default mode + per-job 6G env — cleanest runtime, but unsupported manual binary placement.
  Revisit only if real contention appears; **(b)** or **(c)** are the paths.
- **udev device-node hardening:** `/dev/nvidia*` are world-`rw`, but `ConstrainDevices=yes` already blocks any no-GRES access and students have no non-SLURM shell, so this is near-zero marginal benefit — deferred. If done, must add all GPU-using accounts to a `gpu-users` group or it breaks their jobs (DAC + cgroup both apply).
- **srun --pty gap** (from Phase 03): interactive student `srun` is not containerized — GPU is still cgroup-gated, but fs/net isolation isn't applied. Phase 06 to probe/close.
