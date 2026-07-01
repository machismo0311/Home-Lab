# SLURM — QuarkyLab GPU scheduling

Protects Fernanda's DUNE research workload from ~15 physics students/
semester sharing the same GPU. Config lives in this folder:
`slurm.conf`, `gres.conf`, `cgroup.conf`.

## Design

One physical node (QuarkyLab), two logical partitions:

| Partition | Who | Wall-time | Priority | Behavior |
|---|---|---|---|---|
| `research` | Fernanda (`fernanda` group) | unlimited | high (tier 100) | Never queued behind students; can preempt |
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
sacctmgr add account research Description="Fernanda DUNE research"
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
- **Planned (RKE2 + NVIDIA GPU Operator):** listed in `README.md` under
  "Planned / In Progress" — this is for containerized workloads (e.g. a
  packaged version of the DUNE agent, or services that need to scale
  across nodes) that don't fit SLURM's batch-job model.
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

  When RKE2 + the GPU Operator eventually go in, the GPU Operator ships
  its own DCGM Exporter as a DaemonSet — at that point retire the
  standalone container above and let the operator manage it, since running
  both simultaneously will double-count metrics and can fight over device
  plugin registration.

**Sequencing:** don't stand up RKE2 GPU scheduling on QuarkyLab while SLURM
is actively managing student jobs on the same card — both will try to
claim exclusive access to the device and one will lose jobs silently. Keep
them on separate hardware, or run RKE2 without GPU workloads until the
RTX 8000 swap gives QuarkyLab a second card to split between them.
