# NetFRAME Infrastructure Update
**Date:** June 21, 2026  
**Session:** Randy commissioning, GPU swap decision, DUNE agent planning

---

## Randy (SuperMicro SYS-2028U-E1CNRT+)

### Hardware Inventory

| Component | Detail |
|---|---|
| Motherboard | Supermicro X10DRU-i+ |
| Chassis | SYS-2028U-E1CNRT+ (219U-10) |
| Board Serial | OM15CS036459 |
| CPUs | Dual E5-2690 v4 @ 2.60 GHz |
| RAM | 128GB ECC DDR4 2133 MHz |
| BIOS | 3.5 (flashed from 2.0 on 06/21/2026) |
| IPMI | 192.168.10.22, BMC 03.94, user ADMIN |
| NIC | Mellanox ConnectX-3 EN 10GbE (MCX312A-XCB7) |
| RAID Card | LSI MegaRAID (MR RMB L3-25376-00A) + Tecate supercap |
| GPU | AMD RX 580 8GB DDR5 (awaiting power cable) |
| GPU PWR | 3x onboard headers (GPU PWR2/3/4) — SuperMicro proprietary |
| Drive Bays | 2.5" native, 22 caddies total |
| Riser | RSC-R10W-E8R |

### BIOS Flash — Completed

**Method:** UEFI Shell via IKVM console (IPMI web UI)

1. Downloaded `X10DRU2.427.zip` from Supermicro
2. Created FAT32 UEFI bootable USB on Ares
3. Copied UEFI folder contents to `/EFI/BOOT/`
4. Fixed broken Java KVM via IKVM Reset in IPMI Maintenance
5. Booted to UEFI Built-in EFI Shell via F11 boot menu
6. Two-stage flash: FDT difference detected → reboot → STARTUP.NSH auto-resumed
7. **Result:** BIOS 3.5, ME Entire Image update success ✅

**Key lesson:** Supermicro BIOS jumps with different FDT require two boot cycles. The first run creates STARTUP.NSH and reboots. Boot back to EFI Shell and let STARTUP.NSH run automatically.

### Parts Ordered

| Item | Purpose | Qty |
|---|---|---|
| Dell N08NH | GPU aux power (QuarkyLab dual RTX 6000) | 2 |
| Supermicro CBL-PWEX-0665 | 8-pin CPU → 8-pin PCIe (RX 580 in Randy) | 1 |
| SuperMicro MCP-220-00075-0B | 2.5" drive caddies | 2 |

### Randy's Role in Cluster

Randy is the **infrastructure backbone** — not a compute node.

**Services (priority order):**
1. **Proxmox Backup Server (PBS)** — critical, cluster has no backup currently
2. **NFS/ZFS storage** — serves DS4246 JBOD + internal bays to cluster
3. **Jellyfin** — media server, RX 580 handles ROCm transcoding
4. **Prometheus + Grafana + Loki** — migrate from management G4
5. **Scrutiny** — drive health monitoring for 22+ drives
6. **MinIO** — S3 object storage for the researcher's datasets
7. **Vaultwarden** — location TBD

**What Randy does NOT do:**
- No ML/LLM workloads
- No Ollama inference
- No GPU compute (RX 580 is for display + transcoding only)

### Pending Before Proxmox Install

- [ ] CBL-PWEX-0665 arrives → power RX 580
- [ ] Confirm video output via RX 580 HDMI → KVM
- [ ] Install Proxmox via external USB
- [ ] Determine LSI MegaRAID fate (IT mode flash vs keep for RAID)
- [ ] Add Randy to Proxmox cluster

---

## GPU Swap Decision

### New Configuration

| Server | GPU | VRAM | Role |
|---|---|---|---|
| QuarkyLab | RTX 8000 (from Jarvis) | 48GB | DUNE research agent |
| Jarvis | 2x RTX 6000 (from QuarkyLab) | 48GB total | LLM inference/Ollama |
| Randy | RX 580 | 8GB | Display + transcoding |

### Rationale

**QuarkyLab gets RTX 8000:**
- the researcher's DUNE RAG agent needs max single-GPU VRAM
- 48GB holds large code model + embedding model simultaneously
- Single GPU = cleaner inference, no PCIe overhead

**Jarvis gets dual RTX 6000:**
- LLM inference is bursty, not sustained
- Ollama handles multi-GPU natively
- 48GB aggregate VRAM matches RTX 8000
- PCIe overhead acceptable for query routing use case

**NVLink:** Not needed for either server. the researcher's workload is inference/RAG, not training.

---

## the researcher's DUNE Agent Project

### Overview
- **Goal:** RAG agent over DUNE experiment codebase
- **Purpose:** Help new scientists understand full codebase during onboarding
- **Host:** QuarkyLab (after RTX 8000 swap)
- **Claude Project:** "DUNE Agent" ✅ created

### Architecture
- RAG pipeline (inference, not training)
- Embedding model on RTX 8000 (dedicated GPU allocation)
- Inference model on RTX 8000 (48GB handles large code model)
- Suggested models: Qwen2.5-Coder 32B unquantized or 72B Q4_K_M
- Vector store: ChromaDB or Qdrant (TBD)

---

## Sandbox / Lab Node

### Hardware
- Spare HP EliteDesk G4 (unused, in rack)
- **Standalone** — do NOT add to Proxmox cluster

### Purpose
- Safe environment for learning and breaking things
- CCNA lab work (GNS3, EVE-NG)
- Service testing before deploying to Randy
- k3s Kubernetes lab (future)

### Network
- VLAN 70 (lab VLAN), IP range: `192.168.70.x`
- Hostname/name: TBD

---

## Claude Projects Created

| Project | Purpose |
|---|---|
| NetFRAME — LLM Infrastructure | Jarvis, Ollama, llm_router, GPU swap |
| DUNE Agent | RAG pipeline, QuarkyLab ML env |

---

## Full Cluster GPU Inventory

The GPU-equipped servers (compute/storage nodes; the pve2–pve5 nodes are GPU-less):

| Server | GPU | VRAM | CUDA | Use |
|---|---|---|---|---|
| QuarkyLab | RTX 8000 | 48GB | ✅ | ML / DUNE research |
| Jarvis | 2x RTX 6000 | 48GB | ✅ | LLM inference |
| Randy | RX 580 | 8GB | ❌ (ROCm) | Display/transcode |

This enables distributed inference routing across all GPU nodes via `llm_router.py`.
