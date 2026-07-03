# 🧭 Runbook Template — Migrate a Node to a VLAN (dual-home pattern)
**Tags:** #runbook #template #network #vlan #proxmox #corosync
**Related:** [[Runbook/VLAN30-Migration-Report-2026-07-02]] · [[Runbook/QuarkyLab-VLAN30-Server-Migration-2026-07-02]] · [[Networking/Network Overview]] · [[Infrastructure/Proxmox Cluster]] · [[00 - Homelab MOC]]

A reusable, low-downtime procedure for moving **any** km-cluster node onto a tagged VLAN while keeping it in the cluster and preserving monitoring. Proven on QuarkyLab/Randy/Jarvis (2026-07-02). **Read the whole runbook before starting.** Fill the placeholders `<...>` first.

> **Golden rule:** never move Corosync across a routed VLAN. Keep the cluster ring on its stable VLAN 1 L2 network. This template **dual-homes** — VLAN 1 stays for cluster/mgmt/monitoring; the new VLAN is *added* for service/data/egress.

## Fill-in parameters
| Param | Value |
|---|---|
| Node hostname | `<node>` |
| Node VLAN 1 (mgmt) IP — **kept** | `192.168.10.<m>` |
| New VLAN id / name | `<VID>` / `<name>` |
| New VLAN subnet / gateway | `192.168.<VID>.0/24` / `192.168.<VID>.1` |
| New node IP | `192.168.<VID>.<m>` |
| Bridge / uplink NIC | `vmbr0` / `<nicX>` |
| Switch port (from MAC table) | `<ge-0/0/xx or xe-0/2/x>` |
| iDRAC/IPMI (VLAN 1) | `192.168.10.<i>` |
| Coupled services (NFS/PBS/app IPs) | `<list>` |

## Pre-flight (read-only — gate before any change)
```bash
ssh <node> 'pvecm status | egrep -i "Quorate|Total votes"'         # must be Quorate
ping -c1 192.168.10.<i>                                             # iDRAC lifeline UP
ssh <node> 'tailscale ip -4 | head -1'                             # out-of-band lifeline
ping -c2 192.168.<VID>.1                                            # new VLAN gateway reachable
# Identify the switch port: match the node vmbr0 MAC in the EX3400 MAC table
#   ssh mason@192.168.10.50 'show ethernet-switching table | match <mac>'
ssh <node> 'squeue -h 2>/dev/null | wc -l'                         # prefer 0 running jobs
```
**Gate:** Quorate=Yes, iDRAC pings, Tailscale up, new gateway pings. Confirm a recent backup exists.

## Step 1 — Switch: trunk the new VLAN to the node port (additive)
EX3400 (`mason@192.168.10.50`), use `commit confirmed` as a dead-man switch:
```
configure
set interfaces <port> unit 0 family ethernet-switching interface-mode trunk
set interfaces <port> unit 0 family ethernet-switching vlan members default
set interfaces <port> unit 0 family ethernet-switching vlan members <name>
set interfaces <port> native-vlan-id 1
show | compare
commit confirmed 5
```
**Verify within 5 min** (from a VLAN 1 admin host): `ping 192.168.10.<m>` still works and `ssh <node> pvecm status` is Quorate. **Good →** `commit`. **Bad →** do nothing; auto-rolls back in 5 min (or `rollback 0; commit`).
> Native VLAN 1 stays untagged, so the node's mgmt IP and any VM on the native VLAN are unaffected.

## Step 2 — Node: add the VLAN interface + move default gateway (additive)
Edit `/etc/network/interfaces`: **remove only** the `gateway 192.168.10.1` line from `vmbr0` (keep its address), then append:
```
auto vmbr0.<VID>
iface vmbr0.<VID> inet static
	address 192.168.<VID>.<m>/24
	gateway 192.168.<VID>.1
```
```bash
ssh <node> 'cp /etc/network/interfaces /etc/network/interfaces.bak-$(date +%s); <edits>; ifreload -a'
```
**Verify:**
```bash
ssh <node> 'ip -br a | grep vmbr0.<VID>; ip r | grep default'      # default now via .<VID>.1
ssh <node> 'ping -c2 192.168.<VID>.1; getent hosts github.com; ping -c2 1.1.1.1'  # gw, DNS, egress
ping -c2 192.168.10.<m>                                             # VLAN 1 mgmt still UP
ssh <node> 'pvecm status | grep -i quorate'                        # still Quorate
```
> The node keeps `192.168.10.<m>` (directly-connected), so DNS to Pi-hole `.10.177` and all VLAN-1 monitoring are unaffected. Admin SSH from a VLAN 1 host is same-subnet, so the gateway swap cannot lock you out. **Do one node at a time; do a VM-hosting node last.**

## Step 3 — Re-home coupled services to the new VLAN (add-before-remove)
For each hardcoded coupling (NFS export/mount, PBS repo, app configs), **add** the new-VLAN endpoint, verify, then **remove** the old. Sweep for stragglers:
```bash
ssh <node> 'grep -rIn "192.168.10.<peer>" /etc/fstab /etc/pve/storage.cfg /usr/local/sbin /etc/exports 2>/dev/null'
```
NFS example: add `... 192.168.<VID>.<client>(...)` to the server's `/etc/exports` (`exportfs -ra`), repoint the client `fstab` to `192.168.<VID>.<server>`, remount at idle, then drop the old export. PBS: update `storage.cfg` server IP (fingerprint unchanged) **and** any script-level `PBS_REPOSITORY`. Run one real backup to prove the new path.

## Step 4 — Verify monitoring end-to-end (expect no change)
```bash
curl -s -o /dev/null -w "%{http_code}\n" http://192.168.10.183:9100/metrics   # node_exporter (via VLAN1)
# Grafana→Prometheus: up{instance="<node>"} should be 1 (query via datasource proxy)
ssh <node> 'systemctl is-active wazuh-agent'                                    # active
# Scrutiny hub shows the node's disks (install collector if absent — see report)
```

## Step 5 — OPNsense (operator, GUI) for other clients on the new VLAN
- DHCP: DNS = `192.168.10.177` (Pi-hole); reserve/exclude static node IPs.
- Firewall: allow `<VID> net → 192.168.10.177:53`; egress; and any client-VLAN → node service ports.

## Rollback (any step, fully reversible)
1. Services: revert `fstab`/`storage.cfg`/scripts to `.10`; restore old export.
2. Node: delete `vmbr0.<VID>`, restore `gateway 192.168.10.1`, `ifreload -a`.
3. Switch: `rollback 1; commit`.
4. Cluster: untouched — nothing to undo.
5. Lockout: iDRAC console (`192.168.10.<i>`) or `ssh <tailscale-ip>`.

## Do / Don't
- ✅ Keep Corosync on VLAN 1; add the new VLAN; verify each step before the next.
- ✅ Use `commit confirmed`; back up every file you touch; sweep for hardcoded IPs.
- ❌ Don't re-IP an active corosync link. ❌ Don't drive the change over the SSH path whose IP you're changing. ❌ Don't put secrets in the (public) vault — use Vaultwarden.
