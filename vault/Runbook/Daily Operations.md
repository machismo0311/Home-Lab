# 📋 Runbook — Daily Operations
**Tags:** #runbook #operations
**Related:** [[Runbook/Network Procedures]] · [[Runbook/Recovery Procedures]] · [[00 - Homelab MOC]]

---

> [!INFO] km-cluster is 7 nodes (pve2–pve5 + QuarkyLab .179 / Jarvis .31 / Randy .187); pve1 (Mac Mini, .193) is standalone. Mgmt/services on 192.168.10.0/24. **VLANs are active since 2026-06-25** (EX3400 trunk live) — iDRAC/IPMI now on VLAN 20, servers dual-homed on VLAN 30.

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

# 6. iDRAC/IPMI reachability (VLAN 20 — ping from Ares enp0s31f6.20)
ping -c 1 -W 2 192.168.20.20 && echo "quarkylab iDRAC reachable"
ping -c 1 -W 2 192.168.20.21 && echo "Jarvis iDRAC reachable"
ping -c 1 -W 2 192.168.20.22 && echo "Randy IPMI reachable"
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

## 📡 iDRAC Access (R730s — in km-cluster)

| Node | IP | Status |
|---|---|---|
| QuarkyLab | 192.168.20.20 | Live ML node (RTX 8000 48GB (installed 2026-07-01)); iDRAC on VLAN 20 since 2026-07-03, root / creds in Vaultwarden |
| Jarvis | 192.168.20.21 | Live LLM node (2× RTX 6000 48GB installed 2026-07-04, Ollama GPU-backed); iDRAC on VLAN 20 since 2026-07-03, root / creds in Vaultwarden |
| Randy | 192.168.20.22 | Storage/PBS node; IPMI (ADMIN) on VLAN 20 since 2026-07-03, creds in Vaultwarden |

```bash
# SSH to iDRAC (VLAN 20 — from Ares enp0s31f6.20)
ssh root@192.168.20.21   # Jarvis
ssh root@192.168.20.20   # quarkylab

# Power control via racadm
racadm -r 192.168.20.21 -u root -p <pass> serveraction powerup
racadm -r 192.168.20.21 -u root -p <pass> serveraction hardreset
racadm -r 192.168.20.21 -u root -p <pass> getsysinfo
racadm -r 192.168.20.21 -u root -p <pass> getsel   # event log
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

## 🔒 Headscale (self-hosted VPN control plane)

> Headscale runs on pve3 CT 105 (192.168.10.186). Ares uses Headscale. the researcher's devices still on commercial Tailscale — migration pending.

```bash
# Health check
curl http://192.168.10.186:8080/health   # expect: {"status":"pass"}

# Node list
pct exec 105 -- headscale nodes list

# Logs
pct exec 105 -- journalctl -u headscale -n 30 --no-pager

# Restart
pct exec 105 -- systemctl restart headscale
```

## 🔒 Tailscale (commercial — the researcher's devices)

```bash
# Status on any node
tailscale status
tailscale ip

# Key IPs
# pve1: 100.x.x.x
# Ares: 100.64.0.1 (Headscale) — was 100.x.x.x on commercial

# Remote Proxmox UI via Tailscale
# https://100.x.x.x:8006

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
