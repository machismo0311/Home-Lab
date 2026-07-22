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
| Role | Core switch - primary uplink hub, PoE+ host |

---

## Current State

| Item | Status |
|---|---|
| Management access (SSH) | ✅ Working - `ssh mason@192.168.10.50` |
| ge-0/0/32 uplink to UniFi | ✅ Working (access port, VLAN 1 only) |
| DAC xe-0/2/3 → UniFi SFP 2 | ⚠️ DOWN - speed mismatch (10G vs 1G EEPROM) |
| VLAN segmentation | ✅ Live - activated 2026-06-25 (EX3400 ELS); see [[Runbook/VLAN-Activation-2026-06-25]] |
| Trunk to OPNsense | ✅ Live - OPNsense cutover complete; ge-0/0/46 trunk to UniFi Port 24, verified end-to-end |
| WiFi → EX3400 path | ⚠️ BROKEN - use wired enp0s31f6 on Ares |

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

> [!NOTE] Below is the **live config** deployed 2026-06-25 (see [[Runbook/VLAN-Activation-2026-06-25]]). On JunOS ELS, `native-vlan-id` must sit at the **physical interface level**, NOT under `unit 0 family ethernet-switching` - that misplacement caused the earlier trunk outage.

```junos
# VLANs - default (VLAN 1, management) is built-in; the rest are defined by name
set vlans trusted vlan-id 20      # Trusted / iDRAC
set vlans servers vlan-id 30      # Servers
set vlans iot     vlan-id 40      # IoT
set vlans voip    vlan-id 50      # VoIP
set vlans guest   vlan-id 60      # Guest
set vlans lab     vlan-id 70      # Lab

# Access port (single VLAN, untagged) - example
set interfaces ge-0/0/0 unit 0 family ethernet-switching interface-mode access
set interfaces ge-0/0/0 unit 0 family ethernet-switching vlan members servers

# Trunk uplink to UniFi Port 24 - the deployed ge-0/0/46 config
set interfaces ge-0/0/46 native-vlan-id 1                        # ← INTERFACE level (the key ELS fix)
set interfaces ge-0/0/46 unit 0 family ethernet-switching interface-mode trunk
set interfaces ge-0/0/46 unit 0 family ethernet-switching vlan members [ default trusted servers iot voip guest lab ]
```

### ge-0/0/32 Uplink to UniFi (access only - VLAN 1)

`ge-0/0/32` is a legacy access uplink carrying the default VLAN (1) only. The tagged
trunk to the UniFi was ultimately deployed on **ge-0/0/46** (not ge-0/0/32) - see the
trunk config above and [[Runbook/VLAN-Activation-2026-06-25]].

> ⚠️ **Correction:** an earlier version of this note claimed "native-vlan-id is not
> supported on the EX3400." That is **false** - it is supported, but on JunOS ELS it must
> be set at the **physical interface level** (`set interfaces ge-0/0/46 native-vlan-id 1`),
> not under `unit 0 family ethernet-switching`. The wrong placement - not lack of support -
> was the root cause of the original trunk failure.

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

### Confirmed / live (from [[Runbook/VLAN-Activation-2026-06-25]] + `CLAUDE.md`)

| Port | Assignment | Mode | VLAN(s) / Status |
|---|---|---|---|
| ge-0/0/32 | Copper uplink → UniFi USW-24 | Access | `default` (VLAN 1) only - legacy uplink |
| ge-0/0/38 | APC AP7901 managed PDU | Access | `default` (VLAN 1) |
| ge-0/0/45 | Uplink to EX2300 | Trunk | all VLANs (1G) |
| ge-0/0/46 | **Trunk uplink → UniFi Port 24** | Trunk | ✅ **LIVE 2026-06-25** - members `default trusted servers iot voip guest lab`; `native-vlan-id 1` |
| xe-0/2/0 | Randy nic3 (10G data) | - | 10GbE link |
| xe-0/2/3 | DAC → UniFi SFP 2 | Trunk | ⚠️ **DOWN** - 10G/1G EEPROM speed mismatch |

### Planned / unverified (from the 2026-06-14 buildout - confirm with `show ethernet-switching interface` / `show lldp neighbors` on the live switch)

| Port Range | Assignment (as planned) | Mode |
|---|---|---|
| ge-0/0/0–7 | R730 Jarvis (NICs + iDRAC) | Trunk / Access |
| ge-0/0/8–11 | R730 QuarkyLab (NICs + iDRAC) | Trunk / Access |
| ge-0/0/12–15 | SuperMicro / Randy (NICs + IPMI) | Trunk / Access |
| ge-0/0/16–19 | EliteDesk G4 SFF ×2 (pve2, pve3) | Access |
| ge-0/0/20–23 | EliteDesk G3 Mini ×2 (pve4, pve5) | Access |
| ge-0/0/24–27 | Mac mini (pve1) + RPi 4 | Access |
| ge-0/0/36–39 | Cisco CP-8841 phones ×5 | Access (VoIP) |
| ge-0/0/44 | NetApp DS4246 mgmt | Access |

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

### ✅ SSH Authentication Failure - RESOLVED 2026-06-05

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

### ⚠️ DAC Uplink xe-0/2/3 - OPEN

EX3400 reads DAC as 10G, UniFi reads as 1G (EEPROM mismatch on 10Gtek passive DAC).
**Fix:** Replace DAC with 10G SFP+ optics + LC fiber on both ends.

### ⚠️ ge-0/0/32 Trunk - OPEN

`native-vlan-id` IS supported on EX3400 but must be set at the **physical-interface** level (JunOS ELS), NOT under `unit 0 family ethernet-switching` — that misplacement was the trunk-failure root cause. Corrected & live since 2026-06-25 (see the live-config note above and VLAN-Activation-2026-06-25).

---

## Related
- [[Networking/Network Overview]] - Full topology and current IP assignments
- [[Networking/UniFi USW-24-250W]] - DAC peer
- [[Runbook/Network Procedures]] - Operational runbook
