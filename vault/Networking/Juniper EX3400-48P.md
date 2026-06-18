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
| **Junos Version** | **23.4R2-S7.4** (upgraded from 20.2R3.9) |
| Management IP | **192.168.10.50** |
| Purchase Price | ~$80 (local pickup) |
| Rack Position | U40 |
| Role | Core switch — primary uplink hub, PoE+ host |

---

## Current State

| Item | Status |
|---|---|
| Management access (SSH) | ✅ Working — `ssh mason@192.168.10.50` |
| ge-0/0/32 uplink to UniFi | ✅ Working (access port, VLAN 1 only) |
| DAC xe-0/2/3 → UniFi SFP 2 | ⚠️ DOWN — speed mismatch (10G vs 1G EEPROM) |
| VLAN segmentation | ⏸️ Planned — not yet configured |
| Trunk to OPNsense | ⏸️ Planned — post-OPNsense cutover |
| WiFi → EX3400 path | ⚠️ BROKEN — use wired enp0s31f6 on Ares |

> **⚠️ WiFi access to EX3400 is broken.** Always use wired interface on Ares:
> ```bash
> sudo ip addr add 192.168.10.100/24 dev enp0s31f6
> sudo ip link set enp0s31f6 up
> ssh mason@192.168.10.50
> ```

---

## Junos Key Concepts

### Candidate vs Running Config
```junos
configure

show | compare

commit

rollback 1
commit
```

### ELS VLAN Syntax

> [!NOTE] VLANs are planned but not yet configured. These are reference commands for when VLAN segmentation is implemented.

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
set interfaces ge-0/0/47 unit 0 family ethernet-switching vlan members [MGMT COMPUTE SERVICES IOT VOIP LAB GUEST]
```

### ge-0/0/32 Uplink to UniFi (current — access only)

```junos
# Current config: access port, passes only default VLAN
# This is a known limitation — native-vlan-id is not supported on EX3400
# Fix: configure as trunk without native-vlan-id
set interfaces ge-0/0/32 unit 0 family ethernet-switching interface-mode trunk
set interfaces ge-0/0/32 unit 0 family ethernet-switching vlan members all
# (do NOT add native-vlan-id — not supported, was root cause of previous trunk failure)
```

### Management IP

```junos
# Renumbered 2026-06-05 from .2 to .50 (IP conflict)
set interfaces irb unit 10 family inet address 192.168.10.50/24
set vlans MGMT l3-interface irb.10
set routing-options static route 0.0.0.0/0 next-hop 192.168.10.1
```

### STP Root Bridge

```junos
set protocols rstp bridge-priority 4096
```

---

## Port Map

| Port Range | Assignment | Mode | VLAN(s) |
|---|---|---|---|
| ge-0/0/0–7 | R730 Jarvis (4× NIC + iDRAC) | Trunk / Access | COMPUTE, MGMT (planned) |
| ge-0/0/8–11 | R730 quarkylab (4× NIC + iDRAC) | Trunk / Access | COMPUTE, MGMT (planned) |
| ge-0/0/12–15 | SuperMicro (4× NIC + IPMI) | Trunk / Access | COMPUTE, MGMT (planned) |
| ge-0/0/16–19 | EliteDesk G4 SFF ×2 (pve2, pve3) | Access | COMPUTE (current: untagged) |
| ge-0/0/20–23 | EliteDesk G3 Mini ×2 (pve4, pve5) | Access | COMPUTE (current: untagged) |
| ge-0/0/24–27 | Mac mini (pve1) + RPi 4 | Access | current: untagged |
| ge-0/0/28–35 | Available / future | — | — |
| ge-0/0/32 | **Copper uplink → UniFi USW-24** | **Access (not trunk yet)** | Default VLAN only |
| ge-0/0/36–39 | Cisco CP-8841 phones ×5 (planned) | Access | VOIP (planned) |
| ge-0/0/44 | NetApp DS4246 mgmt | Access | MGMT (planned) |
| ge-0/0/45 | Uplink to EX2300 | Trunk | All |
| ge-0/0/46 | Uplink to OPNsense/Proxmox (planned) | Trunk | All |
| xe-0/2/3 | DAC → UniFi SFP 2 (**⚠️ DOWN**) | Trunk | All (when fixed) |

---

## Useful Show Commands

```bash
show version
show chassis hardware
show interfaces terse
show ethernet-switching interfaces
show vlans
show ethernet-switching table
show spanning-tree bridge
show spanning-tree interface
show route
show poe interface
show poe controller
show log messages | last 50
```

---

## Junos Upgrade

Current version: **23.4R2-S7.4** (upgraded from 20.2R3.9)

```
# To upgrade:
request system software add /var/tmp/junos-arm-32-23.x.Rx.tgz
request system reboot
```

---

## Incidents

### ✅ SSH Authentication Failure — RESOLVED 2026-06-05

**Root causes:**
1. Ares had no IP on management subnet → "Network is unreachable" before SSH connected
2. Stale SSH host key in `~/.ssh/known_hosts:14` after switch re-keyed

**Fixes:**
```bash
sudo nmcli con mod "Wired connection 1" ipv4.method manual ipv4.addresses 192.168.10.11/24 ipv4.gateway 192.168.10.1
sudo nmcli con up "Wired connection 1"
ssh-keygen -R 192.168.10.2
```

**Post-login work:** passwords rotated, NTP configured, timezone set, management IP renumbered .2 → .50, copper uplink ge-0/0/32 patched to UniFi.

Full post-mortem: `Home-Lab/runbooks/EX3400-SSH-Auth-Failure-RCA.md`

### ⚠️ DAC Uplink xe-0/2/3 — OPEN

EX3400 reads DAC as 10G, UniFi reads as 1G (EEPROM mismatch on 10Gtek passive DAC).
**Fix:** Replace DAC with 10G SFP+ optics + LC fiber on both ends.

### ⚠️ ge-0/0/32 Trunk — OPEN

`native-vlan-id` is not supported on EX3400 — this was root cause of trunk failure. ge-0/0/32 is currently access-only. Fix: configure as plain trunk without `native-vlan-id`.

---

## Related
- [[Networking/Network Overview]] — Full topology and current IP assignments
- [[Networking/UniFi USW-24-250W]] — DAC peer
- [[Runbook/Network Procedures]] — Operational runbook
