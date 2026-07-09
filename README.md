# NETFRAME Homelab

> **Kyle Mason** · USMC Veteran · EC-135/145 Instructor Pilot
> [`kylemason.org`](https://kylemason.org) · [`machismo0311`](https://github.com/machismo0311)

A professional-grade homelab built inside a **NetFRAME CS9000 42U rack**, running a 7-node Proxmox VE cluster (km-cluster) — PVE 9.2.3 on every node except Randy (9.1.1, kernel/ZFS-only upgrade). Purpose-built as a live CCNA lab, LLM inference platform, ML research node, and backup infrastructure — documented here as a technical portfolio.

---

## Cluster Nodes

| Hostname | Role | IP | CPU | RAM | GPU | PVE | Kernel |
|---|---|---|---|---|---|---|---|
| **Randy** | Storage / PBS | 192.168.10.187 | 2× E5-2690 v4 | 128 GB | RX 580 8GB | 9.1.1 | 7.0.12-1 |
| **QuarkyLab** | ML / Fernanda | 192.168.10.179 | 2× E5-2699 v4 | 512 GB | RTX 8000 48GB† | 9.2.3 | 6.14.11-9-pve† |
| **Jarvis** | LLM Inference | 192.168.10.31 | 2× E5-2687W v4 | 384 GB | 2× RTX 6000 (48GB total)‡ | 9.2.3 | 6.14.11-9-pve‡ |
| **pve2** | OPNsense host | 192.168.10.204 | i7-8700 | 32 GB | — | 9.2.3 | 7.0.12-1 |
| **pve3** | Cluster node | 192.168.10.201 | i7-8700 | 48 GB | — | 9.2.3 | 7.0.12-1 |
| **pve4** | Cluster node | 192.168.10.202 | i5-7500T | 32 GB | — | 9.2.3 | 7.0.12-1 |
| **pve5** | Cluster node | 192.168.10.203 | i5-7500T | 32 GB | — | 9.2.3 | 7.0.12-1 |

†QuarkyLab: RTX 8000 48GB installed & verified 2026-07-01 (nvidia-smi reports 48GB on NVIDIA 550.163.01; driver-free Turing swap). Kernel pinned — NVIDIA 550.163.01 requires 6.14.11-9-pve.  
‡Jarvis: **2× RTX 6000 installed & verified 2026-07-04** — 24GB each / 48GB total (driver 550.163.01, kernel 6.14.11-9-pve). Required a nouveau blacklist on first boot; fans managed by the `gpu-fan-control` daemon. Ollama GPU-backed, qwen2.5:72b pulled.

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
- **Data pool:** ZFS `datastore` — 4× RAIDZ2 vdevs: 3× 6-wide Toshiba AL15SEB18EQ 1.6TB 10K SAS + 1× 4-wide Seagate ST2000NX0423 1.8TB SATA (all in-pool, no spares)
- **Capacity:** 36.7TB raw / ~23TB usable | **PBS fingerprint:** `(stored in Vaultwarden — not published)`
- **PBS UI:** `https://192.168.10.187:8007`

### DS4246 — External JBOD

- 16× 4TB SAS, dual-path via LSI 9207-8e HBA (IT mode) + multipath, SFF-8644→SFF-8088 cables
- **Pool `bulk` — built & online 2026-07-08:** 2× 8-wide RAIDZ2, 58.2TB raw / ~41.3 TiB usable, reboot-verified (auto-imports cleanly)

---

## Services

| Service | Host | URL / Port | Notes |
|---|---|---|---|
| Proxmox Backup Server | Randy | `:8007` | v4.2.2, ZFS 36.7TB raw / ~23TB usable — daily backups 02:00/03:00 |
| OPNsense | pve2 (VM 100) | `192.168.10.1` | v25.7 |
| Pi-hole | pve1 (LXC, Mac Mini) | `192.168.10.177` | DNS filter — standalone node, NOT pve3 |
| Headscale | pve3 (LXC 105) | `192.168.10.186` | v0.29.1, self-hosted VPN |
| Wazuh | QuarkyLab (VM 104) | `https://192.168.10.184` | SIEM |
| step-ca | pve2 | `https://192.168.10.204:443` | Internal CA, `*.netframe.local` TLS |
| Vaultwarden | pve3 (LXC 102) | `http://192.168.10.182` | Active ✅ (healthy, onboot=1) |
| Open WebUI | pve3 (LXC 107) | `http://chat.netframe.local` | ChatGPT-style UI → llm_router; models `local`/`rag` |
| Jellyfin | Randy | `:8096` | v10.11.11; media on `/datastore/media` |
| Ollama + Qwen2.5 72B | Jarvis | `llm.netframe.local` | v0.31.1, GPU-backed on 2× RTX 6000 (installed 2026-07-04); qwen2.5:72b tensor-split across both |

> Selected services — full container/service inventory (NPM, Grafana/Prometheus/Loki, Homepage, Scrutiny, llm_router, …) is in the vault.

---

## LLM Infrastructure

Jarvis runs **Ollama** serving **Qwen2.5 72B Q4_K_M** across **2× RTX 6000** (48GB VRAM total, 24GB each) — GPUs installed & verified 2026-07-04, qwen2.5:72b pulled (tensor-splits across both cards). Stack: kernel 6.14.11-9-pve, NVIDIA 550.163.01, models on the `tank/models` ZFS dataset (7.2TB pool, since 2026-07-08).

A **FastAPI `llm_router.py`** (OpenAI-compatible) implements hybrid routing:
- Default: local Ollama inference (Qwen2.5 72B)
- Escalation: Claude API (`claude-opus-4-8`) on an explicit `escalate` flag, a `model=claude-*` request, or local failure. (Ollama exposes no logprobs, so routing is by flag/model/failure — not confidence scoring.)
- Optional `model:"rag"` grounds answers on the Home-Lab vault with `[source]` citations.

---

## Power

| UPS | Feeds | Capacity |
|---|---|---|
| Middle Atlantic UPS-OL2200R | R730s, Randy, DS4246 | 6× 12V 9Ah AGM series (76.4V) |
| Tripp Lite SMART1500VA | EX3400, UniFi, small compute | 1500VA |

PDU: APC AP7901 on EX3400 ge-0/0/38.

---

## Planned / In Progress

- [x] Randy commissioned — PBS live, ZFS datastore 36.7TB raw / ~23TB usable
- [x] Cluster upgrade — all cluster nodes to PVE 9.2.3 / kernel 7.0.12-1 (2026-06-22); Randy kernel/ZFS-only, stays on pve-manager 9.1.1
- [x] NVIDIA 550 driver on QuarkyLab — kernel pinned to 6.14.11-9-pve
- [x] Jarvis GPU software stack staged (2026-07-01) — kernel 6.14.11-9-pve pinned, NVIDIA 550.163.01 DKMS built, Ollama on /opt/models
- [x] QuarkyLab RTX 6000 → RTX 8000 48GB swap ✅ 2026-07-01 (nvidia-smi reports 48GB, NVIDIA 550.163.01)
- [x] Jarvis 2× RTX 6000 install ✅ 2026-07-04 (24GB each / 48GB total; Ollama GPU-backed, qwen2.5:72b)
- [x] Backup schedules configured — daily to randy-pbs, 7d+4w retention
- [x] Promtail log shipping on all 8 nodes → Loki ✅ 2026-06-25
- [x] Wazuh agent 4.9.2 on all 8 nodes → full SIEM coverage ✅ 2026-06-25
- [x] DS4246 → Randy — pool `bulk` built & online 2026-07-08 (2× 8-wide RAIDZ2, ~41.3 TiB usable, reboot-verified)
- [x] VLAN activation ✅ 2026-06-25 — EX3400 ge-0/0/46 trunk live, verified end-to-end (DHCP lease on VLAN 20). Fix: native-vlan-id at interface level (ELS)
- [x] Jellyfin installed on Randy v10.11.11 — http://192.168.10.187:8096 ✅ (GPU transcoding pending RX 580 power cable)
- [x] Prometheus node-exporter deployed on all 8 nodes (randy/pve2/pve3/pve4/pve5/quarkylab/jarvis/pve1) ✅
- [x] Scrutiny — drive health UI live at http://192.168.10.183:8080 (~50 drives, collectors on Randy + QuarkyLab, 6h) ✅
- [ ] FreePBX + 5× Cisco CP-8841 VoIP phones
- [ ] RKE2 Kubernetes (Cilium, MetalLB, NVIDIA GPU Operator)
- [ ] Cyberpunk monitoring dashboard — live API integration
- [ ] IMU gesture control (nRF52 trackers → Home Assistant)
- [x] Headscale Phase 1 — pve3/4/5/Jarvis migrated to self-hosted (2026-06-22)
- [ ] Headscale Phase 2 — QuarkyLab + the researcher's Mac (must migrate together)

---

## Repo Structure

```
Home-Lab/
├── README.md
├── CLAUDE.md                     # Homelab context for Claude Code (canonical)
├── CLAUDE.dotfiles.md            # Dotfiles repo context
├── index.html                    # Personal landing page (kylemason.org)
├── docs/                         # Runbooks, incident reports, LaTeX sources (.tex)
│   └── storage/                  #   PDFs are recompiled from .tex before publishing
├── runbooks/                     # Session runbooks (EX3400, VLAN, Homepage)
├── vault/                        # Obsidian knowledge base — canonical runbooks & topic docs
│   ├── Compute/ Infrastructure/ Networking/ Runbook/ Projects/
│   └── CLAUDE.netframe.md        # Deployed copy of root CLAUDE.md
├── scripts/                      # llm_router (FastAPI), jarvis-oncall bot, gpu-fan-control, SMART tooling
├── services/                     # homepage/ + netframe-monitor/ configs & systemd units
├── topology/                     # Sanitized network topology reference (.md/.tex/.pdf)
├── headscale/                    # Headscale VPN docs
├── student-guide/                # QuarkyLab researcher/student onboarding guides
└── dotfiles/                     # .bashrc, .bash_aliases, .ssh/config (sanitized)
```

---

*NetFRAME · Kyle Mason · Greater Cleveland, OH · Built as a live CCNA lab and ML research platform*
