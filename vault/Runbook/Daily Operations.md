# 📋 Runbook — Daily Operations
**Tags:** #runbook #operations  
**Related:** [[Runbook/Network Procedures]] · [[Runbook/Recovery Procedures]] · [[00 - Homelab MOC]]

---

> [!INFO] Runbook Purpose
> This runbook covers routine operational tasks, health checks, and common maintenance procedures for the homelab. Keep this updated as the lab evolves.

---

## 🩺 Daily Health Check

```bash
# 1. Proxmox cluster status
pvecm status
pvecm nodes

# 2. VM/CT status across all nodes
for node in pve-r730-ml pve-r730-gen pve-supermicro pve-g4a pve-g4b; do
  echo "=== $node ===" 
  ssh root@$node "qm list && pct list"
done

# 3. ZFS pool health
zpool status datastore

# 4. UPS status (NUT)
upsc tripplite@localhost
upsc middleatlantic@localhost

# 5. Disk health (smart)
for dev in /dev/sd{a..f}; do
  smartctl -H $dev | grep -E "SMART|overall"
done

# 6. Network — verify core switches up
ping -c 1 10.0.10.2 && echo "EX3400 OK"
ping -c 1 10.0.10.3 && echo "USW-24 OK"
ping -c 1 10.0.10.4 && echo "EX2300 OK"

# 7. Service health (Uptime Kuma covers this visually)
curl -s http://10.0.40.5:3001/api/status-page/default | python3 -m json.tool
```

---

## 🔌 Startup Sequence

> [!TIP] Follow this order on cold start to avoid IP/routing issues.

```
1. Power on Middle Atlantic UPS-2200R (UPS B) → wait for output stable
2. Power on Tripp Lite SMART1500VA (UPS A) → wait for output stable  
3. Power on Furman RP-8 (already on if UPS is on)
4. Power on NetApp DS4246 (storage first)
5. Power on Juniper EX3400-48P (core switch)
6. Power on UniFi USW-24-250W
7. Power on Juniper EX2300-48P
8. Power on Proxmox nodes (start with R730 General — has OPNsense VM)
9. Start OPNsense VM → verify routing
10. Power on remaining Proxmox nodes
11. Start remaining VMs (Vaultwarden, Jellyfin, etc.)
12. Power on small nodes (EliteDesks, Mac mini)
13. Verify Pi-hole running on RPi 4
14. Verify IMU gesture service: `systemctl status imu-gesture`
```

---

## 🛑 Shutdown Sequence (reverse)

```
1. Gracefully shut down VMs (via Proxmox UI or pvesh)
2. Shut down Proxmox nodes (small nodes first, then R730s)
3. Shut down switches (EX2300, USW-24, EX3400)
4. Shut down storage (DS4246)
5. Let UPS drain gracefully (or use NUT: upsmon -c fsd)
```

---

## 📡 iDRAC / IPMI Access

| Node | iDRAC/IPMI IP | Default Login |
|---|---|---|
| R730 ML Node | 10.0.10.10 | root / calvin (change immediately!) |
| R730 General | 10.0.10.11 | root / calvin |
| SuperMicro | 10.0.10.12 | ADMIN / ADMIN (change immediately!) |

```bash
# SSH to iDRAC
ssh root@10.0.10.10

# Power on via racadm
racadm -r 10.0.10.10 -u root -p <pass> serveraction powerup

# Force power cycle
racadm -r 10.0.10.10 -u root -p <pass> serveraction hardreset

# Get system info
racadm -r 10.0.10.10 -u root -p <pass> getsysinfo
```

---

## 🔄 Proxmox VM Operations

```bash
# List all VMs on a node
qm list

# Start / stop VM
qm start <vmid>
qm stop <vmid>
qm shutdown <vmid>

# Migrate VM to another node
qm migrate <vmid> <target-node>

# Create snapshot
qm snapshot <vmid> <snapname> --description "Pre-update snapshot"

# Rollback snapshot
qm rollback <vmid> <snapname>

# Clone VM
qm clone <vmid> <newid> --name <newname> --full
```

---

## 🧹 Maintenance Tasks

### Weekly
- [ ] `zpool scrub datastore` — verify ZFS data integrity
- [ ] Check Proxmox Backup Server — verify backups completed
- [ ] Review Uptime Kuma dashboard — any outages?
- [ ] `pihole updateGravity` — update Pi-hole blocklists
- [ ] Review Grafana dashboards — anomalies?

### Monthly
- [ ] Check SMART data on all drives: `smartctl -a /dev/sdX`
- [ ] Proxmox + package updates: `apt update && apt upgrade`
- [ ] Junos config backup: `show configuration | save /tmp/backup.conf`
- [ ] Review UPS battery health (NUT report)
- [ ] Check iDRAC firmware for R730s (Dell support site)

---

## ☎️ VoIP Troubleshooting

> [!NOTE] VoIP project is deferred. This section is for when it goes live.

```bash
# Check Asterisk/FreePBX status
systemctl status asterisk
asterisk -rvv

# List registered phones
asterisk -rx "sip show peers"

# Check active calls
asterisk -rx "core show channels"

# Reload SIP config
asterisk -rx "sip reload"

# Check VoIP.ms trunk registration
asterisk -rx "sip show registry"
```

---

## 🔋 UPS Events

```bash
# NUT — check UPS state
upsc tripplite@localhost ups.status
# OL = Online, OB = On Battery, LB = Low Battery

# Force graceful shutdown on low battery (NUT auto)
# Configure in /etc/nut/upsmon.conf:
# MINSUPPLIES 1
# SHUTDOWNCMD "/sbin/shutdown -h now"

# Manual FSD (Forced Shutdown)
upsmon -c fsd
```
