# 🖥️ Dell R730 — QuarkyLab (ML Node)
**Tags:** #compute #dell #r730 #cuda #ml
**Related:** [[Compute/Dell R730 - General Node]] · [[Infrastructure/Proxmox Cluster]] · [[Power Distribution]] · [[00 - Homelab MOC]]

---

## Status: 🟢 Online — km-cluster node (RTX 6000 ML → RTX 8000 48GB planned)

- **Host IP:** 192.168.10.179
- **iDRAC:** 192.168.10.20 (root/calvin)
- Member of km-cluster (PVE 9.2.3)
- Hosts **Wazuh SIEM VM 104** (192.168.10.184)
- **Scrutiny collector** installed (reports to hub at 192.168.10.183:8080)
- SSH: `ssh quarkylab` (via `fernanda@quarkylab` key, id_ed25519 on Ares)
- **RTX 8000 48GB swap planned** (2026-06-30 GPU plan): swap out the current RTX 6000 for the RTX 8000 (card in hand); the freed RTX 6000 moves to Jarvis. Driver-free swap — same NVIDIA 550.163.01 / kernel 6.14.11-9-pve stack (Turing TU102).

> [!WARNING] Kernel pin
> Kernel **must** stay on `6.14.11-9-pve` — `GRUB_DEFAULT` is pinned; 6.17+ breaks NVIDIA 550. Never run kernel upgrades or change the GRUB default on QuarkyLab. NVIDIA 550.163.01 verified working post-upgrade.

---

## Hardware Specs

| Component | Spec |
|---|---|
| Model | Dell PowerEdge R730 |
| Hostname | QuarkyLab |
| Service Tag | **1S8WR22** |
| Form Factor | 2U |
| Rack Position | U15–U16 |
| **CPU** | 2× Intel Xeon E5-2699 v4 (44c / 88t total) |
| CPU Base Clock | 2.2 GHz |
| **RAM** | 512 GB LRDIMM ECC DDR4 |
| **GPU** | NVIDIA Quadro RTX 6000 24GB GDDR6 ECC (driver 550.163.01) → **RTX 8000 48GB** planned swap |
| NICs | 4× 1G onboard |
| Remote Mgmt | iDRAC 8 (192.168.10.20) |
| Depth | ~28" — **rear panel removed** from NetFRAME CS9000 |

---

## Purpose

- Fernanda's ML workloads / **DUNE agent** (RAG pipeline over the DUNE experiment codebase)
- CUDA compute (PyTorch, TensorFlow, JAX), training / fine-tuning
- Vector store (ChromaDB or Qdrant — TBD)

---

## GPU — Quadro RTX 6000 Detail (→ RTX 8000 planned)

| Field | Value |
|---|---|
| VRAM | 24 GB GDDR6 ECC (48 GB after RTX 8000 swap) |
| CUDA Cores | 4608 |
| Tensor Cores | 576 (2nd gen) |
| TDP | ~250W |
| Driver | NVIDIA 550.163.01 (CUDA 12.x) |

> [!NOTE] Planned RTX 8000 swap
> Per the 2026-06-30 plan, QuarkyLab gets the **RTX 8000 48GB** (card in hand) and its current RTX 6000 moves to Jarvis. Both are Turing TU102 — the swap is driver-free (same 550.163.01 / 6.14.11-9-pve stack). See [[Compute/Dell R730 - General Node]].

> [!WARNING] Power Draw
> RTX 6000 under full load = ~250W; with dual Xeons this node can draw 500W+. Runs on **UPS A** (Middle Atlantic UPS-OL2200R, the ML bus). See [[Power Distribution]].

---

## CUDA Environment

```bash
nvidia-smi                       # verify GPU + driver 550.163.01
conda create -n ml python=3.11
conda activate ml
conda install pytorch torchvision torchaudio pytorch-cuda=12.1 -c pytorch -c nvidia
python -c "import torch; print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0))"
```

---

## iDRAC Access

```bash
https://192.168.10.20                                   # Web UI (root/calvin)
racadm -r 192.168.10.20 -u root -p calvin getsysinfo
racadm -r 192.168.10.20 -u root -p calvin getsel        # event log
```

---

## Thermal Notes

- R730 fans ramp hard under GPU load
- Custom fan curve via iDRAC: `racadm set System.ThermalSettings.FanSpeedHighOffsetVal`
- Ambient inlet target < 25°C; rear panel of CS9000 removed — ensure wall clearance

---

## Related
- [[Compute/Dell R730 - General Node]] — Jarvis (iDRAC 192.168.10.21, LLM, 2× RTX 6000 planned)
- [[Power Distribution]] — UPS A (Middle Atlantic, ML bus)
- [[Infrastructure/Proxmox Cluster]] — GPU passthrough config
