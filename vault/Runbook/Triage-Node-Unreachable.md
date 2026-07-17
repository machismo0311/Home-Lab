# Triage: Node Unreachable

**Purpose:** distinguish *host down* from *NIC/link down* in minutes, remotely.
Written after the 2026-07-16 pve3 incident, where a hung NIC was misdiagnosed as
power loss for 13 hours (AAR: `AAR-2026-07-16-Pve3-Outage.md`). The two states
look identical from ping/ARP/WoL; only the switch knows the difference.

## Decision tree

1. **Confirm scope.** `ping <node>`, then `ip neigh show <ip>` from two other
   nodes (INCOMPLETE/FAILED = no ARP reply). Check `pvecm status` from a healthy
   node: sudden KNET link-down with no graceful leave = crash, power, or link;
   a clean member-leave = something shut it down.
2. **Check the netframe view.** All checks `UNREACHABLE` for the node (the
   collector distinguishes this from WARN since PR #63). The deterministic
   alerter should already have DM'd NODE DOWN.
3. **Check switch port link state - THE discriminating test.**
   Get EX3400 credentials from the **break-glass file** if Vaultwarden is down
   (`scripts/break-glass/breakglass-read.sh`), then:
   ```
   ssh mason@192.168.10.50
   show interfaces <port> terse            # up/up vs up/down
   show ethernet-switching table | match <MAC>
   show interfaces <port> extensive | match "Last flapped"
   ```
   - **Port up/up + MAC in table + node unpingable → NIC/driver hang or host
     network stack wedge. The box is probably RUNNING.** Do not assume power.
     (e1000e hang keeps the link up in some phases; a missing MAC with link up
     still means the PHY has power.)
   - **Port down → no link: powered off, cable, NIC PHY dead, or switch port.**
4. **Wake-on-LAN - know its limits.** WoL only works when the NIC is in a
   powered standby state (clean shutdown, S5 with AC). It does NOTHING if the
   box is running with a hung NIC, and usually nothing after total AC loss
   until the box has booted once. **WoL silence is NOT evidence of power loss.**
5. **If the box is likely running but off-net** (step 3 first bullet): guests on
   it are still serving their local state but unreachable; a power-button short
   press (physical) triggers a clean ACPI shutdown that also resets the NIC -
   then WoL works. R730s/Randy have iDRAC/IPMI on VLAN 20 instead (from Ares
   `enp0s31f6.20`); EliteDesks have no OOB.
6. **After any recovery:** health-check the WHOLE estate, not just the node -
   recovery actions are load, and load broke RKE2 on 2026-07-16.

## Node -> MAC -> switch port map (collected 2026-07-16)

| Node | Primary NIC MAC (VLAN 1) | Switch port | OOB |
|---|---|---|---|
| pve2 | b4:96:91:90:85:d4 | EX3400 (find via MAC table) | none |
| pve3 | c8:d9:d2:17:5c:d0 | EX3400 (find via MAC table) | none |
| pve4 | 10:62:e5:18:95:d7 | EX3400 (find via MAC table) | none |
| pve5 | ac:e2:d3:0e:50:4e | EX3400 (find via MAC table) | none |
| QuarkyLab | b0:83:fe:e5:ca:bc | ge-0/0/24 (trunk) | iDRAC 192.168.20.20 |
| Jarvis | 18:66:da:9e:ef:14 | ge-0/0/22 (native VLAN 1) | iDRAC 192.168.20.21 |
| Randy | f4:52:14:94:94:31 | xe-0/2/0 (trunk) | IPMI 192.168.20.22 |

Fill in the EliteDesk ports the next time each is confirmed on the switch
(`show ethernet-switching table | match <mac>` while the node is healthy) and
record them here.

## WoL one-liner (from any VLAN 1 node)

```bash
python3 -c "
import socket
mac = bytes.fromhex('MACHEXNOCOLONS')
pkt = b'\xff'*6 + mac*16
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
for port in (9, 7):
    s.sendto(pkt, ('192.168.10.255', port))
"
```
