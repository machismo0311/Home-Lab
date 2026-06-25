# VLAN Activation — Session Notes
**Date:** 2026-06-25  
**Status:** 🟡 In Progress — pve2 bridge and OPNsense VM fully prepared; blocked on UniFi switch port config  
**Follows:** `EX3400-Network-Buildout-2026-06-14.md`

---

## Session Summary

Partial VLAN activation. The Proxmox/OPNsense side is now fully configured for VLAN trunking. The blocker is the UniFi switch — pve2's port on the UniFi needs to be set to a VLAN trunk profile before the EX3400 uplink can be trunked.

---

## Topology Discovery (Critical)

The actual path from EX3400 to pve2 (confirmed via MAC table lookup on EX3400):

```
EX3400 ge-0/0/46 → UniFi USW-24-250W → (port) → pve2 nic1
```

pve2 is **not directly connected to the EX3400**. It connects via the UniFi switch. The EX3400 only sees pve2's MAC (`b4:96:91:90:85:d4`) through ge-0/0/46 (the EX3400→UniFi uplink).

**Implication:** The UniFi switch must be configured to trunk VLANs on pve2's port before the EX3400 uplink goes trunk. If EX3400 sends tagged frames to the UniFi and the UniFi's port for pve2 is still an access port, all tagged traffic is dropped inside the UniFi — pve2 never sees it, and VLAN 1 untagged connectivity also breaks.

---

## What Was Completed This Session

### ✅ pve2 vmbr1 — Now VLAN-Aware

Required a **full pve2 reboot** (`ifreload -a` was insufficient — it runs but doesn't apply `vlan_filtering=1` to the running bridge).

`/etc/network/interfaces` on pve2:
```
auto vmbr1
iface vmbr1 inet static
       address 192.168.10.204/24
       gateway 192.168.10.1
       bridge-ports nic1
       bridge-stp off
       bridge-vlan-aware yes
       bridge-fd 0
```

**Verified after reboot:**
```
ip -d link show vmbr1 | grep vlan_filtering
# → vlan_filtering 1  ✅
```

VLAN 1 is the PVID on all ports (native untagged) by default:
```
bridge vlan show
# → nic1: 1 PVID Egress Untagged
# → vmbr1: 1 PVID Egress Untagged
# → tap100i0/i1: 1 PVID Egress Untagged
```

### ✅ OPNsense VM 100 net1 — Trunk Mode Set

```bash
qm set 100 --net1 virtio=BC:24:11:12:30:00,bridge=vmbr1,trunks=1-70
```

**Verified in `/etc/pve/nodes/pve2/qemu-server/100.conf`:**
```
net1: virtio=BC:24:11:12:30:00,bridge=vmbr1,trunks=1-70
```

OPNsense's vtnet1 now receives tagged traffic for VLANs 1-70. OPNsense's internal VLAN subinterfaces (TRUSTED/20, SERVERS/30, IOT/40, etc.) were configured in the June 14 session — no changes needed there.

### ❌ EX3400 ge-0/0/46 — Rolled Back to Access Port

**Attempted trunk config:**
```
set interfaces ge-0/0/46 unit 0 family ethernet-switching interface-mode trunk
set interfaces ge-0/0/46 unit 0 family ethernet-switching vlan members [all VLANs]
set interfaces ge-0/0/46 unit 0 family ethernet-switching native-vlan-id 1
```

**Result:** Broke connectivity — pve2, OPNsense, and all management network devices became unreachable from Ares (Ares routes through OPNsense). Root cause: UniFi switch port for pve2 is still access mode; tagged frames were dropped inside the UniFi before reaching pve2.

**Rolled back to access port:**
```
delete interfaces ge-0/0/46 unit 0 family ethernet-switching
set interfaces ge-0/0/46 unit 0 family ethernet-switching interface-mode access
set interfaces ge-0/0/46 unit 0 family ethernet-switching vlan members default
commit
```

Current state: ge-0/0/46 is access/VLAN 1 — same as before.

---

## What Remains

### Step 1 — UniFi Controller (USER ACTION — cannot automate, uses Ubiquiti SSO)

Log into UniFi Network controller (`https://192.168.10.2:8443`).

**Configure pve2's port on the UniFi switch:**
1. Devices → select the UniFi USW-24-250W
2. Find the port pve2 is plugged into (look for MAC `b4:96:91:90:85:d4`)
3. Set port profile to **All** (trunk all VLANs) or create a custom profile with VLANs 1,20,30,40,50,60,70

**Also configure ge-0/0/32 port on the UniFi** (the EX3400 uplink):
- This was already set as trunk on the EX3400 side (from the June 14 session)
- The UniFi side of this link also needs to accept all VLANs tagged (set to All/trunk profile)

### Step 2 — Re-apply EX3400 ge-0/0/46 Trunk (once UniFi is configured)

```bash
ssh switch << 'EOF'
configure
set interfaces ge-0/0/46 unit 0 family ethernet-switching interface-mode trunk
set interfaces ge-0/0/46 unit 0 family ethernet-switching vlan members default
set interfaces ge-0/0/46 unit 0 family ethernet-switching vlan members trusted
set interfaces ge-0/0/46 unit 0 family ethernet-switching vlan members servers
set interfaces ge-0/0/46 unit 0 family ethernet-switching vlan members iot
set interfaces ge-0/0/46 unit 0 family ethernet-switching vlan members voip
set interfaces ge-0/0/46 unit 0 family ethernet-switching vlan members guest
set interfaces ge-0/0/46 unit 0 family ethernet-switching vlan members lab
set interfaces ge-0/0/46 unit 0 family ethernet-switching native-vlan-id 1
commit and-quit
EOF
```

### Step 3 — Test VLAN Connectivity

```bash
# OPNsense VLAN gateways should respond
ping 192.168.20.1   # TRUSTED
ping 192.168.30.1   # SERVERS
ping 192.168.40.1   # IOT
ping 192.168.50.1   # VOIP
ping 192.168.60.1   # GUEST
ping 192.168.70.1   # LAB

# Request a DHCP lease on VLAN 20 from a wired device
# (requires a device connected to a VLAN 20 access port on the EX3400 or UniFi)
```

---

## Network State (Current)

| Component | State |
|---|---|
| pve2 vmbr1 | ✅ VLAN-aware (`vlan_filtering=1`) |
| OPNsense VM 100 net1 | ✅ `trunks=1-70` |
| OPNsense VLAN subinterfaces | ✅ Pre-configured (June 14) |
| OPNsense DHCP per VLAN | ✅ Pre-configured (June 14) |
| OPNsense firewall rules per VLAN | ✅ Pre-configured (June 14) |
| EX3400 VLANs defined | ✅ Pre-configured (June 14) |
| EX3400 ge-0/0/32 trunk (→UniFi) | ✅ Pre-configured (June 14) |
| EX3400 ge-0/0/46 trunk (→pve2 via UniFi) | ❌ **Rolled back — pending UniFi port config** |
| UniFi port for pve2 | ❌ **Still access port — USER ACTION NEEDED** |
| UniFi port for ge-0/0/32 (EX3400 uplink) | ❌ **Needs trunk profile — USER ACTION NEEDED** |

---

## Safety Notes

- **Ares's management network path goes through OPNsense** — Ares's WiFi is on the WAN side (192.168.1.x). Any OPNsense outage makes the entire 192.168.10.x management network unreachable from Ares via WiFi.
- **Keep Ares's wired cable plugged in during any future pve2/OPNsense work** — the wired interface `enp0s31f6` at `192.168.10.100` provides a direct L2 path to the management network that bypasses OPNsense routing.
- **Do NOT trunk ge-0/0/46 on EX3400 before configuring the UniFi port for pve2** — doing so breaks VLAN 1 connectivity through the UniFi switch.
- **`ifreload -a` is NOT sufficient for `bridge-vlan-aware`** — a full pve2 reboot is required for `vlan_filtering=1` to take effect on vmbr1.
