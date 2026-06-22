# NetFRAME Home Lab — Claude Code Context

## Who I Am
- Kyle Mason, USMC veteran, aviation professional transitioning to network engineering
- Pursuing CCNA via VetTec 2.0, MIS degree at Cleveland State University
- GitHub: machismo0311 | Site: kylemason.org
- Primary workstation: Ares (Debian 12, user: machismo, 192.168.10.199)
- Editor preference: nano
- Style: open-source tooling, step-by-step CLI, code blocks with separate explanation blocks

## Cluster Overview

**km-cluster** — 7-node Proxmox VE 9.1

### Proxmox Nodes
| Node | Hardware | IP | RAM | Role |
|---|---|---|---|---|
| pve2 | HP EliteDesk 800 G4 (i7-8700) | 192.168.10.204 | 48GB | OPNsense host |
| pve3 | HP EliteDesk 800 G4 (i7-8700) | 192.168.10.201 | 32GB | Cluster node |
| pve4 | HP EliteDesk 800 G3 Mini (i5-7500T) | 192.168.10.202 | 32GB | Cluster node |
| pve5 | HP EliteDesk 800 G3 Mini (i5-7500T) | 192.168.10.203 | 32GB | Cluster node |
| sandbox | HP EliteDesk G4 (spare) | 192.168.70.x | — | Standalone lab — NOT in cluster |

### R730 Compute Nodes
| Node | Service Tag | IP | CPUs | RAM | GPU | Role |
|---|---|---|---|---|---|---|
| QuarkyLab | 1S8WR22 | 192.168.10.30 | 2x E5-2699 v4 | 512GB LRDIMM | RTX 6000 24GB | Fernanda ML / DUNE agent |
| Jarvis | DWG7HH2 | 192.168.10.31 | 2x E5-2687W v4 | 384GB LRDIMM | RTX 8000 48GB | LLM inference (Ollama) |

### Randy (SuperMicro — Storage / PBS)
| Field | Value |
|---|---|
| Chassis | SuperMicro CSE-219U 2U 24-bay / X10DRU-i+ |
| IP | 192.168.10.187 |
| IPMI | 192.168.10.22 (ADMIN) |
| CPUs | 2x E5-2690 v4 (56 cores / 48 logical) |
| RAM | 128GB ECC DDR4 |
| BIOS | 3.5 (flashed 06/21/2026) |
| NIC | Mellanox ConnectX-3 MCX312A dual-port 10GbE |
| 10G link | nic3 → EX3400 xe-0/2/0 (10000Mb/s full duplex) |
| Headscale IP | 100.64.0.2 |
| Boot | RAID-1 mirror, 2x Seagate ST200FM0053 185.8GB SAS via AVAGO 3108 MegaRAID |
| Data drives | 18x Toshiba AL15SEB18EQ 1.636TB 10K SAS (3x RAIDZ2 vdevs of 6) |
| Spare drives | 2x Seagate ST2000NX0423 1.818TB SATA (unallocated) |
| GPU | RX 580 8GB (ROCm, display/transcoding only) |
| Proxmox UI | https://192.168.10.187:8006 |
| PBS UI | https://192.168.10.187:8007 (v4.2.2) |
| PBS fingerprint | `da:61:6a:4c:49:e8:87:03:08:1d:d7:31:ab:23:58:20:47:58:e8:77:4a:52:3d:39:0c:19:52:e0:67:ee:d9:c9` |

Randy is a **km-cluster member** (joined 06/22/2026). StorCLI installed at `/usr/sbin/storcli64`. JBOD mode enabled on AVAGO 3108 for data drives.

## Networking
| Device | IP | Role |
|---|---|---|
| EX3400-48P | 192.168.10.50 | Core switch, JunOS 23.4R2-S7.4 |
| OPNsense | 192.168.10.1 (VM 100, pve2) | Router/firewall/DHCP, v25.7 |
| Headscale | 192.168.10.186 (LXC 105, pve3) | VPN, v0.29.1 |
| Pi-hole | 192.168.10.177 (LXC, pve3) | DNS filter |
| APC AP7901 PDU | EX3400 ge-0/0/38 | Managed PDU |
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
| IoT | 40 | 192.168.40.0/24 |
| VoIP | 50 | 192.168.50.0/24 |
| Guest | 60 | 192.168.60.0/24 |
| Lab | 70 | 192.168.70.0/24 |

### Power
| UPS | Feeds | Capacity |
|---|---|---|
| Middle Atlantic UPS-OL2200R | R730s, Randy, DS4246 | 6x 12V 9Ah AGM (76.4V) |
| Tripp Lite SMART1500VA | EX3400, UniFi, small compute | 1500VA |

## Key Services
| Service | Location | URL/Port | Notes |
|---|---|---|---|
| Proxmox Backup Server | Randy | https://192.168.10.187:8007 | v4.2.2, ZFS datastore ~19.5TB |
| Ollama / llm_router.py | Jarvis | llm.netframe.local | Qwen2.5 72B Q4_K_M, RTX 8000 |
| OPNsense | VM 100, pve2 | 192.168.10.1 | v25.7 |
| Headscale | LXC 105, pve3 | 192.168.10.186 | v0.29.1 |
| Pi-hole | LXC, pve3 | 192.168.10.177 | DNS |
| Wazuh | VM 104, pve2 | — | SIEM |
| Prometheus/Grafana/Loki | LXC 103, pve3 | — | Pending migration to Randy |
| step-ca | pve3 | — | *.netframe.local TLS |
| Vaultwarden | TBD | — | Passwords |

## Storage
- **Randy ZFS pool:** `datastore` — 3x RAIDZ2 of 6x Toshiba AL15SEB18EQ 1.636TB 10K SAS, 29.4TB raw / 19.5TB usable
- **Randy boot:** RAID-1 mirror, 2x Seagate ST200FM0053 via AVAGO 3108 MegaRAID
- **Randy spares:** 2x Seagate ST2000NX0423 1.818TB SATA (unallocated in bays)
- **DS4246 JBOD:** 13x Toshiba 1.8TB 10K SAS + 19x Dell/Seagate 2TB 7.2K SAS
- DS4246 → Randy via LSI 9207-8e HBA (IT mode), SFF-8644 → SFF-8088 — passthrough in progress

## Active Projects

### llm_router.py (Jarvis)
- FastAPI service, OpenAI-compatible endpoint
- Routes queries between local Ollama (Qwen2.5 72B, RTX 8000) and Claude API fallback
- Logprob confidence scoring for routing decisions
- Target endpoint: llm.netframe.local
- Discussed in r/LocalLLM

### DUNE Agent (QuarkyLab — Fernanda)
- RAG pipeline over DUNE experiment codebase
- Helps new scientists understand codebase during onboarding
- RTX 6000 24GB: embedding model + inference model
- Vector store: ChromaDB or Qdrant (TBD)
- Model: Qwen2.5-Coder 32B unquantized or 72B Q4_K_M

### NetFRAME Dashboard
- Cyberpunk React wall dashboard (v3, netframe-dashboard-v3.jsx)
- Runs on Dell P2722H monitor
- Displays cluster nodes, GPU strip, Pi-hole stats, OPNsense WAN sparklines

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
- Randy boot drives are RAID-1 via AVAGO 3108 MegaRAID — do not reconfigure
- Randy data drives use separate LSI 9207-8e HBA in IT mode — two different cards
- Randy JBOD mode may reset after reboot — re-run `storcli64 /c0 set jbod=on && storcli64 /c0/eall/sall set jbod` if drives disappear
- Do not mix RDIMMs and LRDIMMs (confirmed incompatible on R730s)
- Supermicro BIOS flash with FDT difference requires two-stage boot — let STARTUP.NSH auto-run
- Proxmox 9.1 + PBS ship enterprise repos in both .list AND .sources formats — disable all 6 files
- Tailscale must set --accept-dns=false on Headscale nodes (MagicDNS not configured)
- StorCLI not in apt — download from Broadcom portal manually, SCP to node
