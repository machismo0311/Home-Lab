# QuarkyLab — Relocate containerd image store to ZFS pool (PLANNED OUTAGE)

**Status:** 📌 PINNED — awaiting a planned maintenance window (notify all QuarkyLab users first).
**Raised:** 2026-07-10 (disk WARN: `/` at 82%).
**Node:** QuarkyLab (`192.168.10.179` mgmt / `192.168.30.179` VLAN30).
**Est. window:** ~15–20 min (mostly the ~60 GB copy). No GPU/driver changes.

---

## Problem

Disk alert: `/dev/mapper/pve-root` (the **94 GB LVM OS root**) is at **82% (73 G used)**.
Root cause: Docker 29.6 uses the **containerd image store**, and containerd's root
`/var/lib/containerd` sits on the 94 GB OS root. The single ML image
`quarkylab-ml:latest` is **63 GB** (`docker system df`: 63.36 GB image, 63.02 GB unique),
so one image nearly fills the OS disk.

Meanwhile the **`workspace` ZFS pool is 9.09 TB with only ~2 TB used** — the big
storage is sitting idle because containers don't live on it.

**This is a placement misconfiguration, not a capacity problem.** A `docker builder
prune` was run 2026-07-10 and reclaimed the build-cache *index* (14.6 GB → 90 MB) but
freed **zero** physical space, because with the containerd image store the build-cache
layers are the same blobs as the live image. The only real fix is to move the store
onto the pool. Deleting the image is NOT an option (it is the live ML env).

## Goal

Move `/var/lib/containerd` onto the `workspace` ZFS pool so the ML image has multiple
TB to grow into. Expected result: `/` drops from ~73 G → ~13 G used (**82% → ~14%**).

---

## Pre-flight (safe to do anytime, no outage)

1. Announce the window to QuarkyLab students/researchers — **no containers may be
   launched during the move.**
2. Confirm nothing is running:
   ```bash
   ssh quarkylab 'sudo docker ps ; squeue'
   ```
   Expect 0 running containers and no container-launching SLURM jobs.
3. Record current state:
   ```bash
   ssh quarkylab 'df -h / ; sudo du -xsh /var/lib/containerd ; sudo docker images'
   ```

## ⚠️ overlayfs-on-ZFS caveat — DECIDE FIRST

containerd uses the **overlayfs snapshotter**. overlayfs on top of a ZFS *dataset*
works on modern kernels but historically needs `xattr=sa` and can be fragile. Two
storage layouts — **pick one before the window**:

- **Option A — ZFS dataset (thin, simplest).** Create `workspace/containerd` mounted
  at `/var/lib/containerd`, set `xattr=sa`. Verify overlayfs works after restart
  (pull/run a small image). Preferred if it passes the smoke test.
- **Option B — zvol + ext4 (guaranteed identical behavior).** Create a zvol, format
  ext4, mount at `/var/lib/containerd`. overlayfs behaves exactly as today. Use this
  if Option A's smoke test fails. Trade-off: fixed-size, not thin.

---

## Procedure — Option A (ZFS dataset)

```bash
ssh quarkylab

# 1. Stop the daemons (order matters: docker first, then containerd)
sudo systemctl stop docker.socket docker.service
sudo systemctl stop containerd

# 2. Move the existing store aside (do NOT delete yet — it is the rollback)
sudo mv /var/lib/containerd /var/lib/containerd.old

# 3. Create a dedicated dataset mounted at the containerd path
sudo zfs create -o mountpoint=/var/lib/containerd -o xattr=sa -o acltype=off workspace/containerd

# 4. Copy the data back onto the pool (preserve everything)
sudo rsync -aHAXP --numeric-ids /var/lib/containerd.old/ /var/lib/containerd/

# 5. Restart
sudo systemctl start containerd
sudo systemctl start docker.service docker.socket

# 6. SMOKE TEST — verify overlayfs snapshotter works on ZFS
sudo docker images                      # quarkylab-ml + nvidia/cuda must list
sudo docker run --rm nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi   # GPU + overlay OK
sudo docker run --rm quarkylab-ml:latest python -c 'import torch; print(torch.cuda.is_available())'

# 7. Confirm the reclaim
df -h /                                  # expect ~14%
sudo zfs list workspace/containerd       # ~60 G now on the pool
```

### Rollback (if smoke test fails)
```bash
sudo systemctl stop docker.socket docker.service containerd
sudo zfs set mountpoint=none workspace/containerd     # (or: zfs destroy workspace/containerd)
sudo rmdir /var/lib/containerd 2>/dev/null || sudo rm -rf /var/lib/containerd
sudo mv /var/lib/containerd.old /var/lib/containerd
sudo systemctl start containerd docker.service docker.socket
```
Then retry with **Option B (zvol + ext4)**:
```bash
sudo zfs create -V 200G workspace/containerd-vol        # size to taste; watch pool free
sudo mkfs.ext4 /dev/zvol/workspace/containerd-vol
# fstab entry so it mounts on boot:
#   /dev/zvol/workspace/containerd-vol  /var/lib/containerd  ext4  defaults,nofail  0 2
sudo mount /var/lib/containerd
sudo rsync -aHAXP --numeric-ids /var/lib/containerd.old/ /var/lib/containerd/
# restart + smoke test as above
```

## Post-flight

1. Once the smoke test passes and the env is confirmed healthy for a day or two:
   ```bash
   sudo rm -rf /var/lib/containerd.old      # reclaims the OS-root space for good
   ```
2. Persist the mount:
   - Option A (dataset): ZFS mounts it automatically — no fstab needed. Confirm
     `zfs get mountpoint workspace/containerd`.
   - Option B (zvol): the `/etc/fstab` line above.
3. Update the alert baseline / NetFRAME expectation for QuarkyLab `/`.

## Notes
- Docker version 29.6.0, containerd v2.2.5. NVIDIA runtime (`nvidia` in
  `/etc/docker/daemon.json`) is unaffected — this is purely a storage move.
- If you later prefer, the same effect is achievable by setting `root =
  "/workspace/containerd"` in `/etc/containerd/config.toml` instead of mounting at the
  default path — but mounting at `/var/lib/containerd` keeps behavior identical and
  survives package upgrades that rewrite the config.
- Related: [[Network-Performance-and-Upgrade-Path-2026-07-09]] (VLAN30/10G context),
  QuarkyLab-Operations.md.
