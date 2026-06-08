# 🖥️ Dell R730 — ML Node (#1)
**Tags:** #compute #dell #r730 #cuda #ml  
**Related:** [[Compute/Dell R730 - General Node]] · [[Infrastructure/Proxmox Cluster]] · [[Power Distribution]] · [[00 - Homelab MOC]]

---

## Hardware Specs

| Component | Spec |
|---|---|
| Model | Dell PowerEdge R730 |
| Form Factor | 2U |
| Rack Position | U18–U20 |
| **CPU** | 2× Intel Xeon E5-2690 v4 |
| CPU Cores | 28c / 56t total |
| CPU Base Clock | 2.6 GHz |
| **RAM** | 384 GB ECC DDR4 |
| **GPU** | NVIDIA Quadro RTX 6000 24GB GDDR6 ECC |
| Storage | TBD (see [[Infrastructure/Storage]]) |
| NICs | 4× 1G onboard |
| Remote Mgmt | iDRAC 8 Enterprise |
| iDRAC IP | 10.0.10.10 (VLAN 10 MGMT) |
| Depth | ~28" — **rear panel removed** from NetFRAME CS9000 |

---

## Purpose

> This node is **Fernanda's dedicated ML/CUDA workstation** — priority resources for AI/ML research at Fermi National Accelerator Laboratory.

Primary workloads:
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
> RTX 6000 under full load = ~250W. Combined with dual Xeons under load, this node may draw 400–500W+. Ensure [[Power Distribution]] UPS B (Middle Atlantic UPS-2200R) has headroom. Monitor via iDRAC.

---

## CUDA Environment Setup

```bash
# Verify GPU detected
nvidia-smi

# Check CUDA version
nvcc --version

# Python environment (conda recommended)
conda create -n ml python=3.11
conda activate ml
conda install pytorch torchvision torchaudio pytorch-cuda=12.1 -c pytorch -c nvidia

# Test CUDA
python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

---

## Proxmox Config

- OS: Proxmox VE (bare metal, standalone or clustered)
- GPU passthrough via VFIO/IOMMU (PCIe passthrough to VM)
- Primary VM: Ubuntu 22.04 LTS (Fernanda's ML env)

```bash
# Enable IOMMU in GRUB (Intel)
# Edit /etc/default/grub:
GRUB_CMDLINE_LINUX_DEFAULT="quiet intel_iommu=on iommu=pt"

# Find GPU PCI ID
lspci -nn | grep NVIDIA

# vfio bind
echo "options vfio-pci ids=10de:XXXX" > /etc/modprobe.d/vfio.conf
```

See [[Infrastructure/Proxmox Cluster]] for full GPU passthrough procedure.

---

## iDRAC Access

```bash
# Web UI
https://10.0.10.10

# Racadm CLI (from network)
racadm -r 10.0.10.10 -u root -p <pass> getsysinfo

# Power control
racadm -r 10.0.10.10 -u root -p <pass> serveraction powercycle
```

---

## Thermal Notes

- R730 fans ramp hard under GPU load — plan for noise
- Consider custom fan curve via iDRAC: `racadm set System.ThermalSettings.FanSpeedHighOffsetVal`
- Ambient inlet temp target: < 25°C

---

## Related
- [[Compute/Dell R730 - General Node]] — The other R730
- [[Power Distribution]] — UPS B bus, load monitoring
- [[Infrastructure/Proxmox Cluster]] — GPU passthrough config
