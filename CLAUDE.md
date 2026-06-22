# NetFRAME Home Lab — Claude Code Context

## Who I Am
- Kyle Mason, USMC veteran, aviation professional transitioning to network engineering
- Pursuing CCNA via VetTec 2.0, MIS degree at Cleveland State University
- GitHub: machismo0311 | Site: kylemason.org
- Primary workstation: Ares (Debian 12, user: machismo, 192.168.10.199)
- Editor preference: nano
- Style: open-source tooling, step-by-step CLI, code blocks with separate explanation blocks

## Cluster Overview

### Proxmox Nodes (pve1–pve5)
| Node | Hardware | Role |
|---|---|---|
| pve1-pve4 | HP EliteDesk G4 | Proxmox cluster nodes |
| pve5 | HP EliteDesk G4 (i5-7500) | Proxmox cluster node |
| sandbox | HP EliteDesk G4 (spare) | Standalone lab/learning — NOT in cluster |

### R730 Compute Nodes
| Node | Service Tag | CPUs | RAM | GPU | Role |
|---|---|---|---|---|---|
| QuarkyLab | 1S8WR22 | 2x E5-2699 v4 | 512GB LRDIMM | RTX 8000 48GB | Fernanda ML / DUNE agent |
| Jarvis | DWG7HH2 | 2x E5-2687W v4 | 384GB LRDIMM | 2x RTX 6000 24GB | LLM inference (Ollama) |

### Randy (SuperMicro)
| Field | Value |
|---|---|
| Model | SYS-2028U-E1CNRT+ |
| Motherboard | X10DRU-i+ |
| CPUs | 2x E5-2690 v4 |
| RAM | 128GB ECC |
| BIOS | 3.5 (flashed 06/21/2026) |
| IPMI | 192.168.10.22 |
| GPU | RX 580 8GB (ROCm, display/transcoding only) |
| NIC | Mellanox ConnectX-3 10GbE |
| RAID | LSI MegaRAID + Tecate supercapacitor |
| Role | Storage, PBS, Jellyfin, monitoring, NFS |

## Networking
| Device | IP | Role |
|---|---|---|
| EX3400 | 192.168.10.50 | Core switch, JunOS 23.4R2-S7.4 |
| OPNsense | 192.168.10.200/204 | Firewall/router (VM 100 on pve2) |
| Headscale | 192.168.10.186 | VPN (LXC 105 on pve3) |
| Ares | 192.168.10.199 | Admin workstation |
| QuarkyLab iDRAC | 192.168.10.20 | root/calvin |
| Jarvis iDRAC | 192.168.10.21 | root/calvin |
| Randy IPMI | 192.168.10.22 | ADMIN |

### VLANs (EX3400)
| VLAN | ID | Subnet |
|---|---|---|
| Management | 1 | 192.168.10.0/24 |
| Trusted/iDRAC | 20 | 192.168.20.0/24 |
| Servers | 30 | 192.168.30.0/24 |
| IoT | 40 | — |
| VoIP | 50 | — |
| Guest | 60 | — |
| Lab | 70 | 192.168.70.0/24 |

## Key Services
| Service | Location | Notes |
|---|---|---|
| Proxmox Backup Server | Randy (planned) | Highest priority |
| Ollama / llm_router.py | Jarvis | FastAPI, Qwen2.5 72B Q4_K_M |
| OPNsense | VM 100, pve2 | v25.7 |
| Headscale | LXC 105, pve3 | v0.29.1 |
| Pi-hole | LXC, cluster | DNS |
| Wazuh | VM 104 | SIEM |
| Prometheus/Grafana/Loki | Management G4 | Pending migration to Randy |
| Step-CA | pve3 | *.netframe.local TLS |
| Vaultwarden | TBD | Passwords |

## Active Projects

### llm_router.py (Jarvis)
- FastAPI service, OpenAI-compatible endpoint
- Routes queries between local Ollama (Qwen2.5 72B) and Claude API fallback
- Logprob confidence scoring for routing decisions
- Target endpoint: llm.netframe.local
- Discussed in r/LocalLLM

### DUNE Agent (QuarkyLab — Fernanda)
- RAG pipeline over DUNE experiment codebase
- Helps new scientists understand codebase during onboarding
- RTX 8000 48GB: embedding model + inference model
- Vector store: ChromaDB or Qdrant (TBD)
- Model: Qwen2.5-Coder 32B unquantized or 72B Q4_K_M

### NetFRAME Dashboard
- Cyberpunk React wall dashboard (v3, netframe-dashboard-v3.jsx)
- Runs on Dell P2722H monitor
- Displays all 8 cluster nodes, GPU strip, Pi-hole stats, OPNsense WAN sparklines

## Storage
- NetApp DS4246 JBOD: 13x Toshiba 1.8TB 10K SAS + 19x Dell/Seagate 2TB 7.2K SAS
- LSI 9207-8e HBA (IT mode) in Randy for DS4246 passthrough
- Planned ZFS pools: fast (5x Toshiba RAIDZ2) + bulk (18x Dell, 2x RAIDZ2 9-wide)
- Randy internal bays: 22x 2.5" SAS drives

## Pending Hardware (parts in transit)
- 2x Dell N08NH GPU power cables (QuarkyLab dual RTX 6000)
- 1x Supermicro CBL-PWEX-0665 (RX 580 power in Randy)
- 2x SuperMicro MCP-220-00075-0B 2.5" drive caddies

## GPU Swap (pending parts arrival)
- RTX 8000 moves: Jarvis → QuarkyLab
- 2x RTX 6000 move: QuarkyLab → Jarvis
- No NVLink bridge needed on either server

## Coding Conventions
- All scripts use bash unless Python is explicitly required
- Python scripts use venv, requirements.txt
- Configs go in /etc or service-appropriate locations
- Systemd unit files for all persistent services
- No Docker unless explicitly requested (prefer LXC on Proxmox)
- Secrets go in Vaultwarden, never hardcoded
- Label convention: [DEVICE]-[PORT], TIA-606 cable colors

## Important Safety Notes
- ALWAYS search prior conversation history before touching pve2 network config
- Prior June 15 network outage caused by incorrect interface changes on pve2
- QuarkyLab kernel must be pinned to 6.14.11-9-pve (6.17 breaks NVIDIA 550 driver)
- Randy LSI MegaRAID fate TBD — do not assume IT mode until confirmed
- Do not mix RDIMMs and LRDIMMs — confirmed incompatible
