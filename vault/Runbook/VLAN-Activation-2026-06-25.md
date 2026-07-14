# VLAN Activation - COMPLETE
**Date:** 2026-06-25
**Status:** ✅ **DONE** - VLAN trunking live, verified end-to-end via DHCP lease on VLAN 20
**Follows:** `EX3400-Network-Buildout-2026-06-14.md`

---

## Result

VLAN trunking is fully operational. A test device on tagged VLAN 20 received a DHCP
lease (`192.168.20.100`) from OPNsense (`192.168.20.1`), proving the complete path:

```
EX3400 ge-0/0/46 (trunk) → UniFi Port 24 → UniFi Port 14 → pve2 vmbr1 (VLAN-aware)
   → OPNsense vtnet1.20 → DHCP → lease ✅
```

Management (untagged VLAN 1) stays fully stable with the trunk active.

---

## The Root Cause (why it took several attempts)

**`native-vlan-id` must be at the PHYSICAL INTERFACE level on JunOS ELS - not under
`unit 0 family ethernet-switching`.**

```
✗ WRONG - accepted by JunOS without error, but does NOT drive untagged egress:
   set interfaces ge-0/0/46 unit 0 family ethernet-switching native-vlan-id 1

✓ CORRECT (EX3400 / JunOS ELS 23.4):
   set interfaces ge-0/0/46 native-vlan-id 1
```

With the wrong placement, the trunk tagged *every* VLAN including VLAN 1. The UniFi
switch (which expects untagged native VLAN 1 on its uplink) then lost its own management,
taking down everything behind it (pve2, OPNsense). The "commit complete" with no error
masked the problem.

Secondary issue: **pve2 nic2/vmbr2** - an unused bridge with a live cable to the UniFi -
created an L2 loop that melted the *entire* network on early attempts. Disabled (below).

---

## Final Working Config

### EX3400 ge-0/0/46 (uplink to UniFi, confirmed via LLDP → UniFi Port 24)
```
native-vlan-id 1;                      ← interface level (the key fix)
unit 0 {
    family ethernet-switching {
        interface-mode trunk;
        vlan {
            members [ default trusted servers iot voip guest lab ];
        }
    }
}
```

### UniFi US-24-250W (verified correct)
| Port | Connects to | Native VLAN | Tagged |
|---|---|---|---|
| Port 24 | EX3400 ge-0/0/46 | Default (1) | Allow All |
| Port 14 | OPNsense / pve2 | Default (1) | Allow All |

### pve2
- `vmbr1`: `bridge-vlan-aware yes` (requires full reboot to apply - `ifreload -a` insufficient)
- VM 100 (OPNsense) `net1`: `trunks=1-70`
- `vmbr2`/`nic2`: **auto-start disabled** in `/etc/network/interfaces` - unused bridge,
  live UniFi cable caused the trunk loop. Kept down persistently.

---

## End-to-End Verification (reproducible)
```bash
ssh pve2 "
  bridge vlan add dev vmbr1 vid 20 self
  ip link add link vmbr1 name vmbr1.20test type vlan id 20
  ip link set vmbr1.20test up
  dhclient -1 -v vmbr1.20test          # → bound to 192.168.20.100 ✅
  dhclient -r vmbr1.20test; ip link del vmbr1.20test
  bridge vlan del dev vmbr1 vid 20 self
"
```

---

## Safety Notes
- **Keep Ares wired (enp0s31f6, 192.168.10.100) during any pve2/OPNsense/EX3400 work** -
  Ares WiFi is on the WAN side; an OPNsense outage cuts the management network from WiFi.
- **Use `commit confirmed 5` on the EX3400** for any risky change - auto-reverts in 5 min.
- **Do not re-enable vmbr2/nic2** without removing its UniFi cable first - it loops the trunk.
- `native-vlan-id` goes at the **interface level** on this EX3400 (ELS).

---

## Next (now unblocked)
- Move IoT devices to VLAN 40 (Fire Tablet, Echo ×5, BBL strip - pentest F-07/09/10)
- Move Transmission client to VLAN 40
- Decide permanent fate of nic2 cable (remove or repurpose)

---

## Post-Activation Fix: Tagged VLANs Not Reaching OPNsense from Network (2026-06-25)

**Symptom:** Management (VLAN 1) worked, but WiFi IoT devices on the VLAN 40 SSID
failed DHCP ("failed to obtain IP").

**Cause:** pve2's VLAN-aware bridge `vmbr1` had VLANs 20-70 on the OPNsense VM port
(`tap100i1`, from `trunks=1-70`) but the **physical uplink `nic1` was a member of VLAN 1
only**. Tagged VLAN frames arriving from the network (AP → UniFi → nic1) were dropped at
the bridge before reaching OPNsense. The earlier VLAN-20 DHCP test passed only because it
originated inside the bridge and never traversed nic1.

**Fix (runtime + persistent):**
```bash
# Runtime (immediate):
ssh pve2 "for v in 20 30 40 50 60 70; do bridge vlan add dev nic1 vid \$v; done"

# Persistent - add to vmbr1 in /etc/network/interfaces:
#     bridge-vlan-aware yes
#     bridge-vids 2-4094        ← makes the uplink carry all VLANs
#     bridge-fd 0
```

**Verify:** `bridge vlan show dev nic1` → should list 20,30,40,50,60,70.
Confirmed working: Fire Tablet obtained a VLAN 40 (IoT) lease on the IoT SSID.

**Note:** `bridge-vids` is config-only until next reboot/ifreload; runtime `bridge vlan add`
keeps it live in the meantime. Did NOT run `ifreload` to avoid disrupting active migration.
