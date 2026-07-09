# 📋 Runbook — Network Procedures
**Tags:** #runbook #networking #junos
**Related:** [[Networking/Juniper EX3400-48P]] · [[Networking/Network Overview]] · [[Runbook/Daily Operations]]

---

## 🔀 Switch Access

> [!WARNING] WiFi → EX3400 path is broken. Must use wired `enp0s31f6` on Ares.

```bash
# Set up wired access first (from Ares)
sudo ip addr add 192.168.10.100/24 dev enp0s31f6
sudo ip link set enp0s31f6 up

# SSH to EX3400
ssh mason@192.168.10.50

# SSH to EX2300 (IP TBD — not yet on network)
# ssh mason@<ex2300-ip>

# Access cluster nodes
ssh root@192.168.10.193   # pve1
ssh root@192.168.10.204   # pve2
ssh root@192.168.10.201   # pve3
ssh root@192.168.10.202   # pve4
ssh root@192.168.10.203   # pve5
```

---

## Junos — Safe Change Procedure

> [!WARNING] Always use `commit confirmed` for risky changes. Auto-rolls back in 10 minutes if you don't confirm.

```junos
configure

set interfaces ge-0/0/5 unit 0 family ethernet-switching vlan members COMPUTE

show | compare

commit confirmed 10

# If all good — confirm permanently
commit

# If something broke — wait for auto-rollback or:
rollback 1
commit
```

---

## VLAN Provisioning — New Port

```junos
# Access port (single VLAN)
configure
set interfaces ge-0/0/X description "<device-name>"
set interfaces ge-0/0/X unit 0 family ethernet-switching interface-mode access
set interfaces ge-0/0/X unit 0 family ethernet-switching vlan members <VLAN-NAME>
commit

# Trunk port (multi-VLAN)
configure
set interfaces ge-0/0/X description "<device-name>"
set interfaces ge-0/0/X unit 0 family ethernet-switching interface-mode trunk
set interfaces ge-0/0/X unit 0 family ethernet-switching vlan members [VLAN1 VLAN2 VLAN3]
commit
```

---

## Adding a New VLAN

> [!NOTE] VLANs are active since 2026-06-25 (EX3400 trunk live post-OPNsense-cutover). This is the procedure for adding a further VLAN.

```junos
# Step 1: Create VLAN on EX3400
configure
set vlans <NAME> vlan-id <ID>
commit

# Step 2: Add to trunk ports
set interfaces ge-0/0/46 unit 0 family ethernet-switching vlan members <NAME>
# Note: do NOT add native-vlan-id — not supported on EX3400
commit

# Step 3: Create IRB interface for routing
set interfaces irb unit <ID> family inet address 10.0.<ID>.2/24
set vlans <NAME> l3-interface irb.<ID>
commit

# Step 4: In OPNsense (VM 100 on pve2)
# Interfaces > Other Types > VLAN > parent: vtnet1, tag: <ID>
# Assign interface, set static IP 10.0.<ID>.1/24, enable DHCP, add firewall rules

# Step 5: Verify
show vlans <NAME>
show interfaces irb.<ID>
```

---

## OPNsense Cutover Procedure

> Pre-condition: VLANs configured on EX3400, OPNsense fully configured, tested from console.

```
1. Open qm terminal 100 on pve2 (console access to OPNsense, doesn't need network)
2. Verify OPNsense VLAN subinterfaces are all up
3. Verify DHCP server configured per VLAN
4. Verify firewall rules allow inter-VLAN traffic where needed
5. Configure OPNsense WAN (vtnet0) to match Dream Router's uplink settings
6. On EX3400: change ge-0/0/32 from access to trunk (no native-vlan-id)
7. Patch OPNsense Proxmox host's vmbr0 uplink cable to EX3400 trunk port
8. Unplug Dream Router uplink
9. Verify routing from a client on each VLAN
10. ~2 min downtime during cable swap
```

---

## Fix ge-0/0/32 Trunk (current open issue)

```junos
# Current: access port (only default VLAN passes)
# Fix: plain trunk, no native-vlan-id
configure
set interfaces ge-0/0/32 unit 0 family ethernet-switching interface-mode trunk
set interfaces ge-0/0/32 unit 0 family ethernet-switching vlan members all
commit confirmed 5
# Verify connectivity, then: commit
```

---

## DAC / SFP+ Troubleshooting

xe-0/2/3 → UniFi SFP 2 is currently DOWN (speed mismatch on 10Gtek passive DAC).

```bash
# Check interface status on EX3400
show interfaces xe-0/2/3 detail

# If DAC shows down:
# - Reseat both ends
# - Try different SFP+ port
# - Verify same speed on both ends
# Permanent fix: replace DAC with 10G SFP+ optics + LC fiber
```

---

## PoE Troubleshooting (EX3400)

```bash
show poe interface ge-0/0/X
show poe controller

# Cycle port if device not powering
configure
set poe interface ge-0/0/X disable
commit
delete poe interface ge-0/0/X disable
commit
```

---

## Spanning Tree Verification

```bash
show spanning-tree bridge
# EX3400 should be root: Priority 4096

show spanning-tree interface
# Active ports: Forwarding (FWD)
# Blocked loops: Discarding (DSC)
```

---

## Config Backup

```bash
# On EX3400
show configuration | save /tmp/ex3400-backup-$(date +%Y%m%d).conf

# SCP to Proxmox node
scp root@192.168.10.50:/tmp/ex3400-backup-*.conf root@192.168.10.201:/root/switch-backups/
```

---

## Emergency — Switch Unreachable

```bash
# Physical console (RJ45 console cable → Ares USB)
screen /dev/ttyUSB0 9600

# Last resort: factory reset (WIPES ALL CONFIG)
# Hold MODE button 15 seconds during boot
# Have backup config ready before doing this
```
