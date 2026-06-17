# Home Lab

Documentation for my personal home lab — a multi-node Proxmox cluster with Juniper switching, dual UPS, and a NetApp storage shelf, hosted in a NetFRAME CS9000 42U rack in Vermilion / Greater Cleveland, OH.

## Hardware

### Compute
| Node | Hardware | IP | Role |
|---|---|---|---|
| pve1 | Apple Mac mini (2011, Intel Sandy Bridge) | 192.168.10.193 | Lightweight always-on services |
| pve2 | HP EliteDesk 800 G4 SFF (i7-8700, 32GB) | 192.168.10.200 | OPNsense host, network gateway |
| pve3 | HP EliteDesk 800 G4 SFF (i7-8700, 48GB) | 192.168.10.201 | General compute |
| pve4 | HP EliteDesk 800 G3 Mini (i5-7500T, 32GB) | 192.168.10.202 | General compute |
| pve5 | HP EliteDesk 800 G3 Mini (i5-7500T, 32GB) | 192.168.10.203 | General compute |
| QuarkyLab-r730-ml | Dell R730 (28c/56t, 512GB) | — | ML / CUDA workloads |
| Jarvis-r730- LLM | Dell R730 (24c/48t, 384GB) | — | General VM host |
| pve-supermicro | SuperMicro CSE-219U (24c/48t, 128GB) | — | Mixed / storage-adjacent |

### Networking
| Device | Role | Management |
|---|---|---|
| Juniper EX3400-48P | Core PoE+ switch | `192.168.10.50` |
| UniFi USW-24-250W | Access / PoE switch | — |

### Storage
- NetApp DS4246 — 24-bay JBOD, 11× HGST 4TB SATA currently populated, connected via SAS HBA

### Power
- Tripp Lite SMART1500VA (UPS A) — networking + small compute
- Middle Atlantic UPS-2200R (UPS B) — R730s + SuperMicro + DS4246

## Docs

| File | Description |
|---|---|
| [`homelab-setup.md`](homelab-setup.md) | Initial single-node Proxmox setup on Mac Mini — Tailscale, Pi-hole |
| [`docs/proxmox-node-postinstall-runbook.md`](docs/proxmox-node-postinstall-runbook.md) | Post-install checklist applied to all 5 Proxmox nodes before clustering |
| [`runbooks/EX3400-SSH-Auth-Failure-RCA.md`](runbooks/EX3400-SSH-Auth-Failure-RCA.md) | EX3400 SSH auth failure post-mortem (resolved 2026-06-05) |

## Vault

The `vault/` directory is an Obsidian knowledge base with detailed notes on every subsystem:

- **Compute** — R730 ML node, R730 general, SuperMicro, small node cluster
- **Infrastructure** — Proxmox cluster config, VM layout, storage architecture
- **Networking** — EX3400, UniFi switch configs and JunOS notes
- **Power Distribution** — dual UPS bus diagram and load calculations
- **Rack Layout** — physical layout, depth notes, thermal zones
- **Projects** — VoIP/FreePBX, IMU gesture control, server scraper
- **Runbook** — daily ops, network procedures, recovery procedures

Open `vault/` as an Obsidian vault for best navigation.

## Services (Planned)

OPNsense · Vaultwarden · Jellyfin · Grafana · Uptime Kuma · Home Assistant · FreePBX · Proxmox Backup Server
