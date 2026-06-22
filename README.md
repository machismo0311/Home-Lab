# NetFRAME CS9000 — Home Lab

> **Operator:** Kyle Mason (`machismo`) · USMC Veteran · Aviation Professional → Network Engineer  
> **Location:** Vermilion / Greater Cleveland, OH  
> **Cabinet:** NetFRAME CS9000 42U · **Last Updated:** June 2026

A production-grade home lab built around enterprise surplus hardware, purpose-built for ML/AI compute, network engineering study (CCNA), self-hosted services, and hands-on infrastructure work. This repo documents configuration, runbooks, architecture decisions, and ongoing projects.

---

## Table of Contents

- [Hardware Overview](#hardware-overview)
- [Network Architecture](#network-architecture)
- [Compute Nodes](#compute-nodes)
- [Storage](#storage)
- [Services & Software Stack](#services--software-stack)
- [Projects](#projects)
- [Power Distribution](#power-distribution)
- [Cable Standards](#cable-standards)
- [Rack Layout](#rack-layout)
- [Career Context](#career-context)

---

## Hardware Overview

### Switching & Routing

| Device | Role | Notes |
|---|---|---|
| Juniper EX3400-48P | Core switch (L3, PoE+) | Junos 20.2R3.9 · dual PSU · 4× 10G SFP+ |
| UniFi USW-24-250W | Access switch (PoE+) | 24× 1G + 2× 10G SFP+ · DAC uplink to EX3400 |
| Juniper EX2300-48P | Secondary / lab isolation | CCNA lab segmentation |
| HP EliteDesk G4 SFF (32GB) | OPNsense router | Bare metal · WAN gateway · inter-VLAN routing |
| UniFi Dream Router | WAP only | Demoted from router role |
| Raspberry Pi 4 | Pi-hole (DNS primary) | Pi-hole + Home Assistant |

### Enterprise Compute

| Node | CPU | RAM | GPU | Role |
|---|---|---|---|---|
| Dell R730 #1 (Fernanda's ML node) | 2× Xeon E5-2699 v4 (44c/88t) | 512GB ECC LRDIMM | NVIDIA Quadro RTX 6000 24GB | ML/AI research (Fermilab DUNE project) |
| Dell R730 #2 (LLM inference node) | 2× Xeon E5-2687W v4 (24c/48t) | 384GB ECC RDIMM | NVIDIA Quadro RTX 8000 48GB *(in progress)* | Local LLM inference · Ollama + Qwen2.5 72B |
| SuperMicro CSE-219U | 2× Xeon E5-2690 v4 (28c/56t) | 128GB ECC | — | TrueNAS SCALE storage node |

### Small Node Cluster (Proxmox)

| Node | Hardware | RAM | Role |
|---|---|---|---|
| pve1 / pve2 | HP EliteDesk G4 SFF i7-8700 | 48GB / 32GB | Proxmox · OPNsense VM host |
| pve3 / pve4 | HP EliteDesk G3 Mini i5-7th gen | 32GB each | Proxmox general VMs |
| pve5 | Apple Mac mini 2011 | varies | Proxmox · Home Assistant + Pi-hole backup |

### Storage

| Device | Type | Capacity | Role |
|---|---|---|---|
| SuperMicro CSE-219U (internal) | 24× 2.5" SAS | 32 drives total (13× Toshiba 1.8TB 10K + 19× Dell/Seagate 2TB 7.2K) | ZFS fast + bulk pools |
| NetApp DS4246 JBOD | 24-bay 3.5" shelf | Future 3.5" expansion | Connected via LSI 9207-8e HBA (IT mode) |
| Seagate ST200FM0053 SSDs (×4) | SAS 12Gbps MLC | 200GB each | L2ARC / SLOG — SuperMicro + R730 #2 |

---

## Network Architecture

### VLAN Plan

| VLAN | Name | Subnet | Purpose |
|---|---|---|---|
| 10 | MGMT | `10.0.10.0/24` | iDRAC, IPMI, switch OOB, UPS |
| 20 | COMPUTE | `10.0.20.0/24` | Proxmox hosts, VMs |
| 30 | STORAGE | `10.0.30.0/24` | NFS/iSCSI isolation |
| 40 | SERVICES | `10.0.40.0/24` | Jellyfin, Vaultwarden, Uptime Kuma |
| 50 | IOT | `10.0.50.0/24` | Home Assistant, Frigate, BLE bridge |
| 60 | VOIP | `10.0.60.0/24` | Cisco CP-8841 phones, FreePBX |
| 70 | LAB | `10.0.70.0/24` | CCNA lab, EVE-NG, experimental |
| 99 | GUEST | `10.0.99.0/24` | Isolated guest WiFi |

**Routing:** OPNsense on HP EliteDesk G4 SFF (bare metal) · router-on-a-stick via EX3400 trunk  
**DNS:** Pi-hole on Raspberry Pi 4 (primary) · `homelab.local` domain  
**Remote access:** Tailscale mesh VPN across all nodes  
**Subnet migration:** `192.168.1.0/24` → `192.168.10.0/24` (in progress via OPNsense Virtual IP alias)

### Static Management IPs (VLAN 10)

| Device | IP |
|---|---|
| OPNsense | `10.0.10.1` |
| EX3400-48P | `10.0.10.2` |
| USW-24-250W | `10.0.10.3` |
| EX2300-48P | `10.0.10.4` |
| R730 #1 iDRAC | `10.0.10.10` |
| R730 #2 iDRAC | `10.0.10.11` |
| SuperMicro IPMI | `10.0.10.12` |
| Pi 4 | `10.0.10.20` |

---

## Compute Nodes

### R730 #1 — ML Node (Fernanda)

Dedicated to ML/AI research for the [DUNE project](https://www.fnal.gov/) at Fermi National Accelerator Laboratory.

- **CPU:** Dual Xeon E5-2699 v4 · 44c/88t total
- **RAM:** 512GB ECC (16× Samsung 32GB DDR4 LRDIMMs)
- **GPU:** NVIDIA Quadro RTX 6000 24GB (Turing · ECC · PCIe x16)
- **Storage:** Internal bays (Proxmox datastore) — SFF drive population TBD
- **Network:** 4× 1GbE → EX3400 (COMPUTE trunk) + iDRAC (MGMT VLAN 10) → Patch Panel B port 13 (red tape)

### R730 #2 — LLM Inference Node

Local LLM inference server accessible at `llm.netframe.local` (Pi-hole DNS).

- **CPU:** Dual Xeon E5-2687W v4 · 24c/48t total · 3.0GHz base (preferred for inference over 2699's clock speed)
- **RAM:** 384GB ECC RDIMM (24× 16GB — migrated from R730 #1 after Fernanda's upgrade)
- **GPU:** NVIDIA Quadro RTX 8000 48GB *(procurement in progress)*
- **Stack:** Ollama + Qwen2.5 72B Q4_K_M + FastAPI middleware hybrid router
- **Architecture:** Local model handles queries by default; escalates to Claude API when confidence < threshold

**LLM service:** `~/llm_router.py` — OpenAI-compatible endpoint, logprob confidence scoring, Ollama → Claude fallback, stats endpoint for escalation rate monitoring.

**Model targets with RTX 8000 48GB:**

| Model | VRAM Usage | Speed (est.) | Notes |
|---|---|---|---|
| Qwen2.5 72B Q4_K_M | ~40GB | ~12 t/s | Primary deployment target |
| Llama 3.3 70B Q4 | ~38GB | ~12 t/s | Full in-VRAM at this quantization |
| 8B models | ~6GB | ~70 t/s | Fast tier for simple queries |

### SuperMicro CSE-219U — Storage Node

- **CPU:** Dual Xeon E5-2690 v4 · 28c/56t (migrated from R730 #2)
- **RAM:** 128GB ECC (migrated from R730 #2 post-cascade)
- **HBA:** LSI 9207-8e in IT mode (SFF-8088 → DS4246)
- **Planned OS:** TrueNAS SCALE as Proxmox VM with HBA passthrough (IOMMU group verification pending)

### Proxmox Cluster (pve1–pve5)

All nodes hardened post-install: no-subscription repos, Tailscale `--ssh`, Intel IOMMU via GRUB, VLAN-aware bridges, SSH password auth disabled, `prometheus-node-exporter` on each node.

```bash
# Verify cluster health
pvecm status
# Check all nodes
for node in pve1 pve2 pve3 pve4 pve5; do
  ssh $node "hostname && pvecm status | grep -i quorum"
done
```

---

## Storage

### ZFS Pool Design (SuperMicro)

Two-pool architecture separating I/O profiles:

**Fast Pool** — App state, databases, small random I/O
```
Drives:   5× Toshiba AL15SEB18EQ (1.8TB, 10K RPM SAS)
Layout:   RAIDZ1 or mirror (TBD pending final drive count)
L2ARC:    1× Seagate ST200FM0053 200GB SAS SSD
Workloads: Vaultwarden (SQLite), Grafana, Uptime Kuma, FreePBX state
```

**Bulk Pool** — Media, ML datasets, backups, large sequential
```
Drives:   18× Dell/Seagate ST2000NX0463 (2TB, 7.2K RPM SAS)
Layout:   2× RAIDZ2 9-wide vdevs + 1 cold spare
Usable:   ~29TB
L2ARC:    1× Seagate ST200FM0053 200GB SAS SSD
Workloads: Jellyfin media, Fernanda's ML datasets, PBS backups
```

**Why two pools:** Database workloads need low-latency random I/O (SSD or 10K). Media streaming needs throughput, not latency — 7.2K spinning rust is more than fast enough and far cheaper per TB. Mixing them onto one pool wastes either the SSD or throttles the databases.

### Drive Allocation Across Fleet

- **SuperMicro CSE-219U** (24× 2.5" bays): 5× Toshiba 10K + 18× Dell 7.2K + 1 cold spare = 24 drives
- **Dell R730 #2** (8× 2.5" bays): 8× remaining drives (local Proxmox datastore)

### SAS SSDs — L2ARC / SLOG

4× Seagate ST200FM0053 (200GB SAS 12Gbps MLC) from Plus Drives · $29/ea · ETA June 6–11

- 2× → SuperMicro (bulk pool L2ARC via LSI 9207-8e)
- 2× → R730 #2 (pending PERC H730 passthrough resolution)

---

## Services & Software Stack

| Service | Type | Host | URL | Status |
|---|---|---|---|---|
| OPNsense | VM / bare metal | EliteDesk G4 | `10.0.10.1` | ✅ Active |
| Pi-hole | Native | RPi 4 | `http://10.0.10.20/admin` | ✅ Active |
| Home Assistant | VM / native | RPi 4 / pve5 | `http://10.0.50.1:8123` | ✅ Active |
| Tailscale | Mesh VPN | All nodes | — | ✅ Active |
| Ollama + LLM Router | Service | R730 #2 | `llm.netframe.local` | 🔧 In progress |
| TrueNAS SCALE | VM (Proxmox) | SuperMicro | — | 🔧 Planned |
| Vaultwarden | Docker CT | pve-g4a | `vault.homelab.local` | 🔧 Planned |
| Jellyfin | VM | pve-g4b | `jellyfin.homelab.local:8096` | 🔧 Planned |
| Grafana + Loki | Docker CT | pve-g4a | `grafana.homelab.local:3000` | 🔧 Planned |
| Uptime Kuma | Docker CT | pve-g4a | `uptime.homelab.local:3001` | 🔧 Planned |
| FreePBX | VM | R730 #2 | `voip.homelab.local` | 🔧 Planned |
| Proxmox Backup Server | VM | SuperMicro | — | 🔧 Planned |
| UniFi Controller | Docker CT | pve-g4b | `10.0.10.3:8443` | 🔧 Planned |

---

## Projects

### Local LLM Inference Node

**Goal:** Self-hosted LLM accessible across all VLANs at `llm.netframe.local`, with automatic Claude API fallback.

**Stack:** Ollama · Qwen2.5 72B Q4_K_M · FastAPI hybrid router · RTX 8000 48GB

The FastAPI middleware (`llm_router.py`) exposes an OpenAI-compatible endpoint. Confidence is evaluated via logprobs; requests below threshold escalate to Claude API automatically. A `/stats` endpoint tracks local vs. escalated query ratios.

---

### VoIP — FreePBX + Cisco CP-8841 ×5

5× Cisco CP-8841 phones (SIP firmware) on VLAN 60 · VoIP.ms DIDs · FreePBX VM on Proxmox

**Status:** Phones acquired · FreePBX VM deployment pending OPNsense VLAN 60 config

```
Sequence: OPNsense VLAN 60 → FreePBX VM → internal extensions → VoIP.ms SIP trunk
```

---

### IMU Gesture Control → Home Assistant

Reverse-engineered Sword Health IMU trackers (Nordic nRF52) into a BLE gesture-controlled Home Assistant light system.

**Stack:** Python `bleak` · `aiohttp` · systemd service on RPi 4 · Home Assistant REST API

```bash
# Service management
sudo systemctl status imu-gesture
sudo journalctl -u imu-gesture -f
```

---

### CCNA Lab — Cisco IOS + EVE-NG

**Hardware:** Cisco 2901 (physical IOS router, lab VLAN isolated) + EVE-NG on Proxmox (virtual topology)

**Goal:** Hands-on IOS practice alongside existing Juniper (EX3400/EX2300) and OPNsense environments for CCNA exam prep via VetTec 2.0.

---

### eBay Server Scraper

Automated deal scraper monitoring eBay, TechMikeNY, and Bargain Hardware.

**Location:** `~/serverscraper/` on Ares (admin workstation, Debian, `machismo@ares`)  
**Features:** SQLite deduplication · Ohio seller prioritization · email alerting

---

### NetFRAME CS9000 Rack — DS4246 Noise Management

**Problem:** NetApp DS4246 fan noise at full spin  
**Solution:** Shelly Plus Plug US + Home Assistant automation script  
**Behavior:** Script handles ZFS pool export before power cut, import after power restore — safe automated noise management tied to usage schedule

---

## Power Distribution

Two isolated 15A circuits + one additional circuit. Split UPS bus architecture:

**Bus A — Upper rack (network + small compute)**
- Middle Atlantic UPS-2200R (1320W continuous)
- Feeds: Juniper EX3400, UniFi USW-24, EX2300, EliteDesks (pve1–pve4), Mac mini (pve5), RPi 4, patch panels

**Bus B — Lower rack (enterprise compute)**
- Tripp Lite SMART1500VA (2U)
- Feeds: R730 #1, R730 #2, SuperMicro CSE-219U, NetApp DS4246

**Conditioning:** Furman RP-8 upstream of both UPS units (surge + EMI/RFI filtering)

**Additional:** APC Smart-UPS rackmount (model TBD from back panel) · APC AP7901 switched rack PDU (0U vertical)

---

## Cable Standards

**Format:** `[DEVICE]-[PORT]` · Brother PT-D220 · TZe tape · labeled every 10 inches + both ends

**TIA-606 color coding:**

| Color | Assignment |
|---|---|
| 🟢 Green | VoIP (VLAN 60) |
| 🟡 Yellow | Data / WAP / general |
| 🔵 Blue | IoT (VLAN 50) |
| 🔴 Red | Management (iDRAC, IPMI, UPS) |
| ⚫ Gray/Black | Server infrastructure (R730s, SuperMicro, EliteDesks, Mac mini) |

**Patch panels:**
- **Panel A** (24-port → UniFi): ports 13–24 active · 1–12 spare · 6-inch patch cables
- **Panel B** (Leviton → EX3400): ports 13–15 = iDRAC R730 #1 / R730 #2 / SuperMicro (red tape)

**Switch interconnect:** 10Gtek 0.25m passive SFP+ DAC (EX3400 ↔ USW-24-250W)

---

## Rack Layout

```
U42–41  Leviton Patch Panel A + B (×2 stacked)
U40     Juniper EX3400-48P  [core switch]
U39     UniFi USW-24-250W   [access / PoE+]
U38     Juniper EX2300-48P  [secondary / lab]
U35–36  Dell R730 #1        [Fernanda ML node]
U33–34  Dell R730 #2        [LLM inference node]
U31–32  SuperMicro CSE-219U [storage node]
U23     Pull-out work shelf  [fixed]
U18–19  [reserved / future]
U15–16  HP EliteDesk G4 SFF cluster [shelf-mounted]
U13–14  HP EliteDesk G3 Mini + Mac mini [shelf-mounted]
U12     Raspberry Pi 4
U10     NetApp DS4246 JBOD
U7–8    Tripp Lite SMART1500VA (2U)
U6      Furman RP-8
U4–5    Middle Atlantic UPS-2200R
U1–3    APC AP7901 PDU (0U vertical) + APC Smart-UPS
```

---

## Career Context

This lab is built in parallel with a career transition from USMC aviation (EC-135/145 Instructor Pilot, Senior FOQA Officer at Metro Aviation) into network engineering and systems administration.

**Pathway:** VetTec 2.0 → CCNA → Network/Sysadmin roles  
**Portfolio:** [kylemason.org](https://kylemason.org) · GitHub: [machismo0311](https://github.com/machismo0311)

The FOQA background (Flight Operational Quality Assurance — data-driven aviation safety analytics) maps directly to infrastructure monitoring, SIEM, and observability work. The homelab is the hands-on complement to cert study.

---

## Admin Workstation

**Ares** — Debian · username: `machismo` · primary admin node for all CLI work  
Editor: `nano` · Prefers open-source tooling throughout

---

*Built on enterprise surplus. Documented obsessively. Breaking things on purpose since 2024.*
