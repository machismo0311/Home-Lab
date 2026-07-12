# SLURM — QuarkyLab GPU scheduling

> **Status: experimental / not deployed.** These configs capture a GPU
> job-scheduling design for QuarkyLab; the lab currently runs GPU workloads
> directly (Ollama on Jarvis, ad-hoc ML on QuarkyLab) rather than under SLURM.
> Kept as a reference design. GPU type reflects QuarkyLab's current RTX 8000.

Protects the resident researcher's DUNE workload from ~15 physics students/
semester sharing the same GPU. Config lives in this folder:
`slurm.conf`, `gres.conf`, `cgroup.conf`.

## Design

One physical node (QuarkyLab), two logical partitions:

| Partition | Who | Wall-time | Priority | Behavior |
|---|---|---|---|---|
| `research` | the researcher (`fernanda` group) | unlimited | high (tier 100) | Never queued behind students; can preempt |
| `students` | `students` group | 4h | low (tier 10) | Requeued if a research job needs the GPU |

`PreemptType=preempt/partition_prio` + `PreemptMode=REQUEUE` is the actual
protection mechanism — a queued research job doesn't wait behind student
jobs, it requeues them. Partition priority alone only affects scheduling
order for *new* jobs, not running ones.

## Deploy

```bash
# On QuarkyLab, after installing slurm-wlm and munge:
sudo cp slurm.conf gres.conf cgroup.conf /etc/slurm/
sudo systemctl enable --now munge slurmctld slurmd

# Create the QoS referenced by the students partition
sacctmgr add qos student set MaxWall=04:00:00 MaxTRESPerUser=gres/gpu=1

# Create the account/group associations
sacctmgr add account research Description="DUNE research"
sacctmgr add account students Description="Semester coursework"
sacctmgr add user fernanda Account=research
# Add each student as they onboard:
sacctmgr add user <netid> Account=students QOS=student
```

> **What this does:** `sacctmgr` is SLURM's accounting/association tool —
> it's what actually ties a Linux user to a partition and a QoS. The
> `MaxTRESPerUser=gres/gpu=1` line is the real job limit: it caps any
> single student to one GPU allocation at a time, so one person can't
> block the other fourteen. Without an association, a user technically
> in the `students` group still can't submit jobs — SLURM requires both.

## Onboarding students each semester

```bash
for netid in $(cat roster.txt); do
  sudo useradd -M -s /bin/bash "$netid"
  sacctmgr -i add user "$netid" Account=students QOS=student
done
```

Matches the existing Apptainer-based isolation plan (image build checklist
already in the vault) — SLURM handles who gets the GPU and for how long,
Apptainer handles what they can see on the filesystem once they have it.

## DCGM / RKE2 integration strategy

This was the other piece Sonny flagged as undocumented. The short version:
SLURM and Kubernetes are solving different problems here, and NVIDIA DCGM
is the piece that lets both coexist without conflicting.

- **Now (bare metal + SLURM):** SLURM schedules batch jobs directly onto
  QuarkyLab's GPU via `cgroup.conf`'s `ConstrainDevices`. No container
  runtime involved.
- **RKE2 deployed CPU-only (Phases 1-7, 2026-07-10/11); NVIDIA GPU Operator still deferred:**
  RKE2 is live (HA control plane, Cilium, MetalLB — see
  `vault/Runbook/RKE2-Phase1-HA-ControlPlane-2026-07-10.md`) but with **no GPU
  scheduling**. The GPU Operator is for containerized workloads (e.g. a
  packaged version of the DUNE agent, or services that need to scale
  across nodes) that don't fit SLURM's batch-job model — deferred until a card frees.
- **The bridge — DCGM Exporter:** rather than picking one scheduler
  permanently, DCGM Exporter runs independently of both and exposes GPU
  telemetry (utilization, memory, temperature, ECC errors) as Prometheus
  metrics — feeding the Prometheus/Grafana/Loki stack that's already live
  on all 8 nodes. Whichever scheduler is actually driving the GPU at a
  given moment, the same dashboard keeps working:

  ```bash
  # DCGM Exporter as a standalone container, independent of SLURM or RKE2
  docker run -d --gpus all --rm -p 9400:9400 \
    nvcr.io/nvidia/k8s/dgcm-exporter:latest
  ```

  When the GPU Operator eventually goes in (RKE2 itself is already deployed,
  CPU-only), it ships its own DCGM Exporter as a DaemonSet — at that point retire the
  standalone container above and let the operator manage it, since running
  both simultaneously will double-count metrics and can fight over device
  plugin registration.

**Sequencing:** don't stand up RKE2 GPU scheduling on QuarkyLab while SLURM
is actively managing student jobs on the same card — both will try to
claim exclusive access to the device and one will lose jobs silently.
QuarkyLab has a **single** RTX 8000 48GB — the 2026-07-01 swap replaced the
RTX 6000 one-for-one (more VRAM, still one card; it did **not** add a second
GPU). So this stays an either/or: **RKE2 is deployed CPU-only and its GPU
scheduling remains deferred** while SLURM / ad-hoc ML own the card. Split
between the two schedulers only if QuarkyLab ever gets a second GPU, or move
the containerized workloads to separate hardware.
