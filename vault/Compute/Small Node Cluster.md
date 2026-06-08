# 🖥️ SuperMicro CSE-219U
**Tags:** #compute #supermicro  
**Related:** [[Infrastructure/Proxmox Cluster]] · [[Compute/Small Node Cluster]]

---

## Hardware Specs

| Component | Spec |
|---|---|
| Model | SuperMicro CSE-219U |
| Form Factor | 2U |
| Rack Position | U13–U14 |
| **CPU** | 2× Intel Xeon E5-2650 v4 |
| CPU Cores | 24c / 48t total |
| **RAM** | 64 GB ECC |
| NICs | 4× 1G |
| Remote Mgmt | IPMI (10.0.10.12) |

## Purpose

Mixed workloads — overflow compute, storage-adjacent tasks, additional Proxmox cluster node.

---

# 🖥️ Small Node Cluster
**Tags:** #compute #proxmox #elitedesk  
**Related:** [[Infrastructure/Proxmox Cluster]] · [[Compute/Dell R730 - ML Node]]

---

## Node Inventory

| Device | CPU | RAM | Role | Position |
|---|---|---|---|---|
| HP EliteDesk G4 SFF A | i7-8700 (6c/12t) | 48 GB | Proxmox node | U34–U36 shelf |
| HP EliteDesk G4 SFF B | i7-8700 (6c/12t) | 32 GB | Proxmox node | U34–U36 shelf |
| HP EliteDesk G3 Mini A | i5-7th gen | 32 GB | Proxmox node | U31–U33 shelf |
| HP EliteDesk G3 Mini B | i5-7th gen | 32 GB | Proxmox node | U31–U33 shelf |
| Mac mini (2011) | Core i5 | — | Proxmox (experimental) | U30 shelf |
| Raspberry Pi 4 | ARM Cortex-A72 | 4/8 GB | Pi-hole / Home Assistant | U30 shelf (co-mount) |

---

## Physical Notes

- EliteDesk SFFs: mounted on 3U vented shelf, secured with velcro + zip ties
- EliteDesk Minis: same treatment, 3U shelf
- Mac mini: 1U shelf, co-mounted with RPi 4 using custom bracket or adhesive mount
- All connect to [[Networking/UniFi USW-24-250W]] or [[Networking/Juniper EX3400-48P]]

---

## Raspberry Pi 4 — Dedicated Services

| Service | Status |
|---|---|
| Pi-hole | Planned |
| Home Assistant | Planned |
| IMU gesture bridge (`bleak` script) | ✅ Running (see [[Projects/IMU Gesture Control]]) |
| `systemd` autostart for IMU service | ✅ Configured |

---

## Mac mini 2011 — Proxmox Note

> [!WARNING]
> 2011 Mac mini has a 32nm Sandy Bridge CPU. Proxmox runs but this is legacy hardware — treat as ephemeral. Don't run critical VMs here.
