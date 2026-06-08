# 🔀 Juniper EX3400-48P
**Tags:** #networking #juniper #switching #junos  
**Related:** [[Networking/Network Overview]] · [[Networking/UniFi USW-24-250W]] · [[Runbook/Network Procedures]]

---

## Hardware Overview

| Field | Value |
|---|---|
| Model | EX3400-48P |
| Form Factor | 1U |
| Ports | 48× 1G PoE+ (802.3at), 4× 10G SFP+, 2× 40G QSFP+ |
| PoE Budget | ~750W |
| PSUs | Dual redundant |
| Junos Version | ELS Junos 20.2R3.9 |
| Purchase Price | ~$80 (local pickup) |
| Rack Position | U40 |
| Role | Core switch — primary uplink hub, PoE+ host |

---

## Junos Key Concepts

### Candidate vs Running Config
```
# Edit candidate config
configure

# Review pending changes
show | compare

# Commit to running
commit

# Rollback 1 step
rollback 1
commit
```

### ELS VLAN Syntax (Enhanced Layer 2 Software)
```junos
# Create VLANs
set vlans MGMT vlan-id 10
set vlans COMPUTE vlan-id 20
set vlans STORAGE vlan-id 30
set vlans SERVICES vlan-id 40
set vlans IOT vlan-id 50
set vlans VOIP vlan-id 60
set vlans LAB vlan-id 70
set vlans GUEST vlan-id 99

# Access port (single VLAN, untagged)
set interfaces ge-0/0/0 unit 0 family ethernet-switching interface-mode access
set interfaces ge-0/0/0 unit 0 family ethernet-switching vlan members COMPUTE

# Trunk port (multiple VLANs, tagged)
set interfaces ge-0/0/47 unit 0 family ethernet-switching interface-mode trunk
set interfaces ge-0/0/47 unit 0 family ethernet-switching vlan members [MGMT COMPUTE STORAGE SERVICES IOT VOIP LAB GUEST]
```

### Uplink to OPNsense (Router-on-a-Stick)
```junos
# Trunk to Proxmox host running OPNsense VM
set interfaces ge-0/0/46 unit 0 family ethernet-switching interface-mode trunk
set interfaces ge-0/0/46 unit 0 family ethernet-switching vlan members all

# Native VLAN for untagged mgmt fallback
set interfaces ge-0/0/46 unit 0 family ethernet-switching native-vlan-id 10
```

### DAC Uplink to UniFi USW-24
```junos
# SFP+ DAC (10Gtek 0.25m passive) — xe-0/0/0
set interfaces xe-0/0/0 description "DAC-uplink-to-USW24"
set interfaces xe-0/0/0 unit 0 family ethernet-switching interface-mode trunk
set interfaces xe-0/0/0 unit 0 family ethernet-switching vlan members all
```

### STP Root Bridge Configuration
```junos
# Set EX3400 as root bridge for all VLANs
set protocols rstp bridge-priority 4096
```

### Management IP (VLAN 10)
```junos
# NOTE: was .2 — renumbered 2026-06-05 due to IP conflict (see Incidents below)
set interfaces irb unit 10 family inet address 192.168.10.50/24
set vlans MGMT l3-interface irb.10
set routing-options static route 0.0.0.0/0 next-hop 192.168.10.1
```

---

## Port Map

| Port Range | Assignment | Mode | VLAN(s) |
|---|---|---|---|
| ge-0/0/0–7 | R730 ML Node (4× NIC + iDRAC) | Trunk / Access | COMPUTE, MGMT |
| ge-0/0/8–11 | R730 General (4× NIC + iDRAC) | Trunk / Access | COMPUTE, MGMT |
| ge-0/0/12–15 | SuperMicro (4× NIC + IPMI) | Trunk / Access | COMPUTE, MGMT |
| ge-0/0/16–19 | EliteDesk G4 SFF ×2 | Access | COMPUTE |
| ge-0/0/20–23 | EliteDesk G3 Mini ×2 | Access | COMPUTE |
| ge-0/0/24–27 | Mac mini + RPi 4 | Access | COMPUTE / IOT |
| ge-0/0/28–35 | Available / future | — | — |
| ge-0/0/36–39 | Cisco CP-8841 phones ×5 | Access | VOIP |
| ge-0/0/32 | Copper uplink → UniFi USW-24 (1G, working) | Trunk | All |
| ge-0/0/44 | NetApp DS4246 mgmt | Access | MGMT |
| ge-0/0/45 | Uplink to EX2300 | Trunk | All |
| ge-0/0/46 | Uplink to OPNsense/Proxmox | Trunk | All |
| xe-0/2/3 | DAC → UniFi SFP 2 (10G, ⚠️ DOWN — speed mismatch) | Trunk | All |

---

## Useful Show Commands

```bash
# System info
show version
show chassis hardware

# Interface status
show interfaces terse
show ethernet-switching interfaces

# VLAN state
show vlans
show ethernet-switching table

# Spanning tree
show spanning-tree bridge
show spanning-tree interface

# Routing
show route

# PoE status
show poe interface
show poe controller

# Logs
show log messages | last 50
```

---

## Upgrade Path

> [!NOTE] Junos Version
> Running **20.2R3.9** — stable for homelab purposes. If upgrading, download from Juniper support portal, copy via SCP, then:
> ```
> request system software add /var/tmp/junos-arm-32-20.x.Rx.tgz
> request system reboot
> ```

---

## Incidents

### ✅ SSH Authentication Failure — RESOLVED 2026-06-05

**Symptom:** SSH always rejected — appeared to be an auth failure.  
**Actual root causes (two, unrelated to auth):**
1. Ares had no IP on the management subnet (DHCP, no server) → `Network is unreachable` before SSH even connected
2. Stale SSH host key in `~/.ssh/known_hosts:14` after switch was re-keyed → `Host key verification failed`

**Fixes:**
```bash
# 1. Set static IP on Ares wired interface
sudo nmcli con mod "Wired connection 1" ipv4.method manual ipv4.addresses 192.168.10.11/24 ipv4.gateway 192.168.10.1
sudo nmcli con up "Wired connection 1"

# 2. Clear stale host key
ssh-keygen -R 192.168.10.2
```
mason authenticated first attempt — credential was never broken.

**Post-login work done:** passwords rotated (root + mason), NTP configured (`162.159.200.123`), timezone set (`America/New_York`), management IP renumbered from `.2` to `.50` (IP conflict — `.2` was occupied by another device, MAC `78:45:58:bf:3f:ee`), copper uplink (`ge-0/0/32`) patched to UniFi to resolve switch island.

**Open items:**
- ⚠️ DAC uplink `xe-0/2/3` still down — EX3400 reads DAC as 10G, UniFi reads as 1G (EEPROM mismatch). Fix: replace with 10G SFP+ optics + LC fiber on both ends.
- Identify device at `192.168.10.2` (MAC `78:45:58:bf:3f:ee`) and assign it a documented address.
- Add DHCP reservation in OPNsense for Ares (MAC `8c:ec:4b:f1:86:a5`).
- JunOS upgrade: current 20.2R3.9 → JTAC-recommended 23.4R2-S7 (non-urgent).

See full post-mortem: `Home-Lab/docs/EX3400-SSH-Auth-Failure-RCA.md`

---

## Related
- [[Networking/Network Overview]] — Full topology
- [[Networking/UniFi USW-24-250W]] — DAC peer
- [[Runbook/Network Procedures]] — Operational runbook
