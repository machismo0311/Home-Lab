# 🖥️ Dell R730 — Jarvis (General / LLM Node)
**Tags:** #compute #dell #r730 #llm
**Related:** [[Compute/Dell R730 - ML Node]] · [[Infrastructure/Proxmox Cluster]] · [[Power Distribution]]

---

## Status: 🟢 Online — km-cluster node (no GPU yet; 2× RTX 6000 staged)

- **Host IP:** 192.168.10.31
- **iDRAC:** 192.168.10.21 (root/calvin)
- Member of km-cluster (PVE 9.2.3); Headscale 100.64.0.6
- Kernel pinned to **6.14.11-9-pve** (GRUB_DEFAULT; NOT proxmox-boot-tool) for the NVIDIA GPU stack — do not upgrade/change
- **2× RTX 6000 48GB planned** (both cards in hand; QuarkyLab's old RTX 6000 + a new one per the 2026-06-30 GPU plan). GPU software stack BUILT 2026-07-01 (kernel 6.14.11-9-pve, NVIDIA 550.163.01 DKMS, Ollama v0.31.1 → /opt/models). Physical install gated on Dell N08NH aux power cables (2 sets) + R730 GPU riser kit.

> [!NOTE] iDRAC IP was originally static 10.10.198.38; changed via front panel to 192.168.10.21. iDRAC MAC 18:66:da:97:0f:8e.

---

## Hardware Specs

| Component | Spec |
|---|---|
| Model | Dell PowerEdge R730 |
| Hostname | Jarvis |
| Service Tag | DWG7HH2 |
| Form Factor | 2U |
| Rack Position | U18–U20 |
| **CPU** | 2× Intel Xeon E5-2687W v4 (12c each · 48t total) |
| **RAM** | 384 GB LRDIMM ECC DDR4 |
| **GPU** | none installed — 2× RTX 6000 48GB planned (SW stack ready: 6.14.11-9-pve + NVIDIA 550.163.01) |
| Storage | pve LVM 56GB — sda (186GB ST200FM0053 SAS SSD) added to VG 2026-06-22 after disk-full during upgrade; **/opt/models 98G LV** (2026-07-01) for LLM weights |
| NICs | 4× 1G onboard |
| Remote Mgmt | iDRAC 8 (192.168.10.21) |
| Depth | ~28" — **rear panel removed** from NetFRAME CS9000 |

---

## Purpose

LLM inference node (**GPU software stack ready; awaiting cards**):
- **llm_router.py** — FastAPI, OpenAI-compatible; routes between local Ollama (Qwen2.5 72B on 2× RTX 6000) and Claude API fallback. **Inactive** until the GPUs are installed.
- Ollama v0.31.1 (`llm.netframe.local`) — installed, CPU-only for now; models on /opt/models (98G LV). Awaiting GPUs.
- General VM hosting / heavy non-GPU workloads.

> [!WARNING] Power
> Runs on **UPS A** (Middle Atlantic UPS-OL2200R, the bottom/ML bus, shared with QuarkyLab + Randy + DS4246). See [[Power Distribution]].

---

## iDRAC Access

```bash
https://192.168.10.21                                   # Web UI (root/calvin)
racadm -r 192.168.10.21 -u root -p calvin getsysinfo
racadm -r 192.168.10.21 -u root -p calvin serveraction powercycle
```

> Historical BIOS/iDRAC recovery (CPU stepping / firmware) for the R730s: see `Home-Lab/docs/r730-bios-recovery-runbook.md`.

---

## Pending — 2× RTX 6000 install

- Awaiting Dell **N08NH** GPU aux power cables (2 sets) + R730 GPU riser kit.
- Kernel/driver/Ollama already staged (2026-07-01): `dkms status` shows `nvidia/550.163.01, 6.14.11-9-pve` installed; `nvidia-smi` will report devices once cards are seated.
- Headscale Phase 2: QuarkyLab + Fernanda's Mac must migrate together — do not migrate one without the other.

---

## Related
- [[Compute/Dell R730 - ML Node]] — QuarkyLab (iDRAC 192.168.10.20, RTX 8000 48GB (installed 2026-07-01))
- [[Power Distribution]] — UPS A (Middle Atlantic)
- [[Infrastructure/Proxmox Cluster]] — cluster node table
