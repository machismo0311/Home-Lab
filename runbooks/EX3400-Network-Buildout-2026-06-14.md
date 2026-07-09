# NetFRAME Network Buildout — Session Notes
**Date:** 2026-06-14  
**Status:** 🟡 In Progress — VLAN infrastructure built, trunk connection to pve2 pending  
**Follows:** `EX3400-SSH-Auth-Failure-RCA.md`

---

## Session Summary

Full-day buildout session. JunOS upgraded, VLAN infrastructure designed and committed on EX3400, OPNsense fully configured for all VLANs including DHCP and firewall rules. Physical hardware installed (RAM upgrades, SuperMicro 10G NIC + HBA). VLANs are defined but not yet live — pve2 needs a trunk connection before tagged traffic can reach OPNsense.

---

## Network Topology Decision

| Switch | Role | VLANs Served |
|---|---|---|
| Juniper EX3400-48P | Enterprise fabric | Management (1), Trusted (20), Servers (30), Lab (70) |
| UniFi Switch 24 PRO | Consumer fabric | IoT (40), VoIP (50), Guest (60) |

**Rationale:** EX3400 handles rack/server/management infrastructure. UniFi handles IoT, VoIP, and Guest where UniFi's application-aware management and PoE profiles are better suited. VLANs 40/50/60 are defined on the EX3400 trunk only (transit to reach OPNsense) — no access ports for those VLANs on the EX3400.

**Inter-switch link:** RJ45 copper, ge-0/0/32 → UniFi (1G). DAC (xe-0/2/3 → UniFi SFP 2) link-down due to speed mismatch — Juniper reads as 10G, UniFi reads as 1G. Permanent fix: fiber (10G SFP+ optic + LC patch on each end).

---

## VLAN Design

| VLAN | Name | Subnet | Color | Endpoints |
|---|---|---|---|---|
| 1 | Management | 192.168.10.0/24 | 🔴 Red | Switch mgmt (.50), iDRAC ×3, APC AP7901 PDU, Middle Atlantic UPS |
| 20 | Trusted | 192.168.20.0/24 | 🟡 Yellow | Ares (wired), Fernanda's laptop (occasional) |
| 30 | Servers | 192.168.30.0/24 | ⬛ Black | R730 #1, R730 #2, SuperMicro, Proxmox hosts |
| 40 | IoT | 192.168.40.0/24 | 🔵 Blue | UniFi-side only (transit on EX3400) |
| 50 | VoIP | 192.168.50.0/24 | 🟢 Green | UniFi-side only (transit on EX3400) |
| 60 | Guest | 192.168.60.0/24 | — | UniFi-side only (transit on EX3400) |
| 70 | Lab | 192.168.70.0/24 | — | CCNA lab gear, OPNsense mgmt |

---

## JunOS Upgrade — 20.2R3.9 → 23.4R2-S7.4

### Target
23.4R2-S7.4 — current JTAC recommended release for EX3400.

### Issues Encountered

**SCP failure:** `subsystem request failed on channel 0` — OpenSSH 9.x changed `scp` to use SFTP protocol internally. Junos 20.2 doesn't fully support this. Fix: `scp -O` flag forces legacy SCP protocol.

**Storage constraint:** `/dev/gpt/junos` = 1.3G, only 378 MB free. `file copy http://...` double-buffers (downloads to /tmp, then copies to /var/tmp), requiring ~2× file size. Failed with `No space left on device` even though file nominally fit.

**Validation failure:**
```
ERROR: Cannot validate junos-arm-32-23.4R2-S7.4.gz: requires osmajor 12 kernel support.
NOTICE: Use the 'no-validate' option to proceed.
```
Expected — upgrading across kernel versions (20.x → 23.x changes osmajor). Standard documented workaround: `no-validate` flag.

### What Worked
`request system software add` with HTTP URL and `no-validate` flag. The command auto-freed space before downloading (removed old package sets, logs, snapshot), then fetched and installed in one pass:

```
# On Ares — serve the file:
cd ~/Downloads
python3 -m http.server 8000

# On the switch:
request system software add http://192.168.10.199:8000/junos-arm-32-23.4R2-S7.4.gz no-validate
request system reboot
```

**Verified:**
```
show version
# Hostname: KM-EX3400
# Model: ex3400-48p
# Junos: 23.4R2-S7.4 ✅
```

### tmpfs Note
`show system storage` revealed two RAM-based filesystems with significant free space:
- `/.mount/tmp` (tmpfs): 582 MB, 581 MB free
- `/.mount/mfs` (tmpfs): 324 MB, 324 MB free

These are unaffected by the `/dev/gpt/junos` space constraint and can be used for staging if needed: `file copy http://URL /tmp/filename` bypasses the persistent storage constraint.

---

## EX3400 Configuration Committed

### VLANs
```
set vlans trusted vlan-id 20
set vlans servers vlan-id 30
set vlans iot vlan-id 40
set vlans voip vlan-id 50
set vlans guest vlan-id 60
set vlans lab vlan-id 70
```

### Inter-switch Trunk (ge-0/0/32 → UniFi)
```
set interfaces ge-0/0/32 unit 0 family ethernet-switching interface-mode trunk
set interfaces ge-0/0/32 unit 0 family ethernet-switching vlan members default
set interfaces ge-0/0/32 unit 0 family ethernet-switching vlan members trusted
set interfaces ge-0/0/32 unit 0 family ethernet-switching vlan members servers
set interfaces ge-0/0/32 unit 0 family ethernet-switching vlan members iot
set interfaces ge-0/0/32 unit 0 family ethernet-switching vlan members voip
set interfaces ge-0/0/32 unit 0 family ethernet-switching vlan members guest
set interfaces ge-0/0/32 unit 0 family ethernet-switching vlan members lab
set interfaces ge-0/0/32 unit 0 family ethernet-switching native-vlan-id 1
```

### Pending Port Config (needs physical port numbers)
```
# Proxmox host trunk ports — replace ge-0/0/X with actual port
set interfaces ge-0/0/X unit 0 family ethernet-switching interface-mode trunk
set interfaces ge-0/0/X unit 0 family ethernet-switching vlan members default
set interfaces ge-0/0/X unit 0 family ethernet-switching vlan members trusted
set interfaces ge-0/0/X unit 0 family ethernet-switching vlan members servers
set interfaces ge-0/0/X unit 0 family ethernet-switching vlan members iot
set interfaces ge-0/0/X unit 0 family ethernet-switching vlan members voip
set interfaces ge-0/0/X unit 0 family ethernet-switching vlan members guest
set interfaces ge-0/0/X unit 0 family ethernet-switching vlan members lab
set interfaces ge-0/0/X unit 0 family ethernet-switching native-vlan-id 1

# Management access ports — Panel B (replace ge-0/0/? with actual port)
set interfaces ge-0/0/? unit 0 family ethernet-switching interface-mode access
set interfaces ge-0/0/? unit 0 family ethernet-switching vlan members default
```

---

## Panel B Port Assignments (Finalized)

| Port | Device | VLAN | Cable |
|---|---|---|---|
| 13 | R730 #1 iDRAC | 1 (Management) | 🔴 Red |
| 14 | R730 #2 iDRAC | 1 (Management) | 🔴 Red |
| 15 | SuperMicro IPMI | 1 (Management) | 🔴 Red |
| 16 | APC AP7901 PDU | 1 (Management) | 🔴 Red |
| 17 | Middle Atlantic UPS-OL2200R | 1 (Management) | 🔴 Red |
| 18–24 | Spare | — | — |
| 1–12 | Spare | — | — |

**Note:** Tripp-Lite SMART1500 is USB-managed only — no Panel B port needed. Monitor via NUT (Network UPS Tools) on a Proxmox node.

---

## OPNsense VLAN Configuration

**OPNsense VM:** VM 100 on pve2 (192.168.10.200)  
**LAN interface:** `vtnet1` → Proxmox `net1` → bridge `vmbr1`  
**vmbr1:** VLAN-aware ✅ (enabled this session)

### VLAN Sub-interfaces Created
Parent interface `vtnet1`, one per VLAN:

| Interface | Tag | IPv4 Address | DHCP Range |
|---|---|---|---|
| TRUSTED | 20 | 192.168.20.1/24 | .100 – .200 |
| SERVERS | 30 | 192.168.30.1/24 | .100 – .200 |
| IOT | 40 | 192.168.40.1/24 | .100 – .200 |
| VOIP | 50 | 192.168.50.1/24 | .100 – .200 |
| GUEST | 60 | 192.168.60.1/24 | .100 – .200 |
| LAB | 70 | 192.168.70.1/24 | .100 – .200 |

DHCP DNS: OPNsense Unbound resolver (temporarily). Update to Pi-hole IP once Pi-hole is restored.

### Firewall Alias
- **Name:** `LOCAL_NETS`
- **Type:** Network(s)
- **Content:** 192.168.10–70.0/24 (all seven subnets)

### Firewall Rules Summary

**TRUSTED:**
1. Pass → 192.168.10.0/24 (management access)
2. Pass → 192.168.30.0/24 (server access)
3. Block → LOCAL_NETS (isolates from IoT/VoIP/Guest/Lab)
4. Pass → any (internet)

**SERVERS:** Pass → any (internet + updates)

**IOT:** Block → LOCAL_NETS, Pass → any

**VOIP:** Pass → 192.168.30.0/24 (FreePBX), Block → LOCAL_NETS, Pass → any

**GUEST:** Block → LOCAL_NETS, Pass → any

**LAB:** Block → LOCAL_NETS, Pass → any

---

## Identified Devices on 192.168.10.0/24

| IP | Device | Notes |
|---|---|---|
| 192.168.10.1 | OPNsense | Gateway/router |
| 192.168.10.50 | KM-EX3400 | Juniper switch (irb.0) |
| 192.168.10.174 | SuperMicro CSE-219U | No hostname |
| 192.168.10.193 | UniFi Switch 24 PRO | Management IP |
| 192.168.10.199 | Ares | WiFi (wlp2s0) |
| 192.168.10.200 | pve2 | Proxmox node (OPNsense host) |

---

## Open Items

### Critical — VLANs not yet live

**Root cause:** pve2 (running OPNsense) is connected to the UniFi on what is likely an access port (VLAN 1 only). OPNsense's `vtnet1/vmbr1` cannot receive tagged VLAN traffic until pve2 has a trunk connection.

**Fix options (pick one):**

Option A — Move pve2 to EX3400 trunk port (recommended):
1. Run patch cable from pve2's NIC to an EX3400 `ge-0/0/X` port
2. Configure that port as trunk (all VLANs) on EX3400
3. VLANs flow directly: EX3400 → pve2 → OPNsense

Option B — Configure UniFi port for pve2 as trunk:
1. In UniFi controller, define VLANs 20-70 as networks
2. Set the UniFi port pve2 is on to carry all VLANs tagged
3. VLANs flow: EX3400 → trunk (ge-0/0/32) → UniFi → pve2 → OPNsense

### Other Open Items
- iDRAC cables not yet terminated (Panel B ports 13-17 physical runs pending)
- R730 #2 10G DAC (xe-0/2/2) link-down — EX3400 reads DAC as 10G, R730 NIC status unknown (couldn't access R730 #2 — Pi-hole down, not on Proxmox yet)
- EX3400 access port config pending (needs physical port numbers for Proxmox hosts, iDRAC, servers)
- Ares wired interface (`enp0s31f6`) currently DOWN — running on WiFi only
- Pi-hole offline — local DNS not resolving; DHCP pointing to OPNsense Unbound temporarily
- DHCP reservation for Ares in OPNsense (MAC `XX:XX:XX:XX:XX:XX`) — not yet created
- Device at 192.168.10.2 (MAC `XX:XX:XX:XX:XX:XX`) — unknown, needs identification
- pve2 connection to EX3400 trunk is the blocker for VLAN activation

---

## Next Session Priorities

1. Move pve2 to EX3400 trunk port OR configure UniFi trunk for pve2
2. Test VLAN connectivity (DHCP lease on VLAN 20 from a device on the Juniper)
3. Identify and configure EX3400 port numbers for Proxmox hosts and management devices
4. Terminate iDRAC cables to Panel B ports 13-17
5. Restore Pi-hole, update DHCP DNS servers to Pi-hole IP
6. Identify R730 #2 and investigate 10G DAC link issue
