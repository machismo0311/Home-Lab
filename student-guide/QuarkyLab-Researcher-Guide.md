# QuarkyLab — Researcher Guide

Access + the commands to actually do your work. Researchers get a **normal interactive shell** — no SLURM required. Assumes you're comfortable at the CLI.

Admin / key requests / help: **contact Kyle on our shared Discord channel**

---

## 1. Access (one-time)

1. Generate a key and send Kyle the **public** half on Discord; he adds it to your account (we'll tell you your username — e.g. `cephandrius`):
   ```bash
   ssh-keygen -t ed25519 -C "you@lab"
   cat ~/.ssh/id_ed25519.pub          # send this line to Kyle on Discord
   ```
2. Install `cloudflared`: `brew install cloudflared` (mac) · `winget install --id Cloudflare.cloudflared` (win) · package/binary from `https://github.com/cloudflare/cloudflared/releases/latest` (Linux).
3. `~/.ssh/config`:
   ```
   Host quarkylab
       HostName quarkylab.kylemason.org
       ProxyCommand cloudflared access ssh --hostname %h
       IdentityFile ~/.ssh/id_ed25519
   ```
4. Connect (SSH-key auth):
   ```bash
   ssh <your-username>@quarkylab
   ```

No VPN, no inbound ports, nothing to leave running — `cloudflared` dials out through the tunnel on demand. (An email sign-in gate may be added later; if so, the first connection will also pop a one-time browser login.) Questions? Ask on Discord.

---

## 2. The machine

- 1× **Quadro RTX 8000, 48 GB** · driver 550.163.01 · CUDA 12.1 stack.
- `nvidia-smi` — GPU status / who's on it. You share this **one physical GPU** with students' SLURM jobs and the researcher, so glance before grabbing lots of VRAM.

## 3. GPU + ML environment (Apptainer)

The curated stack is an Apptainer image — `ml` conda env: **Python 3.11, torch 2.5.1+cu121, TF 2.21**, numpy/pandas/scipy/scikit-learn/HuggingFace. Image at `/data/containers/base.sif` (fast local copy: `/workspace/containers/base.sif`).

```bash
# run a script on the GPU
apptainer exec --nv /data/containers/base.sif python train.py

# interactive shell inside the container
apptainer shell --nv /data/containers/base.sif

# quick sanity check
apptainer exec --nv /data/containers/base.sif \
  python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
# -> True Quadro RTX 8000
```

- `python` inside the image is already the `ml` env (`/opt/conda/envs/ml`).
- `--nv` is what exposes the GPU — omit it and CUDA is invisible.
- Your **home** and the **current directory** are auto-mounted. Bind extra paths with `-B /host/path:/container/path`.

## 4. Your own environment (optional)

No sudo, but your home is yours. For a custom stack, drop Miniforge in your home:
```bash
curl -L -o ~/miniforge.sh https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
bash ~/miniforge.sh -b -p ~/miniforge3
~/miniforge3/bin/conda create -n myenv python=3.11 pytorch-cuda=12.1 ...
```
The NVIDIA driver is already on the host; install a CUDA-matched torch/TF in your env — or just use the container.

## 5. Storage

| Path | Use | Notes |
|---|---|---|
| `~` = `/workspace/researchers/<your-username>` | code + results | **150 GB** quota, backed up nightly to PBS |
| `/workspace/scratch/<your-username>` | fast scratch | **not** backed up; files >14 days auto-purged |
| `/data/shared` | shared datasets / docs | **read-only** |
| `/data` | bulk (Randy NFS, ~23 TB behind it) | ask Kyle for a writable project dir if you need one |

## 6. Moving data (routes through the tunnel automatically)

`scp`/`rsync` use your SSH config, so they go through Cloudflare with no extra flags:
```bash
scp bigfile.tar quarkylab:~/                 # upload
scp quarkylab:~/results.csv .                # download
rsync -avP ./dataset/ quarkylab:~/dataset/   # sync a folder
```

## 7. Long-running work — use tmux

SSH sessions can drop (laptop sleep, network blips); a detached session keeps the job alive:
```bash
tmux new -s run        # start; launch your training inside
# Ctrl-b then d to detach — close the laptop, come back later:
ssh quarkylab
tmux attach -t run
```
(`screen` works too; `nohup cmd &` for fire-and-forget.)

## 8. Etiquette

- One physical GPU, shared. Running **directly** (outside SLURM) you are **not** VRAM-capped — check `nvidia-smi` first and don't OOM others.
- For multi-day campaigns, there's a `research` SLURM partition (interactive allowed, priority over students) if you'd rather queue/preempt-share — optional, coordinate with Kyle.
