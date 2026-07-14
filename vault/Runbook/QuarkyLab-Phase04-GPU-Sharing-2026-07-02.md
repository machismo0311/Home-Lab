# 🎛️ QuarkyLab Phase 04 - GPU Sharing (RTX 8000)
**Tags:** #runbook #quarkylab #slurm #gpu #cuda #ml
**Related:** [[Compute/Dell R730 - ML Node]] · [[Infrastructure/QuarkyLab Storage]] · [[Infrastructure/Proxmox Cluster]] · [[00 - Homelab MOC]]

---

## Status: ✅ DONE & VALIDATED - 2026-07-02 maintenance window

Turns on GPU access for the multi-tenant student SLURM environment: students share the single **Quadro RTX 8000 (48 GB)** via `gres/shard` with a **hard per-job VRAM cap** (Phase 04b), researchers/the researcher get the whole card, and the researcher is guaranteed priority via preemption. No driver/kernel changes (pin on `6.14.11-9-pve` / NVIDIA `550.163.01` untouched).

> [!NOTE] Sharing = shard (scheduling) + per-job MPS (hard VRAM cap)
> RTX 8000 is Turing → **no MIG**. `gres/shard` is the SLURM scheduling primitive (8 shards, keeps the card in **Default** compute mode so the researcher stays native). Hard VRAM caps come from **per-job CUDA MPS run inside each student job's container** (Phase 04b) - NOT SLURM `gres/mps` (which would force `EXCLUSIVE_PROCESS` and break the researcher) and NOT a host MPS daemon (cross-cgroup IPC fails with error 205).

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
| PartitionName student | added `PriorityTier=1`, `DefMemPerNode=48000`, `MaxMemPerNode=96000` |

> [!IMPORTANT] DefMemPerNode is required for GPU concurrency
> `DefMemPerNode` was `UNLIMITED`, so the first student job grabbed all 500 GB RAM and no second job could co-schedule (`PENDING (Resources)`) - defeating sharing. Bounding it to 48 G lets up to ~8 students run at once (8×48 G = 384 G, headroom for the researcher + system). This is a memory-scheduling fix, unrelated to MPS.

`cgroup.conf` unchanged - **`ConstrainDevices=yes` was already set**, and it is the real enforcement gate (a job with no GPU GRES is denied `/dev/nvidia*` in its cgroup).

### `/etc/slurm/job_submit.lua` (student jobs)
- **Auto-injects `--gres=shard:1`** (`tres_per_node=gres/shard:1`) when a student requests no GRES.
- **Rejects** student whole-GPU requests: *"Students may not request whole GPUs. Use --gres=shard:N."*
- Wraps the job in `apptainer exec --nv` with **per-job MPS** and the VRAM cap (see Phase 04b).

Wrapper (final): `apptainer exec --nv --no-home --no-mount tmp --net --network=none --env TMPDIR=/scratch --env MPS_MEM_GB=<shards*6> -B $HOME -B <scratch>:/scratch -B <scratch>:/tmp -B /usr/bin/nvidia-cuda-mps-control -B /usr/sbin/nvidia-cuda-mps-server -B /opt/mps/mps-exec.sh -B /data/shared:ro --pwd $HOME base.sif /opt/mps/mps-exec.sh <<heredoc`.

> [!WARNING] Not `--contain`
> `--contain` gives the container a **private `/dev/shm`** and *silently skips* `-B /dev/shm`, which severs the MPS shared-memory channel (jobs OOM at 0 GiB). Isolation is instead achieved with `--no-home --no-mount tmp` + explicit binds - **verified equivalent** (other homes/students hidden, `/data/shared` RO, network blocked).

Backups: `/etc/slurm.bak.<ts>/`, `job_submit.lua.bak.<ts>`.

### Phase 04b - per-job MPS hard VRAM cap (2026-07-02)
- Installed Debian **`nvidia-cuda-mps` 550.163.01-2** - byte-identical version to the pinned `libcuda1`, so it installs against the held driver (dry-run: 0 held pkgs touched); then `apt-mark hold`'d.
- Host `nvidia-mps.service` was created but **disabled** - a *host* MPS daemon fails for jobs with `CUDA_ERROR_MAP_FAILED (205)` because the server (outside the job cgroup) and client (inside it) can't share IPC. Package kept only for the binaries.
- **`/opt/mps/mps-exec.sh`** (755): starts `nvidia-cuda-mps-control -d` with a job-unique pipe dir `/scratch/.mps.$$`, exports `CUDA_MPS_PINNED_DEVICE_MEM_LIMIT=0=${MPS_MEM_GB}G`, sets an EXIT trap to quit MPS + clean the dir, then runs the user script via `/bin/bash -s`. Running MPS **inside** the job's container/cgroup removes the cross-cgroup boundary → the cap works.
- Cap scales: `MPS_MEM_GB = SLURM_SHARDS_ON_NODE × 6`. GPU stays **Default** compute mode → the researcher unaffected.

---

## Validation results (all passed)

| Test | Result |
|---|---|
| `sinfo` GRES | `gpu:rtx8000:1,shard:rtx8000:8` on both partitions ✓ |
| research `--gres=gpu:1` | `CUDA_VISIBLE_DEVICES=0`, RTX 8000 visible ✓ |
| research `--gres=shard:2` | GPU shared, visible ✓ |
| **no GRES** | `No devices found.`, `CVD=[]` - **denied** ✓ |
| student default job (no gres) | auto `gres/shard=1`; in-container `torch.cuda.is_available()=True`, RTX 8000 ✓ |
| student `--gres=gpu:1` | **rejected** at submit ✓ |
| **VRAM hard cap** (04b) | default job OOMs at ~6 GiB; `--gres=shard:2` OOMs at ~12 GiB (scales) ✓ |
| **concurrency** (04b) | 3 students RUNNING at once, each capped, sharing the card (nvidia-smi: 3×~3 GiB + 3×26 MiB MPS servers) ✓ |
| **the researcher native** | research `gpu:1`: 47.8 GB visible, allocated 12 GiB uncapped ✓ |
| **preemption** | student shard job RUNNING → fernanda `gpu:1` submitted → student REQUEUED, fernanda RUNNING ✓ |

---

## How it works (operations)

- **Students** (`student` partition, default): just `sbatch job.sh`. They automatically get one shard with a **hard 6 GB VRAM cap**, run inside the container with `--nv`, isolated (no net, own home, `/data/shared` RO, `/scratch`, 48 GB RAM). Ask for more with `--gres=shard:N` → cap scales to `N×6 GB`. `studentqos` caps them at 1 running job → up to 8 students share the 8 shards concurrently.
- **Researchers / the researcher** (`research` partition): `--gres=gpu:1` for the whole card (bypass the container wrapper). `--gres=shard:N` also available.
- **the researcher guarantee:** research `PriorityTier=100` > student `PriorityTier=1` with `preempt/partition_prio` + `REQUEUE`. When she submits `gpu:1`, SLURM requeues student shard jobs to free the card; they restart automatically when she finishes. No static reservation needed (the old Phase-02 "permanent reservation" item is satisfied this way).

> [!WARNING] REQUEUE, not SUSPEND
> GPU preemption uses **REQUEUE** deliberately - a SUSPENDed CUDA process keeps its VRAM, so it wouldn't actually free the card. Requeue kills+requeues the student job, releasing the GPU.

---

## Rollback
```bash
# SLURM config (GRES, preemption, wrapper, partition mem) - restores everything
latest=$(ls -d /etc/slurm.bak.* | tail -1)
rm -f /etc/slurm/gres.conf
cp -a "$latest"/. /etc/slurm/
systemctl restart slurmctld slurmd
# 04b MPS bits (only if fully backing out hard caps)
apt-mark unhold nvidia-cuda-mps && apt-get remove -y nvidia-cuda-mps
rm -rf /opt/mps /etc/systemd/system/nvidia-mps.service
```

---

## Follow-ups (optional)
- **Phase 04b - hard VRAM caps: ✅ DONE** (per-job in-container MPS, documented above). Note: MPS binaries turned out to be in Debian's `nvidia-cuda-mps` at the exact pinned driver version, so no CUDA-toolkit install or container rebuild was needed.
- **udev device-node hardening:** `/dev/nvidia*` are world-`rw`, but `ConstrainDevices=yes` already blocks any no-GRES access and students have no non-SLURM shell, so this is near-zero marginal benefit - deferred. If done, must add all GPU-using accounts to a `gpu-users` group or it breaks their jobs (DAC + cgroup both apply).
- **srun --pty gap: ✅ CLOSED (2026-07-02)** - students are **batch-only**. `job_submit.lua` rejects any student job with no batch script (interactive `srun`/`salloc`) with a message pointing to the quickstart, since interactive jobs would run un-containerized and un-capped. Researchers keep interactive on the `research` partition. Verified: student `srun`/`salloc` rejected, `sbatch` still works.
- **Scratch auto-purge (2026-07-02):** `scratch-purge.timer` (daily 04:30) runs `/usr/local/sbin/scratch-purge.sh` → deletes `/workspace/scratch/*/` files >14 days old. `workspace/scratch` also capped at 2 TB + 200 GB/user.
