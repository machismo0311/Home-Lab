# 🖥️ Small Node Cluster (pve1–pve5)
**Tags:** #compute #proxmox #elitedesk
**Related:** [[Infrastructure/Proxmox Cluster]] · [[Compute/Dell R730 - ML Node]]

---

## Node Inventory

| Hostname | Hardware | CPU | RAM | IP | Role |
|---|---|---|---|---|---|
| pve1 | Apple Mac Mini (2011) | Core i5 (Sandy Bridge) | — | 192.168.10.193 | Cluster mgmt, Pi-hole LXC |
| pve2 | HP EliteDesk 800 G4 SFF | i7-8700 (6c/12t) | 32GB | 192.168.10.204 | Services; hosts OPNsense VM 100 |
| pve3 | HP EliteDesk 800 G4 SFF | i7-8700 (6c/12t) | 48GB | 192.168.10.201 | Primary services node (NPM, Vaultwarden, Grafana) |
| pve4 | HP EliteDesk 800 G3 Mini | i5-7500T (4c/4t) | 32GB | 192.168.10.202 | Services |
| pve5 | HP EliteDesk 800 G3 Mini | i5-7500T (4c/4t) | 32GB | 192.168.10.203 | Services |
| RPi 4 | Raspberry Pi 4 | ARM Cortex-A72 | 4/8GB | 192.168.1.170 | Pi-hole backup, IMU gesture bridge |

---

## SSH Access

```bash
ssh root@192.168.10.193   # pve1 (Mac Mini) — ⚠️ needs key auth, add to authorized_keys first
ssh root@192.168.10.204   # pve2
ssh root@192.168.10.201   # pve3
ssh root@192.168.10.202   # pve4
ssh root@192.168.10.203   # pve5
```

> **⚠️ pve1 SSH:** pve1 only accepts publickey auth. Ares key not yet in `authorized_keys`. To add, use pve1 web console at https://192.168.10.193:8006 and run:
> ```bash
> mkdir -p /root/.ssh && chmod 700 /root/.ssh
> echo "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIA9G5mqN1MTgsi+ddrJDJxVpDhhZ5oNNoa+Nmwn/l9BI fernanda@quarkylab" >> /root/.ssh/authorized_keys
> chmod 600 /root/.ssh/authorized_keys
> ```

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
| Primary Pi-hole (pve1 LXC) | 192.168.1.47 | http://192.168.1.47/admin |
| Backup Pi-hole (RPi 4) | 192.168.1.170 | — |

---

## pve1 — Mac Mini 2011 Note

> [!WARNING]
> 2011 Mac mini has a 32nm Sandy Bridge CPU. Proxmox runs but this is legacy hardware — treat as low-priority. Don't run critical VMs here. Currently used for Pi-hole LXC and cluster quorum.

---

## Raspberry Pi 4 — Services

| Service | Status |
|---|---|
| Pi-hole (backup) | ✅ Running at 192.168.1.170 |
| IMU gesture bridge (`bleak` script) | ✅ Running (see [[Projects/IMU Gesture Control]]) |
| `systemd` autostart for IMU service | ✅ Configured |
| Home Assistant | Planned |
