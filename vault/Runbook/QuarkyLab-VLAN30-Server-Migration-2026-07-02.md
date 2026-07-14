# 🔀 Server VLAN 30 Migration - QuarkyLab · Randy · Jarvis
**Tags:** #runbook #network #vlan #proxmox #corosync #security #quarkylab
**Related:** [[Compute/Dell R730 - ML Node]] · [[Compute/Dell R730 - General Node]] · [[Infrastructure/Proxmox Cluster]] · [[Infrastructure/QuarkyLab Storage]] · [[Runbook/QuarkyLab-Operations]] · [[00 - Homelab MOC]]

Created **2026-07-02**. Migrates the three "enterprise" compute servers onto the **`servers` VLAN 30 (192.168.30.0/24)** for segmentation/security, **without leaving the km-cluster** and **without disrupting Wazuh, Pi-hole, or any monitoring VM**.

---

## Objective & hard constraints
- Move **QuarkyLab (.179)**, **Randy (.187)**, **Jarvis (.31)** onto VLAN 30 (`servers`).
- **Stay full km-cluster members** - corosync must remain healthy.
- **Wazuh (VM 104, 192.168.10.184) keeps monitoring every node.**
- **Pi-hole (192.168.10.177)** keeps serving DNS, including hosts on the new VLANs.
- **All monitoring VMs** (Prometheus/Grafana on pve3 `.183`, Scrutiny hub `.183:8080`, Wazuh) keep seeing the nodes.
- **Lowest possible downtime**; every step reversible. Nothing unrecoverable.

## Design decision (why this shape)
The three nodes are **corosync cluster members**. Proxmox's own docs say corosync needs a **dedicated, low-latency (<5 ms) network** and that you must **never hot-swap an active link's IP** ("add a new interface then remove the old - changing an active corosync interface causes split-brain"). Routing corosync between VLAN 1 and VLAN 30 through OPNsense would put the firewall in the cluster's critical path.

**Therefore corosync stays exactly where it is - on VLAN 1, untouched.** We **dual-home**: VLAN 1 becomes the *cluster + management + monitoring* network (directly connected, no changes), and VLAN 30 is **added** as the *servers' service + data + egress* network. Because VLAN 1 is retained as a directly-connected subnet, **every monitoring flow keeps working with zero config changes** (Prometheus/Wazuh/Scrutiny reach the nodes on their `.10.x` exactly as today; the nodes still reach Pi-hole `.10.177` directly).

**What actually rides each VLAN after migration:**
| Traffic | VLAN | Notes |
|---|---|---|
| Corosync / cluster (all 7 nodes) | **1** | untouched - zero cluster risk |
| Proxmox mgmt / SSH / iDRAC | **1** | `.10.x` retained (directly connected) |
| Wazuh agent→manager, Prometheus scrape, Scrutiny | **1** | unchanged, still works |
| Node → Pi-hole DNS | **1** | `.10.177` directly connected |
| Node internet egress (apt, ntp, tailscale) | **30** | via new default gw `.30.1` |
| Randy↔QuarkyLab NFS `/data` + PBS backup | **30** | isolated onto servers VLAN |
| Student/researcher/external access to services | **30** | reach `.30.x` |

> Proxmox refs: [Cluster Manager](https://pve.proxmox.com/wiki/Cluster_Manager) · [Separate Cluster Network](https://pve.proxmox.com/wiki/Separate_Cluster_Network). Corosync is deliberately NOT moved.

---

## Confirmed facts (recon 2026-07-02)
**Switch (EX3400 `192.168.10.50`, login `mason`):** VLAN `servers` = tag **30**, currently trunked **only** to uplink `ge-0/0/46` (→ UniFi US-24 → OPNsense, which owns gw `.30.1`). Node ports are access/native VLAN 1:

| Node | vmbr0 NIC MAC | Switch port | Link |
|---|---|---|---|
| QuarkyLab | `XX:XX:XX:XX:XX:XX` | **ge-0/0/24** | 1G |
| Randy | `XX:XX:XX:XX:XX:XX` | **xe-0/2/0** | 10G |
| Jarvis | `XX:XX:XX:XX:XX:XX` | **ge-0/0/22** | 1G |

- **Wazuh VM 104** (`XX:XX:XX:XX:XX:XX`) is learned on QuarkyLab's port `ge-0/0/24` - it rides that port's **native** VLAN, so keeping native VLAN 1 on the trunk keeps VM 104 on VLAN 1 unchanged.
- QuarkyLab has a **spare 10G link up on `xe-0/2/3`** (OS NIC down) - future option, not used here.
- Existing couplings to re-point: Randy exports `/datastore/quarkylab` → `192.168.10.179`; QuarkyLab fstab mounts `192.168.10.187:/datastore/quarkylab`; QuarkyLab PBS storage `randy-pbs` → `server 192.168.10.187` (fingerprint unchanged on re-IP).

## Target addressing (static, same host octet)
| Node | VLAN 1 (keep) | VLAN 30 (add) |
|---|---|---|
| QuarkyLab | 192.168.10.179/24 | **192.168.30.179/24** |
| Randy | 192.168.10.187/24 | **192.168.30.187/24** |
| Jarvis | 192.168.10.31/24 | **192.168.30.31/24** |
| Gateway | (removed from vmbr0) | **192.168.30.1** (default) |

## Safety nets (always available)
1. **iDRAC/IPMI on VLAN 1** - QuarkyLab `.10.20`, Jarvis `.10.21`, Randy `.10.22`. On-site console survives any OS-network change.
2. **Tailscale up on all three** - QuarkyLab `100.x.x.x`, Randy `100.64.0.2`, Jarvis `100.64.0.6`. Survives LAN re-IP as long as egress works.
3. **Admin SSH is same-subnet** (from VLAN 1 `.199`) → reaches nodes' `.10.x` **directly**, so the default-gateway swap can never lock us out.
4. **Corosync untouched** → the cluster is never at risk at any step.

---

## Phase 0 - Pre-flight (read-only, no downtime)
Run and record baselines; do not proceed unless all green.
```bash
# Cluster healthy + quorate
ssh quarkylab 'pvecm status | egrep -i "Quorate|Nodes|Total votes"; corosync-cfgtool -s'
# Current net + mounts on each
for h in quarkylab randy jarvis; do echo "== $h =="; ssh $h 'ip -br a; ip r'; done
ssh quarkylab 'mount | grep /data; pvesm status | grep randy-pbs'
# Lifelines reachable
ping -c1 192.168.10.20 && ping -c1 192.168.10.21 && ping -c1 192.168.10.22   # iDRAC/IPMI
for h in quarkylab randy jarvis; do ssh $h 'tailscale status | head -1'; done
# VLAN 30 gateway reachable, subnet ready in OPNsense
ping -c2 192.168.30.1
# Fresh backup of QuarkyLab workspace exists (daily 01:30) - or run now:
ssh quarkylab 'systemctl start pbs-workspace-backup.service; journalctl -u pbs-workspace-backup -n5 --no-pager'
# Note Wazuh baseline
ssh quarkylab 'curl -sk -o /dev/null -w "wazuh_dash=%{http_code}\n" https://192.168.10.184/'
```
**Gate:** cluster Quorate=Yes, all 3 iDRACs ping, all 3 Tailscale up, `.30.1` pings, backup OK.

---

## Phase 1 - Switch: trunk VLAN 30 to the three node ports (additive)
Keeps native VLAN 1 (mgmt/corosync/Wazuh-VM stay untagged on VLAN 1) and adds tagged VLAN 30. Uses **`commit confirmed`** so the switch auto-reverts if we lose the nodes.
```
# ssh mason@192.168.10.50 ; then: configure
# QuarkyLab  ge-0/0/24  (currently implicit access/default)
set interfaces ge-0/0/24 unit 0 family ethernet-switching interface-mode trunk
set interfaces ge-0/0/24 unit 0 family ethernet-switching vlan members default
set interfaces ge-0/0/24 unit 0 family ethernet-switching vlan members servers
set interfaces ge-0/0/24 native-vlan-id 1
# Randy  xe-0/2/0  (currently implicit access/default)
set interfaces xe-0/2/0 unit 0 family ethernet-switching interface-mode trunk
set interfaces xe-0/2/0 unit 0 family ethernet-switching vlan members default
set interfaces xe-0/2/0 unit 0 family ethernet-switching vlan members servers
set interfaces xe-0/2/0 native-vlan-id 1
# Jarvis  ge-0/0/22  (currently explicit access/default → just override mode + add member)
set interfaces ge-0/0/22 unit 0 family ethernet-switching interface-mode trunk
set interfaces ge-0/0/22 unit 0 family ethernet-switching vlan members servers
set interfaces ge-0/0/22 native-vlan-id 1
# Commit with a 5-minute dead-man switch:
commit confirmed 5
```
**Verify (from admin box, within 5 min):** all three still reachable on VLAN 1 -
```bash
for ip in 192.168.10.179 192.168.10.187 192.168.10.31; do ping -c2 $ip; done
ssh quarkylab 'pvecm status | grep -i quorate'   # still Quorate: Yes
```
- **Good →** back on the switch: `commit` (or `commit check` then `commit`) to make it permanent.
- **Bad / no output →** do nothing; the switch **auto-rolls back in 5 min**. Or `rollback 0; commit`.

**Rollback (manual):** `configure; rollback 1; commit` - or delete the added `interface-mode trunk` / `servers` member and restore access.

---

## Phase 2 - Nodes: add VLAN 30 interface + move default gateway (additive)
For each node, append a `vmbr0.30` stanza and **remove only the `gateway` line from `vmbr0`** (the `.10.x` address stays; VLAN 1 is directly connected so it keeps working without a default route). Admin SSH is same-subnet → the gateway swap cannot drop the session.

**QuarkyLab** `/etc/network/interfaces` - remove `gateway 192.168.10.1` from vmbr0, then add:
```
auto vmbr0.30
iface vmbr0.30 inet static
	address 192.168.30.179/24
	gateway 192.168.30.1
```
**Randy** → `address 192.168.30.187/24`, gw `192.168.30.1`.
**Jarvis** → `address 192.168.30.31/24`, gw `192.168.30.1`.

Apply (per node), lowest-downtime - VLAN 1 address is untouched so mgmt stays up:
```bash
ssh <node> 'ifreload -a && ip -br a | grep vmbr0 && ip r | grep default'
```
**Verify:**
```bash
# new IP up, default now via .30.1
for h in quarkylab randy jarvis; do ssh $h 'ip -br a | grep "vmbr0.30"; ip r | grep default'; done
# node-to-node on VLAN 30
ssh quarkylab 'ping -c2 192.168.30.187; ping -c2 192.168.30.31; ping -c2 192.168.30.1'
# egress + DNS still work (Pi-hole on VLAN 1 is directly connected)
ssh quarkylab 'getent hosts github.com; ping -c2 1.1.1.1'
# monitoring plane untouched - still reachable on VLAN 1
for ip in 192.168.10.179 192.168.10.187 192.168.10.31; do ping -c1 $ip; done
```
**Rollback (per node):** delete the `vmbr0.30` stanza, restore `gateway 192.168.10.1` on vmbr0, `ifreload -a`. (If ever unreachable: iDRAC console or `ssh <tailscale-ip>`.)

> ⚠️ Do the nodes **one at a time**, verifying each before the next. QuarkyLab last is safest (it hosts Wazuh VM 104).

---

## Phase 3 - Pi-hole / DNS for VLAN 30 (OPNsense GUI)
The **nodes** already resolve via Pi-hole over VLAN 1 (direct). This covers **other** hosts that live on VLAN 30.
- OPNsense → Services → DHCPv4 → **VLAN 30**: set DNS server = **192.168.10.177**; exclude `.179/.187/.31` from the pool (static).
- OPNsense → Firewall → Rules → **VLAN 30**: allow `VLAN30 net → 192.168.10.177  proto UDP/TCP  port 53`.
- **Verify** from a VLAN 30 host: `dig @192.168.10.177 example.com +short`.

## Phase 4 - Move inter-server storage & backup onto VLAN 30 (low-downtime cutover)
Both endpoints (Randy + QuarkyLab) are now on VLAN 30 → this traffic stays on the switch L2 (no routing). Add-new-then-remove-old.

**Randy - add VLAN 30 export (keep old line until verified):**
```bash
ssh randy 'printf "/datastore/quarkylab 192.168.30.179(rw,sync,no_subtree_check,no_root_squash)\n" >> /etc/exports && exportfs -ra && exportfs -v | grep quarkylab'
```
**QuarkyLab - repoint the mount** (base.sif runs from the LOCAL copy, so a brief `/data` gap is safe; ensure no job is mid-read of `/data`):
```bash
ssh quarkylab 'sed -i "s#192.168.10.187:/datastore/quarkylab#192.168.30.187:/datastore/quarkylab#" /etc/fstab && umount /data && mount /data && mount | grep /data'
```
**QuarkyLab - repoint PBS** (fingerprint unchanged - same cert):
```bash
ssh quarkylab 'sed -i "s/server 192.168.10.187/server 192.168.30.187/" /etc/pve/storage.cfg && pvesm status | grep randy-pbs'
ssh quarkylab 'systemctl start pbs-workspace-backup.service; journalctl -u pbs-workspace-backup -n8 --no-pager'   # test backup over VLAN 30
```
**Then retire the old VLAN 1 export** (only after the above is green):
```bash
ssh randy 'sed -i "\#192.168.10.179(rw,sync#d" /etc/exports && exportfs -ra && exportfs -v | grep quarkylab'
```
**Rollback:** revert fstab to `192.168.10.187:...` + `umount/mount /data`; revert `storage.cfg` server to `.10.187`; the `.10.179` export line is still present until the retire step.

## Phase 5 - Verify monitoring end-to-end (no changes expected - just confirm)
```bash
# Wazuh VM 104 still on VLAN 1, healthy, agents for all nodes reporting
ssh quarkylab 'curl -sk -o /dev/null -w "dash=%{http_code}\n" https://192.168.10.184/'      # expect 302
ssh quarkylab 'qm config 104 | grep -i net; qm status 104'                                   # VM up, bridged vmbr0 (native VLAN1)
# (from Wazuh) agent_control -l shows quarkylab/randy/jarvis Active
# Prometheus still scraping the 3 nodes on .10.x:9100
curl -s 'http://192.168.10.183:9090/api/v1/targets' | grep -oE '"instance":"(quarkylab|randy|jarvis)[^"]*"[^}]*"health":"[a-z]+"'
# Grafana dashboard live
curl -s -o /dev/null -w "grafana=%{http_code}\n" http://192.168.10.183:3000/d/quarkylab-gpu/quarkylab-gpu-cluster
# Scrutiny collectors still posting to .183:8080 (check hub UI)
```
**Gate:** Wazuh dash 302 + agents Active for all 3; Prometheus 3 targets `up`; Grafana 200. All of this rides VLAN 1 and should be unchanged.

---

## OPNsense firewall matrix (apply/confirm in GUI)
Monitoring stays on VLAN 1 (pull to nodes' `.10.x`, directly connected) → **no rule needed**. Corosync all VLAN 1 → **no rule needed**. Only VLAN-30-originated flows need rules:
| Source | Destination | Port | Purpose |
|---|---|---|---|
| VLAN30 net | 192.168.10.177 | 53 UDP/TCP | Pi-hole DNS |
| VLAN30 net | (WAN) | any | egress: apt / ntp / tailscale |
| trusted (20) / lab (70) as needed | 192.168.30.179 | 22 + app ports | student / researcher access to QuarkyLab |
| VLAN1 admin (`.199`) | VLAN30 net | any | admin reach to `.30.x` (optional) |

## Master rollback (worst case, fully reversible)
1. **Storage:** revert fstab + `storage.cfg` to `.10.187`; restore Randy `.10.179` export.
2. **Nodes:** delete `vmbr0.30`, restore `gateway 192.168.10.1` on `vmbr0`, `ifreload -a`.
3. **Switch:** `configure; rollback 1; commit` (ports back to access VLAN 1).
4. **Corosync/cluster:** never touched - nothing to undo.
5. **If locked out:** iDRAC console (`.10.20/.21/.22`) or `ssh <tailscale-ip>`.

## Post-migration follow-ups
- Update vault: [[Compute/Dell R730 - ML Node]], [[Compute/Dell R730 - General Node]], [[Infrastructure/QuarkyLab Storage]], [[Runbook/QuarkyLab-Operations]] with the new `.30.x` service IPs (keep `.10.x` mgmt IPs documented).
- Update memory `project-quarkylab-student-env` / `project-homelab` with dual-home layout + storage now on VLAN 30.
- Update `~/.ssh/config` if any host alias hard-codes `.10.x` for a service that moved (mgmt aliases stay `.10.x`).
- Consider (future, out of scope): full isolation removing the VLAN 1 footprint would require moving corosync via the documented *add-link-then-remove-link* dance - a separate, gated change.
