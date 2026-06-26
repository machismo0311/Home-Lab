# 🖥️ Small Node Cluster (pve1–pve5)
**Tags:** #compute #proxmox #elitedesk
**Related:** [[Infrastructure/Proxmox Cluster]] · [[Compute/Dell R730 - ML Node]]

---

## Node Inventory

| Hostname | Hardware | CPU | RAM | IP | Role |
|---|---|---|---|---|---|
| pve1 | Apple Mac Mini (2011) | Core i5 (Sandy Bridge) | — | 192.168.10.193 | **Standalone** (not in km-cluster); Pi-hole LXC (.177) |
| pve2 | HP EliteDesk 800 G4 SFF | i7-8700 (6c/12t) | 32GB | 192.168.10.204 | km-cluster; hosts OPNsense VM 100, step-ca |
| pve3 | HP EliteDesk 800 G4 SFF | i7-8700 (6c/12t) | 48GB | 192.168.10.201 | km-cluster; primary services (NPM, Vaultwarden, Grafana, Homepage, Headscale, NUT) |
| pve4 | HP EliteDesk 800 G3 Mini | i5-7500T (4c/4t) | 32GB | 192.168.10.202 | km-cluster node |
| pve5 | HP EliteDesk 800 G3 Mini | i5-7500T (4c/4t) | 32GB | 192.168.10.203 | km-cluster node |
| RPi 4 | Raspberry Pi 4 | ARM Cortex-A72 | 4/8GB | (WAN side) | IMU gesture bridge (Pi-hole backup decommissioned) |

---

## SSH Access

```bash
ssh root@192.168.10.193   # pve1 (Mac Mini)
ssh root@192.168.10.204   # pve2
ssh root@192.168.10.201   # pve3
ssh root@192.168.10.202   # pve4
ssh root@192.168.10.203   # pve5
```

---

## Proxmox Web UI Branding

NetFRAME logo installed on all five nodes (replaces default Proxmox logo in the web UI header). Applied to both logo paths via `~/Downloads/netframe_logo_install.sh`:

| Path | Served via |
|------|-----------|
| `/usr/share/javascript/proxmox-widget-toolkit/images/proxmox_logo.svg` | `/pwt/images/` (header — primary) |
| `/usr/share/pve-manager/images/proxmox_logo.*` | `/pve2/images/` (secondary) |

Originals backed up as `proxmox_logo.svg.bak` / `proxmox_logo.png.bak` in the same directories. Rollback: `bash netframe_logo_install.sh rollback [node]`

---

## Physical Notes

- **pve2 + pve3** (EliteDesk G4 SFF): mounted on 3U vented shelf at U34–U36, secured with velcro + zip ties
- **pve4 + pve5** (EliteDesk G3 Mini): same treatment, 3U shelf at U31–U33
- **pve1** (Mac Mini 2011): 1U shelf at U30, co-mounted with RPi 4
- All connect to [[Networking/Juniper EX3400-48P]] or [[Networking/UniFi USW-24-250W]]

---

## Deployed Services (pve3)

| Service | Type | IP | URL |
|---|---|---|---|
| Nginx Proxy Manager | Docker CT 101 | 192.168.10.181 | port 81 (admin) |
| Vaultwarden | Docker CT 102 | 192.168.10.182 | https://vault.kylemason.org |
| Grafana + Prometheus + Loki | Docker CT 103 | 192.168.10.183 | https://grafana.kylemason.org |
| CrowdSec + firewall-bouncer | Native on host | — | https://app.crowdsec.net |

See [[Infrastructure/Services & VMs]] for full configs.

---

## pve1 — Pi-hole

| Role | IP | Admin |
|------|----|-------|
| Pi-hole (pve1 LXC) | 192.168.10.177 | http://192.168.10.177/admin (v6) |

> RPi 4 backup Pi-hole (formerly 192.168.1.170) is **decommissioned**.

---

## pve1 — Mac Mini 2011 Note

> [!WARNING]
> 2011 Mac mini has a 32nm Sandy Bridge CPU. Proxmox runs but this is legacy hardware — treat as low-priority. Don't run critical VMs here. Runs **standalone** (not in km-cluster); hosts the Pi-hole LXC (192.168.10.177).

---

## Raspberry Pi 4 — Services

| Service | Status |
|---|---|
| Pi-hole (backup) | ❌ Decommissioned (was 192.168.1.170) |
| IMU gesture bridge (`bleak` script) | ✅ Running (see [[Projects/IMU Gesture Control]]) |
| `systemd` autostart for IMU service | ✅ Configured |
| Home Assistant | Planned |
