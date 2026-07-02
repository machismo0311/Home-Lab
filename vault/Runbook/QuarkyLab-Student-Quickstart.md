# 🎓 QuarkyLab GPU Cluster — Student Quickstart
**Tags:** #guide #quickstart #quarkylab #slurm #gpu #students
**Related:** [[Runbook/QuarkyLab-Phase04-GPU-Sharing-2026-07-02]] · [[Infrastructure/QuarkyLab Storage]] · [[Compute/Dell R730 - ML Node]]

> This is the student-facing guide. A clean copy (no Obsidian frontmatter) lives on the box at **`/data/shared/QUICKSTART.md`** — students read it there.

---

Welcome to the QuarkyLab GPU cluster. You share **one NVIDIA RTX 8000 (48 GB)** with other students via the SLURM scheduler. This guide is everything you need to run GPU jobs.

## 1. Log in
```bash
ssh studentNN@192.168.10.179     # use the SSH key you were issued; password login is off
```
You land on the login node. **Don't run heavy GPU code here directly** — submit it to SLURM (below).

## 2. Your storage
| Path | What | Notes |
|---|---|---|
| `~` (your home) | your code + results | 100 GB quota, **backed up nightly** |
| `/scratch` | fast temp space (inside jobs) | **disposable, NOT backed up** — use for checkpoints/temp |
| `/data/shared` | shared datasets | **read-only** |

## 3. Run a GPU job
Write a job script, then `sbatch` it. Your job automatically runs in a container with PyTorch/TensorFlow ready and a GPU slice attached.

`train.sh`:
```bash
#!/bin/bash
#SBATCH -J myjob            # job name
#SBATCH -t 01:00:00         # time limit HH:MM:SS (max 2h)
#SBATCH -o myjob-%j.out     # output file (%j = job id)

source /opt/conda/etc/profile.d/conda.sh
conda activate ml
python train.py
```
Submit it:
```bash
sbatch train.sh
```

## 4. What you get automatically
- **6 GB of GPU memory** (a hard limit — see §7 for more)
- The **`ml`** conda environment: Python 3.11, PyTorch 2.5 (CUDA), TensorFlow 2.21, NumPy/pandas/scikit-learn/SciPy, HuggingFace transformers/datasets, and more
- 48 GB RAM + CPU cores
- A private, isolated container: your home + `/scratch` + `/data/shared` only

## 5. Check & manage your jobs
```bash
squeue --me            # your running/queued jobs
sacct                  # your job history
scancel <jobid>        # cancel a job
cat myjob-<jobid>.out  # see output
```

## 6. Limits & rules
| Limit | Value |
|---|---|
| GPU memory | **6 GB** per job (hard cap) |
| Running jobs | 1 at a time (up to 3 more queued) |
| Max job time | 2 hours |
| Internet inside jobs | none |
| Whole GPU | not available to students (researchers only) |

## 7. Need more GPU memory?
Request more shards — each shard = 6 GB:
```bash
#SBATCH --gres=shard:2      # 12 GB
```
You can't request the whole card; that's reserved for researchers.

## 8. Common gotchas
- **No internet in jobs** — you can't `pip install` at runtime. The `ml` env already has the common packages; need something else? Ask the admin to add it to the image.
- **CUDA out of memory?** You have 6 GB. Reduce batch size / model size, or request more shards (§7).
- **Use `/scratch` for temp files & checkpoints** — it's fast and doesn't count against your home quota.
- **Your job may be requeued** if a researcher needs the whole GPU — **save checkpoints** so you can resume.
- **2-hour limit** — checkpoint long training runs and resubmit.

## 9. Quick GPU check
Drop this in a job to confirm your GPU + cap:
```python
import torch
print("GPU:", torch.cuda.get_device_name(0))
print("CUDA available:", torch.cuda.is_available())
```

---
*Questions or need a package added? Contact the cluster admin.*
