# 🔬 QuarkyLab DUNE ML Tuning - Plan (2026-07-25)
**Tags:** #runbook #quarkylab #dune #ml #gpu #cuda #cvmfs #nvme #plan
**Related:** [[Compute/Dell R730 - ML Node]] · [[Infrastructure/QuarkyLab Storage]] · [[Runbook/QuarkyLab-Phase04-GPU-Sharing-2026-07-02]] · [[Runbook/QuarkyLab-Storage-Expansion-2026-07-13]] · [[00 - Homelab MOC]]

---

## Status: 📋 PLAN - not yet applied

Tunes QuarkyLab (`.10.179`, R730, RTX 8000 48GB) for the specific ML workload it exists to serve: **Fernanda Psihas's DUNE reconstruction research**. Nothing here touches the pinned driver/kernel stack or the existing SLURM tenancy. All steps are additive and staged as operator apply-blocks + read-only verification (per live-change handoff policy).

> [!NOTE] Who this node serves, and why the tuning is what it is
> QuarkyLab runs a physicist's **production DUNE ML workload** (README: "dedicated research node for DUNE"). Fernanda is `fernanda@quarkylab`, "the researcher" with `research`-partition preemption priority. Her work is deep-learning reconstruction on liquid-argon TPC (LArTPC) data. The tuning below follows directly from three facts about that workload:
> 1. The production ML stack (SPINE / MinkowskiEngine) **pins CUDA 11.8 and will not build on CUDA 12** - but our host is driver 550 / CUDA 12.x. Resolved by **containers**, not host builds.
> 2. It is **I/O-random-read-bound** on sparse HDF5/larcv tensors, not FLOP-bound. Resolved by **NVMe scratch**.
> 3. The 48GB RTX 8000 is **correctly sized** (SPINE GNN stages want 20-25GB); RAM/cores are already ideal. So the GPU is not the thing to change.

---

## Background: what the workload actually is

Fernanda pioneered CNN-based neutrino event reconstruction (NOvA **CVN**). Her modern DUNE work is two GPU-heavy families:

| Technique | Library / framework | Why | VRAM (train) |
|---|---|---|---|
| **Sparse conv nets** (SPINE full chain) | PyTorch + **MinkowskiEngine** / SubmanifoldSparseConvNet, **CUDA 11.8** | LArTPC events are ~99.99% empty; dense CNNs waste compute (sparse = ~300x less memory, ~30x faster) | ~20-25GB for full chain / GNN stages |
| **Graph neural nets** (NuGraph2) | PyTorch + **PyTorch Geometric** + Lightning, HDF5 via `pynuml` | Hit-level semantic segmentation on irregular detector geometry | ~6-12GB |
| **CVN** (legacy / reproduction) | Caffe (dead) or ported TF/PyTorch, GoogLeNet-style 2D CNN | Her original whole-event flavor classifier | small (<6GB) |
| **Uncertainty quantification** | Deep ensembles (train N models) | Precision measurements need calibrated AI uncertainties | N x a single-model run |

Software delivery is DUNE-standard: **`dunesw`/LArSoft** (C++, art, ROOT) over **CVMFS**, still requiring an **SL7 Apptainer container** on the AL9/EL9-era host during the ongoing UPS/SL7 -> Spack/AL9 migration. Training happens outside `art` on extracted larcv/HDF5; frozen models are then run inside LArSoft.

---

## Tuning actions (ranked by payoff)

### 1. NVMe scratch - the single biggest win

**Problem.** The `workspace` pool is 6-wide raidz1 on **spinning** SATA/SAS (see [[Runbook/QuarkyLab-Storage-Expansion-2026-07-13]]). DUNE ML training is many small random reads of sparse tensors; spinning raidz1 is the worst case and will starve the GPU (sparse decompression + graph construction is CPU-side and can't hide slow reads).

**Plan.** Add a dedicated **NVMe `/scratch`** to stage training datasets (hundreds of GB to low-TB HDF5/larcv). Scratch data is reproducible/re-stageable, so **no redundancy needed** - single drive, plain XFS, kept out of the ZFS pool (avoids ARC double-caching).

- Hardware: one U.2 NVMe on a PCIe adapter, or an M.2 NVMe on a single-slot PCIe AIC (no bifurcation needed for one drive), in a spare R730 PCIe slot. TB-scale, high-endurance preferred.
- Filesystem: `mkfs.xfs`, mount `/scratch`, `chmod 1777` (sticky, shared like `/tmp`).
- Wire into SLURM: the Phase-04 job wrapper already binds `-B <scratch>:/scratch` and sets `TMPDIR=/scratch`. Repoint that scratch path at the new NVMe mount so both student and researcher jobs land datasets on fast storage.

> [!IMPORTANT] This moves the GPU-utilization needle more than any GPU-side change. Verify with `nvidia-smi dmon` before/after: if GPU util is bursty/low while a training job runs, the loader is starved and scratch is the fix.

### 2. CVMFS mount (DUNE + LArSoft software delivery)

Mount the read-only CVMFS repos so LArSoft/`dunesw` and the DUNE containers resolve software the standard way, with an **SSD-backed local cache** to avoid network stalls.

```bash
# apply-block (operator, on QuarkyLab)
apt-get install -y cvmfs
cat >/etc/cvmfs/default.local <<'EOF'
CVMFS_REPOSITORIES=dune.opensciencegrid.org,larsoft.opensciencegrid.org,config-osg.opensciencegrid.org
CVMFS_HTTP_PROXY=DIRECT
CVMFS_CACHE_BASE=/var/lib/cvmfs        # put on SSD; size below
CVMFS_QUOTA_LIMIT=20000                # 20 GB cache
CVMFS_CLIENT_PROFILE=single
EOF
cvmfs_config setup
systemctl restart autofs
```

> [!NOTE] DNS caveat
> Tailscale overwrites `/etc/resolv.conf` on all nodes (see cluster CLAUDE.md). CVMFS needs working DNS to the CDN/Stratum-1s; keep `--accept-dns=false` and nameserver `192.168.10.177` set, same as the apt workaround.

Read-only verify: `ls /cvmfs/dune.opensciencegrid.org` (triggers automount) then `cvmfs_config probe`.

### 3. Pre-stage the containers (avoid the CUDA 11.8 vs 12 build nightmare)

Apptainer is already installed and in the SLURM wrapper (`apptainer exec --nv`). Build the `.sif` images once so nobody fights native builds:

```bash
# apply-block (operator) - stage under a shared images dir, e.g. /data/shared/sif
# SPINE / MinkowskiEngine full chain (CUDA 11.8 runtime lives INSIDE the image):
apptainer build /data/shared/sif/spine.sif docker://ghcr.io/deeplearnphysics/spine:latest
# DUNE SL7 worker-node container for LArSoft/dunesw (from CVMFS unpacked images):
ls /cvmfs/singularity.opensciencegrid.org/fermilab/   # pick fnal-wn-sl7 / dune dev image
```

> [!WARNING] Do NOT try to compile MinkowskiEngine against host CUDA 12
> It has unfixed Thrust `thrust::device` build failures on CUDA 12 and is effectively unmaintained. Driver 550 is backward-compatible and runs a **CUDA 11.8 runtime inside the container** fine; RTX 8000 `sm_75` is supported by both 11.8 and 12.x. The host toolchain is the constraint, never the driver.

GPU passthrough sanity check (read-only): `apptainer exec --nv /data/shared/sif/spine.sif python -c "import torch; print(torch.cuda.get_device_name(0))"` should print the Quadro RTX 8000.

### 4. Keep the driver/kernel pin exactly as-is

No action - this is a **do-not-touch** reminder. Kernel `6.14.11-9-pve` (GRUB_DEFAULT) + NVIDIA `550.163.01` stay pinned. The research confirms *why* it is safe to never chase host CUDA 11.8: it only ever lives in the container. Do not run kernel upgrades or change GRUB default on QuarkyLab (6.17+ breaks NVIDIA 550).

### 5. Lean into the CPU/RAM already present

512GB RAM and 44c/88t (2x E5-2699 v4) are ideal for this workload; just use them:

- Set PyTorch `DataLoader num_workers` high (e.g. 16-32) to parallelize CPU-side sparse decompression + PyG graph construction (Delaunay/edge building).
- Big RAM caches datasets and holds graph batches; combined with NVMe scratch (#1) the loader should keep the GPU fed.
- If ZFS ARC ever competes with loaders, staging to the non-ZFS NVMe scratch sidesteps it entirely.

---

## Second GPU / ensemble spillover (ties to the R730xd)

The one workload of Fernanda's that genuinely benefits from a **second GPU** is **deep-ensemble uncertainty quantification**: train N independent models, which parallelizes perfectly across cards. Her CVN and NuGraph models (~6-12GB) fit on a **16GB T4**, and a T4 is **Turing `sm_75` - identical arch to the RTX 8000, so her code runs with no recompile**. The full 20-25GB SPINE chain stays on the RTX 8000.

If a GPU is ever added to the [[Runbook/... R730xd]] backup box, make it a **T4**, enroll it in the SLURM `research` partition as a second GPU node, and route ensemble members / hyperparameter sweeps / dev-inference to it. See [[Runbook/QuarkyLab-Phase04-GPU-Sharing-2026-07-02]] for the gres/partition model to extend. (A single job cannot shard across two separate nodes over Ethernet in any worthwhile way - this is whole-small-jobs overflow, not model-parallel.)

---

## Verification checklist (all read-only)

- [ ] `nvidia-smi` reports RTX 8000, 46080 MiB, driver 550.163.01 (unchanged)
- [ ] `/scratch` mounted on NVMe, `df -h /scratch` shows the fast device, sticky bit set
- [ ] `cvmfs_config probe` OK for dune + larsoft repos
- [ ] `apptainer exec --nv spine.sif ...` prints the GPU name and a working `torch.cuda`
- [ ] A test NuGraph2 / small training job shows sustained (not bursty) GPU util with data on `/scratch`
- [ ] SLURM `research` preemption still works; student `gres/shard` cap intact (no regression to Phase 04)

---

## Open questions / uncertainty

- **Which datasets does Fernanda actually train on, and how big?** Sizing NVMe scratch (2TB vs 4TB) and whether a 2-drive stripe is worth it depends on her real corpus. Ask before buying.
- **SL7 -> Spack/AL9 boundary is a moving target.** "What builds under Spack today" shifts month to month; verify against current DUNE `computing-basics` docs at apply time.
- **AMP / mixed precision** on Turing is model-dependent for MinkowskiEngine - treat as a per-network experiment, plan for FP32 baseline.
- **PCIe slot budget on the R730** with the RTX 8000 already installed - confirm a free slot (and lane width) for the NVMe AIC before ordering.

---

## References

- Psihas et al., NOvA CVN - arXiv:1604.01444
- Psihas, *context-enriched* CNN particle ID - arXiv:1906.00713 (Phys. Rev. D 100:073005)
- Psihas et al., *Review on ML for Neutrino Experiments* - arXiv:2008.01242
- Scalable sparse CNNs for LArTPC - arXiv:1903.05663
- NuGraph2 (PyTorch Geometric GNN) - arXiv:2403.11872
- SPINE full chain - github.com/DeepLearnPhysics/spine
- MinkowskiEngine CUDA 12 build failure - NVIDIA/MinkowskiEngine issue #594
- DUNE computing basics (Spack/AL9/Apptainer) - dune.github.io/computing-basics/setup.html
