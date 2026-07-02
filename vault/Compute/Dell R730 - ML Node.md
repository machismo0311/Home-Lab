# 🖥️ Dell R730 — QuarkyLab (ML Node)
**Tags:** #compute #dell #r730 #cuda #ml
**Related:** [[Compute/Dell R730 - General Node]] · [[Infrastructure/Proxmox Cluster]] · [[Power Distribution]] · [[Infrastructure/QuarkyLab Storage]] · [[Runbook/QuarkyLab-Phase04-GPU-Sharing-2026-07-02]] · [[00 - Homelab MOC]]

---

## Status: 🟢 Online — km-cluster node (RTX 8000 48GB ML — installed 2026-07-01)

- **Host IP:** 192.168.10.179
- **iDRAC:** 192.168.10.20 (root/calvin)
- Member of km-cluster (PVE 9.2.3)
- Hosts **Wazuh SIEM VM 104** (192.168.10.184)
- **Scrutiny collector** installed (reports to hub at 192.168.10.183:8080)
- SSH: `ssh quarkylab` (via `fernanda@quarkylab` key, id_ed25519 on Ares)
- **RTX 8000 48GB installed 2026-07-01** (per the 2026-06-30 GPU plan): the RTX 6000 was swapped out for the RTX 8000; nvidia-smi reports 46080 MiB on driver 550.163.01 / kernel 6.14.11-9-pve. Driver-free swap (both Turing TU102). The freed RTX 6000 is now staged for Jarvis.

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
| **GPU** | NVIDIA Quadro RTX 8000 48GB GDDR6 ECC (driver 550.163.01) — installed 2026-07-01 (swapped from RTX 6000) |
| NICs | 4× 1G onboard |
| Remote Mgmt | iDRAC 8 (192.168.10.20) |
| Depth | ~28" — **rear panel removed** from NetFRAME CS9000 |

---

## Purpose

- Fernanda's ML workloads / **DUNE agent** (RAG pipeline over the DUNE experiment codebase)
- CUDA compute (PyTorch, TensorFlow, JAX), training / fine-tuning
- Vector store (ChromaDB or Qdrant — TBD)

---

## GPU — Quadro RTX 8000 Detail (installed 2026-07-01)

| Field | Value |
|---|---|
| VRAM | 48 GB GDDR6 ECC (46080 MiB reported) |
| CUDA Cores | 4608 |
| Tensor Cores | 576 (2nd gen) |
| TDP | ~250W |
| Driver | NVIDIA 550.163.01 (CUDA 12.x) |

> [!NOTE] RTX 8000 installed 2026-07-01
> Per the 2026-06-30 plan, QuarkyLab now runs the **RTX 8000 48GB**; its former RTX 6000 is staged for Jarvis. Both are Turing TU102 — the swap was driver-free (same 550.163.01 / 6.14.11-9-pve stack), verified with nvidia-smi (46080 MiB). See [[Compute/Dell R730 - General Node]].

> [!WARNING] Power Draw
> RTX 8000 under full load = ~260W; with dual Xeons this node can draw 500W+. Runs on **UPS A** (Middle Atlantic UPS-OL2200R, the ML bus). See [[Power Distribution]].

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

## Chassis Intrusion / F1 POST Halt

> [!NOTE] Cover-removal F1 halt — FIXED 2026-07-02
> Opening the lid trips the chassis-intrusion switch; on the next POST the R730 shows `Alert! Cover was previously removed — Press F1 to continue` and **halts boot** waiting for a keypress. That prompt renders on the onboard **Matrox G200 VGA (0a:00.0)**, *not* the GPU — a monitor plugged into the RTX card shows a black "no signal" screen. This stalled the node during the 2026-07-01 RTX 8000 swap.
>
> **Fix (2026-07-02):** BIOS `MiscSettings.ErrPrompt` ("F1/F2 Prompt on Error") set to **Disabled** — POST no longer stops for non-fatal alerts. Verified after reboot: `ErrPrompt: Disabled`, kernel 6.14.11-9-pve, RTX 8000 present, Wazuh VM 104 auto-started. Intrusion is still recorded to the iDRAC SEL; it just no longer halts boot.

> [!TIP] Changing BIOS attributes on this iDRAC 8 — no racadm, run Redfish *from the node*
> `racadm` is not installed anywhere, and Ares' modern curl can't negotiate the iDRAC's old TLS (handshake fails → http 000). Drive Redfish **from the QuarkyLab host itself** (it reaches its own iDRAC at .20 fine), then reboot to apply:
> ```bash
> IDRAC=192.168.10.20
> B="https://$IDRAC/redfish/v1/Systems/System.Embedded.1/Bios"
> # 1) stage the attribute change (goes to Bios/Settings as pending)
> ssh quarkylab "curl -sk -u root:calvin -X PATCH $B/Settings \
>   -H 'Content-Type: application/json' -d '{\"Attributes\":{\"ErrPrompt\":\"Disabled\"}}'"
> # 2) create the BIOS config job — applies at next reboot
> ssh quarkylab "curl -sk -u root:calvin -X POST \
>   https://$IDRAC/redfish/v1/Managers/iDRAC.Embedded.1/Jobs \
>   -H 'Content-Type: application/json' \
>   -d '{\"TargetSettingsURI\":\"$B/Settings\"}'"
> # 3) after reboot verify:  curl -sk -u root:calvin $B | grep -i errprompt  →  "ErrPrompt":"Disabled"
> ```

---

## Related
- [[Compute/Dell R730 - General Node]] — Jarvis (iDRAC 192.168.10.21, LLM, 2× RTX 6000 planned)
- [[Power Distribution]] — UPS A (Middle Atlantic, ML bus)
- [[Infrastructure/Proxmox Cluster]] — GPU passthrough config
