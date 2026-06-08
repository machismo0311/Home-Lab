# 📋 Runbook — Network Procedures
**Tags:** #runbook #networking #junos  
**Related:** [[Networking/Juniper EX3400-48P]] · [[Networking/Network Overview]] · [[Runbook/Daily Operations]]

---

## 🔀 Switch Access

```bash
# SSH to EX3400
ssh machismo@10.0.10.2    # or root

# SSH to EX2300
ssh machismo@10.0.10.4

# UniFi CLI (if needed)
ssh admin@10.0.10.3
```

---

## Junos — Safe Change Procedure

> [!WARNING] Always use `commit confirmed` for risky changes. It auto-rolls back in 10 minutes if you don't confirm.

```junos
# 1. Enter config mode
configure

# 2. Make your change
set interfaces ge-0/0/5 unit 0 family ethernet-switching vlan members COMPUTE

# 3. Preview the diff
show | compare

# 4. Commit with auto-rollback timer (10 min safety net)
commit confirmed 10

# 5. If all good — confirm permanently
commit

# 6. If something broke — wait or manually rollback
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

```junos
# Step 1: Create VLAN on EX3400
configure
set vlans <NAME> vlan-id <ID>
commit

# Step 2: Add VLAN to trunk ports (uplink to OPNsense, uplink to USW-24)
set interfaces ge-0/0/46 unit 0 family ethernet-switching vlan members <NAME>
set interfaces xe-0/0/0 unit 0 family ethernet-switching vlan members <NAME>
commit

# Step 3: Create IRB interface for L3 (if routing this VLAN)
set interfaces irb unit <ID> family inet address 10.0.<ID>.2/24
set vlans <NAME> l3-interface irb.<ID>
commit

# Step 4: Create subinterface in OPNsense VM
# Interfaces > Other Types > VLAN > parent: vtnet1, tag: <ID>
# Assign interface, enable DHCP server, add firewall rules

# Step 5: Verify
show vlans <NAME>
show interfaces irb.<ID>
```

---

## OPNsense — Router-on-a-Stick Procedure

```
1. In Proxmox, ensure OPNsense VM has vtnet1 mapped to vmbr0 (trunk bridge)
2. In OPNsense: Interfaces > Other Types > VLAN
   - Parent: vtnet1
   - VLAN tag: <ID>
   - Description: <VLAN_NAME>
3. Interfaces > Assignments > Add newly created VLAN interface
4. Enable interface, set static IP: 10.0.<ID>.1/24
5. Services > DHCPv4 > Enable for new interface, set range
6. Firewall > Rules > Add rules for the interface
7. Test from a client on that VLAN
```

---

## DAC / SFP+ Troubleshooting

```bash
# Check interface status on EX3400
show interfaces xe-0/0/0 detail

# Expected output includes:
# Physical link is Up
# Speed: 10Gbps, Link-mode: Full-duplex

# Check for errors
show interfaces xe-0/0/0 | match error

# If DAC shows down:
# - Reseat both ends
# - Try different SFP+ port
# - Verify same speed on both ends (10G/10G)
# - Check for Junos compatibility (passive DAC should work without override)
```

---

## PoE Troubleshooting (EX3400)

```bash
# Check PoE status
show poe interface ge-0/0/X
show poe controller

# If device not powering on:
# 1. Check PoE budget (show poe controller — look at power used vs available)
# 2. Verify cable is CAT5e or better
# 3. Verify device supports 802.3af or 802.3at
# 4. Try cycling the port:
configure
set poe interface ge-0/0/X disable
commit
delete poe interface ge-0/0/X disable
commit
```

---

## Spanning Tree Verification

```bash
# Verify EX3400 is root bridge
show spanning-tree bridge

# Expected:
# Root ID   Priority 4096
# This bridge is the root

# Check port states
show spanning-tree interface

# Ports should be:
# Forwarding (FWD) — active
# Discarding (DSC) — blocked loops
```

---

## Config Backup Procedure

```bash
# On EX3400 (Junos)
show configuration | save /tmp/ex3400-backup-$(date +%Y%m%d).conf

# SCP to Proxmox backup host
scp root@10.0.10.2:/tmp/ex3400-backup-*.conf root@10.0.10.30:/backups/network/

# Automate weekly via cron on Proxmox
0 3 * * 0 sshpass -p '<pass>' scp root@10.0.10.2:/tmp/ex3400-cfg.conf /backups/network/
```

---

## Emergency — Switch Unreachable

```bash
# Physical console access (RJ45 console cable)
screen /dev/ttyUSB0 9600

# Or via iDRAC console to a host on the management network
# Try to ping the switch management IP from the host

# Last resort: factory reset EX3400
# Hold MODE button on front panel for 15 seconds during boot
# Note: THIS WIPES ALL CONFIG — have backup ready
```
