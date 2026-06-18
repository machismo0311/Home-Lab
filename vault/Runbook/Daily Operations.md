# 📋 Runbook — Daily Operations
**Tags:** #runbook #operations
**Related:** [[Runbook/Network Procedures]] · [[Runbook/Recovery Procedures]] · [[00 - Homelab MOC]]

---

> [!INFO] Current cluster: pve1–pve5 (192.168.10.193/201/202/203/204). All IPs are on flat 192.168.10.0/24 — VLANs not yet active.

---

## 🩺 Health Check

```bash
# 1. Proxmox cluster status
pvecm status
pvecm nodes

# 2. VM/CT status across active nodes
for node in 192.168.10.193 192.168.10.204 192.168.10.201 192.168.10.202 192.168.10.203; do
  echo "=== $node ==="
  ssh root@$node "qm list 2>/dev/null; pct list 2>/dev/null"
done

# 3. Deployed services on pve3
ssh root@192.168.10.201 "cd /opt/nginx-proxy-manager && docker compose ps; cd /opt/vaultwarden && docker compose ps; cd /opt/grafana && docker compose ps"

# 4. CrowdSec status (pve3 host)
ssh root@192.168.10.201 "cscli metrics && cscli decisions list | head -20"

# 5. Network — verify core switch
ping -c 1 192.168.10.50 && echo "EX3400 OK"

# 6. iDRAC reachability (pending R730s)
ping -c 1 -W 2 192.168.10.20 && echo "quarkylab iDRAC reachable"
ping -c 1 -W 2 192.168.10.21 && echo "Jarvis iDRAC reachable"
```

---

## 🔌 Startup Sequence

> [!TIP] Follow this order on cold start.

```
1. Power on Middle Atlantic UPS-2200R (UPS B) → wait for output stable
2. Power on Tripp Lite SMART1500VA (UPS A) → wait for output stable
3. Furman RP-8 should already be live off UPS
4. Power on Juniper EX3400-48P → wait ~60s for boot
5. Power on UniFi USW-24-250W
6. Power on Proxmox small nodes (pve1–pve5)
7. Verify Pi-hole LXC on pve1 is running
8. Verify Docker containers on pve3: NPM, Vaultwarden, Grafana
9. Power on pending hardware as available (R730s, Supermicro)
```

---

## 🛑 Shutdown Sequence (reverse)

```
1. docker compose stop on pve3 (/opt/nginx-proxy-manager, /opt/vaultwarden, /opt/grafana)
2. Gracefully shut down any other VMs/CTs
3. Shut down pve1–pve5: shutdown -h now (or Proxmox UI)
4. Shut down switches (EX3400, USW-24)
5. Let UPS units handle graceful power-off
```

---

## 📡 iDRAC Access (R730s — pending)

| Node | IP | Status |
|---|---|---|
| quarkylab | 192.168.10.20 | iDRAC accessible — BIOS update in progress |
| Jarvis | 192.168.10.21 | iDRAC SSH confirmed — firmware update needed |

```bash
# SSH to iDRAC
ssh root@192.168.10.21   # Jarvis
ssh root@192.168.10.20   # quarkylab

# Power control via racadm
racadm -r 192.168.10.21 -u root -p <pass> serveraction powerup
racadm -r 192.168.10.21 -u root -p <pass> serveraction hardreset
racadm -r 192.168.10.21 -u root -p <pass> getsysinfo
racadm -r 192.168.10.21 -u root -p <pass> getsel   # event log
```

---

## 🔄 Proxmox VM/CT Operations

```bash
# List containers/VMs on a node
qm list && pct list

# Start/stop
qm start <vmid>
qm shutdown <vmid>
pct start <ctid>
pct stop <ctid>

# Snapshot
qm snapshot <vmid> <snapname> --description "Pre-update"
qm rollback <vmid> <snapname>

# OPNsense console access (VM 100 on pve2 — no network needed)
ssh root@192.168.10.204
qm terminal 100
```

---

## 🐳 Docker Services (pve3 — 192.168.10.201)

```bash
ssh root@192.168.10.201

# Nginx Proxy Manager (CT 101)
# Access CT first: pct enter 101
cd /opt/nginx-proxy-manager
docker compose ps
docker compose logs --tail=50 app
docker compose restart app

# Vaultwarden (CT 102)
# pct enter 102
cd /opt/vaultwarden
docker compose ps
docker compose logs --tail=50 vaultwarden
docker compose restart vaultwarden

# Grafana stack (CT 103)
# pct enter 103
cd /opt/grafana
docker compose ps
docker compose logs --tail=50
docker compose restart prometheus   # reload after adding scrape targets
```

---

## 🛡️ CrowdSec (pve3 host)

```bash
ssh root@192.168.10.201

# Status
cscli metrics
cscli decisions list
cscli hub list

# Unban an IP
cscli decisions delete --ip <ip>

# Update hub
cscli hub update && cscli hub upgrade
systemctl restart crowdsec
```

---

## 🧹 Maintenance Tasks

### Weekly
- [ ] Check Proxmox backup status (once PBS is deployed)
- [ ] `docker system prune -f` on pve3 CTs — remove unused images
- [ ] Review Grafana dashboards for anomalies
- [ ] `pihole updateGravity` on pve1 LXC

### Monthly
- [ ] Proxmox + package updates on all nodes: `apt update && apt upgrade`
- [ ] Junos config backup from EX3400: `show configuration | save /tmp/backup.conf`
- [ ] Review CrowdSec console — https://app.crowdsec.net
- [ ] Check iDRAC firmware for R730s (Dell support site)
- [ ] Renew Tailscale auth keys if needed

---

## 🔒 Tailscale

```bash
# Status on any node
tailscale status
tailscale ip

# Key IPs
# pve1: 100.116.237.31
# Ares: 100.124.118.63

# Remote Proxmox UI via Tailscale
# https://100.116.237.31:8006

# DNS fix (if Tailscale overwrites resolv.conf — affects pve3–pve5)
tailscale set --accept-dns=false
```

---

## ☎️ VoIP Troubleshooting

> [!NOTE] VoIP project deferred. Section for when FreePBX goes live.

```bash
systemctl status asterisk
asterisk -rvv
asterisk -rx "sip show peers"
asterisk -rx "core show channels"
asterisk -rx "sip show registry"
```
