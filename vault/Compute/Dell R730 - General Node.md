# 🖥️ Dell R730 — Jarvis (General / LLM Node)
**Tags:** #compute #dell #r730 #llm
**Related:** [[Compute/Dell R730 - ML Node]] · [[Infrastructure/Proxmox Cluster]] · [[Power Distribution]]

---

## Status: 🟢 Online — km-cluster node (no GPU yet)

- **Host IP:** 192.168.10.31
- **iDRAC:** 192.168.10.21 (root / <Vaultwarden>)
- Member of km-cluster (PVE 9.2.3); Headscale 100.64.0.6
- **RTX 8000 swap pending** — Dell N08NH power cables on order; no GPU installed yet

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
| **GPU** | none (RTX 8000 swap pending — N08NH cables on order) |
| Storage | pve LVM 56GB — sda (186GB ST200FM0053 SAS SSD) added to VG 2026-06-22 after disk-full during upgrade |
| NICs | 4× 1G onboard |
| Remote Mgmt | iDRAC 8 (192.168.10.21) |
| Depth | ~28" — **rear panel removed** from NetFRAME CS9000 |

---

## Purpose

LLM inference node (currently **offline / no GPU**):
- **llm_router.py** — FastAPI, OpenAI-compatible; routes between local Ollama (Qwen2.5 72B on RTX 8000) and Claude API fallback. **Inactive** until the RTX 8000 is installed.
- Ollama (`llm.netframe.local`) — inactive, no GPU yet.
- General VM hosting / heavy non-GPU workloads.

> [!WARNING] Power
> Runs on **UPS A** (Middle Atlantic UPS-OL2200R, the bottom/ML bus, shared with QuarkyLab + Randy + DS4246). See [[Power Distribution]].

---

## iDRAC Access

```bash
https://192.168.10.21                                   # Web UI (root / <Vaultwarden>)
racadm -r 192.168.10.21 -u root -p $IDRAC_PASS getsysinfo
racadm -r 192.168.10.21 -u root -p $IDRAC_PASS serveraction powercycle
# $IDRAC_PASS: export from Vaultwarden entry "Jarvis iDRAC" before running, e.g.
#   export IDRAC_PASS="$(bw get password jarvis-idrac)"
```

> Historical BIOS/iDRAC recovery (CPU stepping / firmware) for the R730s: see `Home-Lab/docs/r730-bios-recovery-runbook.md`.

---

## Pending — RTX 8000 install

- Awaiting Dell **N08NH** GPU power cables.
- Headscale Phase 2: QuarkyLab + Fernanda's Mac must migrate together — do not migrate one without the other.

---

## Related
- [[Compute/Dell R730 - ML Node]] — QuarkyLab (iDRAC 192.168.10.20, RTX 6000)
- [[Power Distribution]] — UPS A (Middle Atlantic)
- [[Infrastructure/Proxmox Cluster]] — cluster node table
