# 🖥️ Dell R730 — Jarvis (ML Node)
**Tags:** #compute #dell #r730 #cuda #ml
**Related:** [[Compute/Dell R730 - General Node]] · [[Infrastructure/Proxmox Cluster]] · [[Power Distribution]] · [[00 - Homelab MOC]]

---

## Status: ⏸️ Pending — iDRAC accessible, BIOS/firmware update needed

- iDRAC SSH confirmed reachable at **192.168.10.21**
- iDRAC/LC needs firmware update before BIOS can be flashed (see procedure below)
- Not yet installed as a Proxmox cluster node

---

## Hardware Specs

| Component | Spec |
|---|---|
| Model | Dell PowerEdge R730 |
| Hostname (planned) | Jarvis |
| Form Factor | 2U |
| Rack Position | U18–U20 |
| **CPU** | 2× Intel Xeon E5-2690 v4 |
| CPU Cores | 28c / 56t total |
| CPU Base Clock | 2.6 GHz |
| **RAM** | 384 GB ECC DDR4 |
| **GPU** | NVIDIA Quadro RTX 6000 24GB GDDR6 ECC |
| Storage | TBD (see [[Infrastructure/Storage]]) |
| NICs | 4× 1G onboard |
| Remote Mgmt | iDRAC 8 |
| **iDRAC IP (current)** | **192.168.10.21** |
| iDRAC MAC | 18:66:da:97:0f:8e |
| Depth | ~28" — **rear panel removed** from NetFRAME CS9000 |

> [!NOTE] iDRAC IP was originally static 10.10.198.38. Changed via front panel to 192.168.10.21 to match homelab subnet.

---

## Purpose

Primary workloads (once online):
- CUDA compute jobs (PyTorch, TensorFlow, JAX)
- Large model training / fine-tuning
- Data pipeline processing
- Remote Jupyter / JupyterHub sessions

---

## GPU — Quadro RTX 6000 Detail

| Field | Value |
|---|---|
| VRAM | 24 GB GDDR6 ECC |
| CUDA Cores | 4608 |
| Tensor Cores | 576 (2nd gen) |
| TDP | ~250W |
| ECC | Yes — critical for HPC |
| Driver Target | Latest stable NVIDIA + CUDA 12.x |
| Form Factor | Dual-slot, full-height |

> [!WARNING] Power Draw
> RTX 6000 under full load = ~250W. Combined with dual Xeons, this node may draw 400–500W+. Runs on UPS B (Middle Atlantic UPS-2200R). See [[Power Distribution]].

---

## iDRAC / Firmware Update Procedure

iDRAC 8 must be updated to version **2.86** before BIOS can be flashed. Use legacy TFTP method (no Enterprise license required):

```bash
# Step 1: Update iDRAC/LC to 2.86 via TFTP fwupdate (no Enterprise license needed)
# Download firmimg.d7 from Dell support
racadm -r 192.168.10.21 -u root -p <pass> fwupdate -g -u -a <tftp-server-ip> -d firmimg.d7

# Step 2: Wait for iDRAC reboot (~5–10 min), then verify
racadm -r 192.168.10.21 -u root -p <pass> getidracinfo

# Step 3: Flash BIOS via iDRAC 2.86 web UI
# https://192.168.10.21 → Maintenance → System Update → upload .exe BIOS file
# (No Enterprise license required for web UI upload)
```

> [!WARNING] CPU Stepping
> Mismatched CPU S-spec steppings cause a **silent QPI hang with no error logged** — system appears to POST but hangs. Verify both CPUs have matching S-spec codes before installing. This is the current suspected issue if BIOS update doesn't resolve POST.

---

## CUDA Environment Setup (post-install)

```bash
# Verify GPU detected
nvidia-smi

# Python environment (conda recommended)
conda create -n ml python=3.11
conda activate ml
conda install pytorch torchvision torchaudio pytorch-cuda=12.1 -c pytorch -c nvidia

# Test CUDA
python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

---

## Proxmox Config (planned)

- OS: Proxmox VE (will join existing cluster)
- GPU passthrough via VFIO/IOMMU

```bash
# /etc/default/grub
GRUB_CMDLINE_LINUX_DEFAULT="quiet intel_iommu=on iommu=pt"

# /etc/modules
vfio
vfio_iommu_type1
vfio_pci
vfio_virqfd

lspci -nn | grep NVIDIA
# /etc/modprobe.d/vfio.conf
options vfio-pci ids=<vendor:device>

update-initramfs -u && reboot
```

---

## iDRAC Access

```bash
# Web UI (once firmware updated)
https://192.168.10.21

# CLI
racadm -r 192.168.10.21 -u root -p <pass> getsysinfo
racadm -r 192.168.10.21 -u root -p <pass> serveraction powercycle
```

---

## Thermal Notes

- R730 fans ramp hard under GPU load
- Custom fan curve via iDRAC: `racadm set System.ThermalSettings.FanSpeedHighOffsetVal`
- Ambient inlet temp target: < 25°C
- Rear panel of CS9000 removed — ensure wall clearance for airflow

---

## Related
- [[Compute/Dell R730 - General Node]] — quarkylab (iDRAC: 192.168.10.20)
- [[Power Distribution]] — UPS B bus
- [[Infrastructure/Proxmox Cluster]] — GPU passthrough config
