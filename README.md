# NETFRAME Homelab

> **Kyle Mason** · USMC Aviation Veteran · EC-135/145 Instructor Pilot · Network Engineering Candidate (VetTec 2.0 / CCNA)
> [`kylemason.org`](https://kylemason.org) · [`machismo0311`](https://github.com/machismo0311)

A professional-grade homelab built inside a **NetFRAME CS9000 42U rack**, running a 7-node Proxmox VE 9.1 cluster (km-cluster). Purpose-built as a live CCNA lab, LLM inference platform, ML research node, and backup infrastructure — documented here as a technical portfolio.

---

## Cluster Nodes

| Hostname | Role | IP | CPU | RAM | GPU |
|---|---|---|---|---|---|
| **Randy** | Storage / PBS | 192.168.10.187 | 2× E5-2690 v4 | 128 GB | RX 580 8GB |
| **QuarkyLab** | ML / Fernanda | 192.168.10.30 | 2× E5-2699 v4 | 512 GB | RTX 6000 24GB |
| **Jarvis** | LLM Inference | 192.168.10.31 | 2× E5-2687W v4 | 384 GB | RTX 8000 48GB |
| **pve2** | OPNsense host | 192.168.10.204 | i7-8700 | 48 GB | — |
| **pve3** | Cluster node | 192.168.10.201 | i7-8700 | 32 GB | — |
| **pve4** | Cluster node | 192.168.10.202 | i5-7500T | 32 GB | — |
| **pve5** | Cluster node | 192.168.10.203 | i5-7500T | 32 GB | — |

---

## Network

- **Juniper EX3400-48P** — enterprise fabric, JunOS 23.4R2-S7.4, IP `192.168.10.50`
- **UniFi Switch 24 PRO (PoE+)** — consumer fabric (IoT, VoIP, guest)
- **OPNsense 25.7** — VM 100 on pve2, handles routing/firewall/DHCP for all VLANs
- **10G fabric** — Mellanox ConnectX-3 DAC links from Randy/QuarkyLab/Jarvis to EX3400 xe- ports

### VLANs

| ID | Name | Subnet |
|---|---|---|
| 1 | mgmt | 192.168.10.0/24 |
| 20 | trusted | 192.168.20.0/24 |
| 30 | servers | 192.168.30.0/24 |
| 40 | IoT | 192.168.40.0/24 |
| 50 | VoIP | 192.168.50.0/24 |
| 60 | guest | 192.168.60.0/24 |
| 70 | lab | 192.168.70.0/24 |

---

## Storage

### Randy — Internal (Proxmox Backup Server)

- **Boot:** RAID-1 mirror on 2× Seagate SAS SSDs via AVAGO 3108 MegaRAID
- **Data pool:** ZFS `datastore` — 3× RAIDZ2 vdevs of 6× Toshiba AL15SEB18EQ 1.6TB 10K SAS
- **Usable:** ~19.5TB | **PBS fingerprint:** `da:61:6a:4c:49:e8:87:03:08:1d:d7:31:ab:23:58:20:47:58:e8:77:4a:52:3d:39:0c:19:52:e0:67:ee:d9:c9`
- **PBS UI:** `https://192.168.10.187:8007`

### DS4246 — External JBOD

- 13× Toshiba 1.8TB 10K SAS + 19× Dell/Seagate 2TB 7.2K SAS
- Connected via LSI 9207-8e HBA (IT mode) using SFF-8644→SFF-8088 cables

---

## Services

| Service | Host | URL / Port | Notes |
|---|---|---|---|
| Proxmox Backup Server | Randy | `:8007` | v4.2.2, ZFS datastore |
| OPNsense | pve2 (VM 100) | `192.168.10.1` | v25.7 |
| Pi-hole | pve3 (LXC) | `192.168.10.177` | DNS filter |
| Headscale | pve3 (LXC 105) | `192.168.10.186` | v0.29.1, self-hosted VPN |
| step-ca | pve2 | — | Internal CA, `*.netframe.local` TLS |
| Wazuh | pve2 (VM 104) | — | SIEM |
| Ollama + Qwen2.5 72B | Jarvis | `llm.netframe.local` | Q4_K_M, hybrid LLM router |

---

## LLM Infrastructure

Jarvis runs **Ollama** serving **Qwen2.5 72B Q4_K_M** on the RTX 8000 (48GB VRAM).

A **FastAPI `llm_router.py`** implements hybrid routing:
- Default: local Ollama inference
- Escalation: Claude API when logprob confidence drops below threshold

This architecture was written up on [r/LocalLLM](https://reddit.com/r/LocalLLM) and gained community traction.

---

## Power

| UPS | Feeds | Capacity |
|---|---|---|
| Middle Atlantic UPS-OL2200R | R730s, Randy, DS4246 | 6× 12V 9Ah AGM series (76.4V) |
| Tripp Lite SMART1500VA | EX3400, UniFi, small compute | 1500VA |

PDU: APC AP7901 on EX3400 ge-0/0/38.

---

## Planned / In Progress

- [ ] NVIDIA 550 driver on QuarkyLab (pin kernel to 6.14.11-9-pve first)
- [ ] VLAN activation (pve2 trunk to EX3400)
- [ ] DS4246 → Randy via LSI 9207-8e passthrough
- [ ] FreePBX + 5× Cisco CP-8841 VoIP phones
- [ ] Jellyfin on Randy (RX 580 ROCm transcoding)
- [ ] RKE2 Kubernetes (Cilium, MetalLB, NVIDIA GPU Operator)
- [ ] Cyberpunk monitoring dashboard — live API integration
- [ ] IMU gesture control (nRF52 trackers → Home Assistant)
- [ ] Headscale migration (remaining devices off commercial Tailscale)

---

## Repo Structure

```
Home-Lab/
├── README.md
├── docs/
│   ├── netframe-runbook.pdf      # Full infrastructure runbook (LaTeX)
│   ├── netframe-runbook.tex      # LaTeX source
│   └── *.md                      # Session runbooks / incident reports
├── dotfiles/
│   ├── .bashrc                   # Ares admin workstation
│   ├── .bash_aliases             # Homelab aliases
│   └── .ssh/config               # SSH host shortcuts
└── scripts/
    ├── gpu-fan-control.sh        # QuarkyLab GPU fan daemon
    └── llm_router.py             # Hybrid LLM routing (Ollama + Claude API)
```

---

*NetFRAME · Kyle Mason · Vermilion, OH · Built as a live CCNA lab and ML research platform*
