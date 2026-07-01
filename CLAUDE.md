# NetFRAME Home Lab — Claude Code Context

## Who I Am
- Kyle Mason, USMC veteran, aviation professional transitioning to network engineering
- Pursuing CCNA via VetTec 2.0, MIS degree at Cleveland State University
- GitHub: machismo0311 | Site: kylemason.org
- Primary workstation: Ares (Debian 12, user: machismo, 192.168.10.199)
- Editor preference: nano
- Style: open-source tooling, step-by-step CLI, code blocks with separate explanation blocks

## Cluster Overview

**km-cluster** — 7-node Proxmox VE 9.2.3 (upgraded 2026-06-22)

### Proxmox Nodes
| Node | Hardware | IP | RAM | PVE | Kernel | Role |
|---|---|---|---|---|---|---|
| pve2 | HP EliteDesk 800 G4 (i7-8700) | 192.168.10.204 | 32GB | 9.2.3 | 7.0.12-1 | OPNsense host |
| pve3 | HP EliteDesk 800 G4 (i7-8700) | 192.168.10.201 | 48GB | 9.2.3 | 7.0.12-1 | Cluster node |
| pve4 | HP EliteDesk 800 G3 Mini (i5-7500T) | 192.168.10.202 | 32GB | 9.2.3 | 7.0.12-1 | Cluster node |
| pve5 | HP EliteDesk 800 G3 Mini (i5-7500T) | 192.168.10.203 | 32GB | 9.2.3 | 7.0.12-1 | Cluster node |
| sandbox | HP EliteDesk G4 (spare) | 192.168.70.x | — | — | — | Standalone lab — NOT in cluster |

### R730 Compute Nodes
| Node | Service Tag | IP | CPUs | RAM | GPU | PVE | Role |
|---|---|---|---|---|---|---|---|
| QuarkyLab | 1S8WR22 | 192.168.10.179 | 2x E5-2699 v4 | 512GB LRDIMM | RTX 6000 24GB → RTX 8000 48GB† | 9.2.3 | Fernanda ML / DUNE agent |
| Jarvis | DWG7HH2 | 192.168.10.31 | 2x E5-2687W v4 | 384GB LRDIMM | none (2× RTX 6000 planned)† | 9.2.3 | LLM inference |

†GPU plan FINALIZED 2026-06-30: **QuarkyLab → RTX 8000 48GB** (swap out its current RTX 6000); **Jarvis → 2× RTX 6000 48GB** (QuarkyLab's old card + a new one). Both cards in hand, not yet installed — gated on Dell N08NH-type GPU aux power cables (2 sets) + R730 GPU riser kit. Jarvis GPU software stack BUILT & VERIFIED 2026-07-01: kernel 6.14.11-9-pve installed + GRUB-pinned + running, NVIDIA 550.163.01 DKMS module built, Ollama v0.31.1 active with OLLAMA_MODELS=/opt/models (98G LV) — plug-and-play once cards seated.
QuarkyLab: SSH works — `ssh quarkylab` via `fernanda@quarkylab` key (id_ed25519 on Ares). Kernel pinned to 6.14.11-9-pve via GRUB_DEFAULT. NVIDIA 550.163.01 verified working post-upgrade. RTX 8000 is a driver-free swap (same 550.163.01 / 6.14.11 stack).

### Randy (SuperMicro — Storage / PBS)
| Field | Value |
|---|---|
| Chassis | SuperMicro CSE-219U 2U 24-bay / X10DRU-i+ |
| IP | 192.168.10.187 |
| IPMI | 192.168.10.22 (ADMIN) |
| CPUs | 2x E5-2690 v4 (56 cores / 48 logical) |
| RAM | 128GB ECC DDR4 |
| Kernel | 7.0.12-1-pve |
| NIC | Mellanox ConnectX-3 MCX312A dual-port 10GbE |
| 10G link | nic3 → EX3400 xe-0/2/0 |
| Headscale IP | 100.64.0.2 |
| Boot | RAID-1 mirror, 2x Seagate ST200FM0053 185.8GB SAS via AVAGO 3108 MegaRAID |
| Data drives | 18x Toshiba AL15SEB18EQ 1.636TB 10K SAS (3x RAIDZ2 of 6) |
| Spare drives | 2x Seagate ST2000NX0423 1.818TB SATA (unallocated) |
| GPU | RX 580 8GB (ROCm, display/transcoding only) |
| Proxmox UI | https://192.168.10.187:8006 |
| PBS UI | https://192.168.10.187:8007 (v4.2.2) |
| PBS fingerprint | `da:61:6a:4c:49:e8:87:03:08:1d:d7:31:ab:23:58:20:47:58:e8:77:4a:52:3d:39:0c:19:52:e0:67:ee:d9:c9` |

Randy in km-cluster. StorCLI at `/usr/sbin/storcli64`. JBOD mode enabled on AVAGO 3108.

## Networking
| Device | IP | Role |
|---|---|---|
| EX3400-48P | 192.168.10.50 | Core switch, JunOS 23.4R2-S7.4 |
| OPNsense | 192.168.10.1 (VM 100, pve2) | Router/firewall/DHCP, v25.7 |
| Headscale | 192.168.10.186 (LXC 105, pve3) | VPN, v0.29.1 — Ares (.1), Randy (.2), pve5 (.3), pve4 (.4), pve3 (.5), Jarvis (.6) |
| Pi-hole | 192.168.10.177 (pve1 LXC 103) | DNS — on Mac Mini standalone node, NOT pve3 |
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
| Proxmox Backup Server | Randy | https://192.168.10.187:8007 | v4.2.2, ZFS ~19.5TB — LXCs 02:00 daily, VMs 03:00 daily, 7d+4w retention |
| OPNsense | VM 100, pve2 | 192.168.10.1 | v25.7, onboot=1 |
| Headscale | LXC 105, pve3 | 192.168.10.186 | v0.29.1, onboot=1 |
| Pi-hole | pve1 LXC 103 | 192.168.10.177 | DNS — Mac Mini standalone, NOT pve3 |
| Homepage | pve3 LXC 106 (.148) | https://homepage.kylemason.org | Live widgets (Proxmox/Pi-hole/Jellyfin/Scrutiny/UPS); Power & UPS group via PeaNUT container (:8081→8080, NUT bridge); NPM proxy host id 4 + Lets Encrypt (CF DNS-01) + basic auth (kyle); :3000 firewalled to NPM; tokens/creds in /opt/homepage/config + compose (not git). See Homepage-Setup-2026-06-26.md & Power Distribution.md |
| nginx-proxy (NPM) | LXC 101, pve3 (.181) | Admin http://192.168.10.181:81 | onboot=1; :81 restricted to Ares (.199) via DOCKER-USER fw (F-05) ✅ |
| Vaultwarden | LXC 102, pve3 | http://192.168.10.182 | Docker Compose, healthy ✅ onboot=1 |
| Prometheus/Grafana/Loki | LXC 103, pve3 (.183) | Grafana http://192.168.10.183:3000 | Stack active ✅; 8 nodes scraped; Prom/Loki localhost-only (F-03) |
| Scrutiny (drive health) | LXC 103, pve3 + collectors on Randy & QuarkyLab | http://192.168.10.183:8080 | ~50 drives monitored; InfluxDB backend; binary collector via systemd timer every 6h on Randy (43) and QuarkyLab (7); collector.yaml `host.id` + endpoint `192.168.10.183:8080` |
| Wazuh | QuarkyLab VM 104 | `https://192.168.10.184` | SIEM — migrated from pve2 |
| step-ca | pve2 | https://192.168.10.204:443 | *.netframe.local TLS — active ✅ password at /etc/step-ca/secrets/password |
| Jellyfin | Randy (host) | http://192.168.10.187:8096 | v10.11.11; media at /datastore/media/{movies,tv,music}; GPU transcoding pending RX 580 power cable |
| Ollama | Jarvis | llm.netframe.local | v0.31.1 installed (CPU-only), models on /opt/models (98G LV) — awaiting 2× RTX 6000 |

**Wazuh VM 104 is on QuarkyLab** (migrated from pve2). IP: 192.168.10.184 (DHCP). Dashboard: `https://192.168.10.184`.

## Storage
- **Randy ZFS:** `datastore` — 3x RAIDZ2 of 6x Toshiba 1.636TB 10K SAS, 29.4TB raw / 19.5TB usable
- **Randy boot:** RAID-1, 2x Seagate ST200FM0053 via AVAGO 3108 MegaRAID
- **Jarvis root:** pve LVM 56GB — sda (186GB ST200FM0053 SAS SSD) added to VG 2026-06-22 after disk-full during upgrade; **/opt/models 98G LV** added 2026-07-01 for LLM weights (OLLAMA_MODELS)
- **DS4246 JBOD:** 13x Toshiba 1.8TB + 19x Dell/Seagate 2TB SAS, via LSI 9207-8e (IT mode) — passthrough pending

## Active Projects

### llm_router.py (Jarvis)
FastAPI, OpenAI-compatible. Routes between local Ollama (Qwen2.5 72B, Jarvis 2× RTX 6000 48GB) and Claude API fallback. **Currently inactive** — awaiting Jarvis GPU install (SW stack ready).

### DUNE Agent — Fernanda (QuarkyLab)
RAG pipeline over DUNE experiment codebase. RTX 6000 24GB (→ RTX 8000 48GB after planned swap). Vector store: ChromaDB or Qdrant (TBD).

### NetFRAME Dashboard
Cyberpunk React wall dashboard (v3, netframe-dashboard-v3.jsx) on Dell P2722H.

## Coding Conventions
- All scripts use bash unless Python is explicitly required
- Python scripts use venv, requirements.txt
- Systemd unit files for all persistent services
- No Docker unless explicitly requested (prefer LXC on Proxmox)
- Secrets go in Vaultwarden, never hardcoded
- Label convention: [DEVICE]-[PORT], TIA-606 cable colors

## Important Safety Notes
- ALWAYS check prior conversation before touching pve2 network config (June 15 outage)
- QuarkyLab kernel MUST stay on 6.14.11-9-pve — GRUB_DEFAULT is pinned; 6.17+ breaks NVIDIA 550; never run kernel upgrades or change GRUB default on QuarkyLab
- Jarvis is ALSO now pinned to 6.14.11-9-pve (GRUB_DEFAULT; NOT proxmox-boot-tool) for its NVIDIA 550.163.01 GPU stack — do not change GRUB default or upgrade the kernel on Jarvis either
- QuarkyLab SSH: `ssh quarkylab` (IP 192.168.10.179) via fernanda@quarkylab key (id_ed25519 on Ares)
- Tailscale overwrites /etc/resolv.conf on ALL nodes — run `tailscale set --accept-dns=false` and set nameserver to 192.168.10.177 before any apt operations
- Headscale Phase 2 pending: QuarkyLab + Fernanda's Mac (ferpsihas@, fus22-009897) must migrate together — do not migrate one without the other
- VLAN activation COMPLETE (2026-06-25): EX3400 ge-0/0/46 trunk live to UniFi Port 24, verified end-to-end. KEY: native-vlan-id goes at INTERFACE level on this EX3400 (ELS), NOT under unit 0 family ethernet-switching. pve2 vmbr2/nic2 auto-start DISABLED (unused bridge with live UniFi cable caused trunk loop) — do not re-enable without removing its cable. See VLAN-Activation-2026-06-25.md
- Ares WiFi is on WAN side (192.168.1.x) — OPNsense outage = full loss of management network access from WiFi. Keep wired cable (enp0s31f6, 192.168.10.100) plugged in during any pve2/OPNsense maintenance
- ifreload -a does NOT apply bridge-vlan-aware on pve2 — requires full reboot of pve2
- Randy boot drives RAID-1 via AVAGO 3108 MegaRAID — do not reconfigure
- Randy data drives use separate LSI 9207-8e HBA in IT mode — two different cards
- Randy JBOD mode may reset after reboot — re-run `storcli64 /c0 set jbod=on && storcli64 /c0/eall/sall set jbod`
- Randy corosync singleton after reboot: from pve2 `pvecm delnode Randy`, then on Randy `pkill pmxcfs; systemctl start pve-cluster`
- Jarvis root was 6GB (disk-full during upgrade) — now 56GB with sda added to pve VG
- pve3 LXCs (101/102/103/105) all have onboot=1 set — verify before rebooting pve3
- Proxmox 9.x ships enterprise repos in .list AND .sources formats — disable all 6 files
- Do not mix RDIMMs and LRDIMMs (confirmed incompatible on R730s)
- StorCLI not in apt — download from Broadcom portal manually, SCP to node
- Supermicro BIOS flash with FDT difference requires two-stage boot — let STARTUP.NSH auto-run
