# 📄 Technical Report - Server VLAN 30 Migration (QuarkyLab · Randy · Jarvis)
**Tags:** #report #network #vlan #proxmox #corosync #security #changerecord
**Related:** [[Runbook/QuarkyLab-VLAN30-Server-Migration-2026-07-02]] · [[Runbook/Node-VLAN-Migration-Template]] · [[Infrastructure/QuarkyLab Storage]] · [[Compute/Dell R730 - ML Node]] · [[Compute/Dell R730 - General Node]] · [[Networking/Network Overview]] · [[00 - Homelab MOC]]

| | |
|---|---|
| **Change ID** | NET-2026-07-02-VLAN30 |
| **Date executed** | 2026-07-02 |
| **Author / operator** | K. Mason (with Claude Code) |
| **Systems** | QuarkyLab (R730), Randy (SuperMicro), Jarvis (R730); EX3400; OPNsense |
| **Change type** | Network segmentation - additive, reversible |
| **Maintenance window** | Authorized; 0 SLURM jobs running |
| **Result** | ✅ Success - no unplanned downtime, cluster quorum preserved throughout |

---

## 1. Executive summary
The three "enterprise" compute servers - **QuarkyLab** (ML/GPU), **Randy** (PBS/storage), and **Jarvis** (LLM) - were migrated onto the dedicated **`servers` VLAN 30 (192.168.30.0/24)** for network segmentation and security. To satisfy the hard requirement that the nodes **remain km-cluster members** and that **Wazuh, Pi-hole, and all monitoring continue to function**, the migration used a **dual-homed** design: the Corosync cluster/management/monitoring plane was left **untouched on VLAN 1**, while VLAN 30 was **added** as the servers' service, storage, and internet-egress network. No corosync reconfiguration was performed; the cluster stayed quorate (7/7) at every step.

## 2. Background & objective
The servers were originally provisioned on the flat management VLAN 1 (192.168.10.0/24). The objective was to place them in the pre-built `servers` segment (VLAN 30) to (a) isolate their service/data/egress traffic from the general management LAN and (b) provide a controlled security boundary for multi-tenant student GPU workloads on QuarkyLab - **without** re-architecting the Proxmox cluster or disrupting observability.

## 3. Scope
**In scope:** VLAN 30 network attachment for the 3 nodes; default-route/egress move; inter-server NFS + PBS re-homing to VLAN 30; monitoring verification; Jarvis Scrutiny install; QuarkyLab splash correction.
**Out of scope (deliberately):** moving Corosync off VLAN 1; migrating pve1–pve5; removing the nodes' VLAN 1 presence (full isolation); OPNsense DNS firewall rule for *other* VLAN-30 clients (handed to operator as Phase 3).

## 4. Design & architecture
**Governing constraint - Corosync.** Proxmox VE documents that the cluster stack needs a **dedicated, low-latency (<5 ms) network** and that you must **never change an active corosync link's IP** ("add a new interface, then remove the old - changing an active link causes split-brain"). Routing corosync between VLAN 1 and VLAN 30 would insert OPNsense (a VM on pve2) into the cluster's critical path. **Decision: Corosync remains on VLAN 1, unchanged.**

**Dual-home model.** VLAN 1 is retained as a directly-connected *cluster + management + monitoring* subnet; VLAN 30 is added as the *service/data/egress* network. Because VLAN 1 stays directly connected, **every VLAN-1 monitoring flow keeps working with zero configuration change**.

| Traffic | VLAN | Change |
|---|---|---|
| Corosync / cluster (7 nodes) | 1 | none (untouched) |
| Proxmox mgmt / SSH / iDRAC | 1 | none (`.10.x` retained) |
| Wazuh agent→manager, Prometheus scrape, Scrutiny | 1 | none |
| Node → Pi-hole DNS (`.10.177`) | 1 | none (directly connected) |
| Node internet egress | **30** | default route → `.30.1` |
| Randy↔QuarkyLab NFS `/data` + PBS backup | **30** | endpoints re-homed to `.30.x` |

## 5. Pre-change state (baseline)
- Cluster: Quorate, 7/7 votes, single corosync ring (LINK 0) on `192.168.10.x`.
- Node ports on EX3400 were access/native VLAN 1: QuarkyLab **ge-0/0/24**, Randy **xe-0/2/0**, Jarvis **ge-0/0/22**. VLAN 30 (`servers`) existed but was trunked only to the OPNsense uplink `ge-0/0/46`.
- NFS: Randy exported `/datastore/quarkylab` to `192.168.10.179`; QuarkyLab mounted `192.168.10.187:/datastore/quarkylab`. PBS repo `192.168.10.187`.
- Lifelines confirmed up: iDRAC/IPMI `.10.20/.21/.22`; Tailscale on all 3.

## 6. Implementation (as executed)
**Phase 1 - Switch (EX3400).** Converted the three node ports to trunk, `native-vlan-id 1`, `vlan members [default servers]`, applied with **`commit confirmed 5`** (dead-man auto-rollback); verified node reachability + quorum, then `commit` to confirm. Wazuh VM 104 remained on native VLAN 1.

**Phase 2 - Nodes.** Added `vmbr0.30` (QuarkyLab `192.168.30.179`, Randy `192.168.30.187`, Jarvis `192.168.30.31`, gw `192.168.30.1`) and removed the `gateway` line from `vmbr0`. Applied per node (Jarvis → Randy → QuarkyLab last) with `ifreload -a`, verifying VLAN 30 mesh, egress, DNS, and VLAN 1 mgmt after each. `/etc/network/interfaces` backed up on each node.

**Phase 4 - Storage/backup cutover.** Randy: added `.30.179` export (add-before-remove), then retired the `.10.179` export. QuarkyLab: repointed `/etc/fstab` to `192.168.30.187:/datastore/quarkylab` (remounted at 0 jobs; base.sif runs from local cache so no launch impact); repointed PBS `storage.cfg` server to `192.168.30.187`; corrected the hardcoded repo in `/usr/local/sbin/pbs-workspace-backup.sh` to `root@pam@192.168.30.187:datastore`. A workspace backup was run successfully over VLAN 30.

**Post-change fixes.** Installed the Scrutiny collector on Jarvis (was absent) → reports to hub `.183:8080`. Corrected the QuarkyLab login splash `NODE` field from a `192.168.30.x` placeholder to a live `vmbr0.30` lookup (self-updating).

## 7. Verification & results
| Check | Result |
|---|---|
| Cluster quorum | Quorate, **7/7 votes** (unchanged throughout) |
| VLAN 30 mesh + gateway + egress | QuarkyLab/Randy/Jarvis reach each other, `.30.1`, and the internet |
| VLAN 1 management | All 3 reachable on `.10.x`; SSH/iDRAC intact |
| NFS `/data` | `192.168.30.187`, read/write OK; old export retired |
| PBS | Active over `.30.187`; **workspace backup ran green** |
| Wazuh | Dashboard 302; agents **active** on all 3; VM 104 running |
| Prometheus → Grafana | All 3 `up=1`; live GPU metric fresh (age 0 s); dashboard 302 |
| Scrutiny | Hub 302; QuarkyLab + Randy + **Jarvis** disks reporting |

## 8. Concerns & risks
| # | Concern | Likelihood | Impact | Handling |
|---|---|---|---|---|
| C1 | Corosync destabilised by cross-VLAN routing | - | High | **Avoided by design** - corosync left on VLAN 1 L2. Residual: any *future* full-isolation reintroduces this; must use add-link/remove-link. |
| C2 | Node egress now depends on OPNsense VLAN 30 interface | Low | Med | Verified egress; VLAN 1 (mgmt/monitoring/DNS) is directly connected and independent of the default route; instantly revertible. |
| C3 | OPNsense (VM 100 on pve2) is SPOF for inter-VLAN + egress | Low | Med | Cluster + monitoring are L2 on VLAN 1 and unaffected by OPNsense; only internet/inter-VLAN depends on it (pre-existing condition). |
| C4 | `/data` remount interrupts running jobs | - | Low | Executed at **0 jobs**; base.sif served from local cache; add-before-remove on the export. |
| C5 | Non-VLAN-aware bridge carries tagged VLAN 30 transparently | Low | Low | Works today; **if `vlan_filtering` is ever enabled on `vmbr0`, VID 30 must be added to the bridge/port PVID/vids.** Documented. |
| C6 | Wazuh VM 104 rides the trunk's native VLAN | Low | Med | `native-vlan-id 1` explicitly set; changing it would move the VM's VLAN - flagged for change control. |
| C7 | Public repo (`machismo0311/Home-Lab`) leaking secrets | Low | High | **No passwords in any doc**; EX3400/Grafana/iDRAC creds live in Vaultwarden and are referenced, not embedded. |
| C8 | Hidden IP couplings (e.g. hardcoded backup repo) | Med | Low | Swept `/usr/local/sbin`, `/etc/slurm`, `/opt/mps`; found + fixed the one hardcoded PBS repo. |

## 9. Safeguards & controls applied
- **Corosync untouched** → the cluster was never at risk at any step.
- **`commit confirmed 5`** on the switch → automatic rollback if the nodes were lost.
- **Additive-first** (add VLAN 30 while keeping VLAN 1) → every step reversible.
- **Same-subnet admin SSH** (VLAN 1, directly connected) → the default-gateway move could not lock the operator out.
- **Console lifelines:** iDRAC/IPMI on VLAN 1 (`.10.20/.21/.22`) + Tailscale on all 3 (survives LAN re-IP).
- **One node at a time**, verifying each before the next; QuarkyLab (Wazuh host) last.
- **Config backups** on every node before edits (`interfaces.bak-vlan30-*`, `fstab.bak-*`, Randy `exports.bak-*`, splash `.bak-vlan30-*`).
- **Fresh PBS restore point** + **add-before-remove** on the NFS export cutover.
- **Authorized window** with zero running jobs.

## 10. Rollback (available at every step)
1. Storage: revert `fstab` + `storage.cfg` + backup script to `.10.187`; restore Randy `.10.179` export.
2. Nodes: delete `vmbr0.30`, restore `gateway 192.168.10.1` on `vmbr0`, `ifreload -a`.
3. Switch: `rollback 1; commit` (ports back to access VLAN 1).
4. Cluster: nothing to undo (untouched).
5. Lockout recovery: iDRAC console or `ssh <tailscale-ip>`.

## 11. Outcome & residual items
Migration succeeded with no unplanned downtime and full monitoring continuity. **Residual / follow-up:**
- **Phase 3 (operator, OPNsense GUI):** VLAN 30 DHCP DNS = `.177`; firewall allow `VLAN30 → .177:53`; client-access + egress rules per the plan's matrix. *Not required for the 3 nodes themselves* (they resolve via VLAN 1 directly).
- Jarvis Scrutiny - **done**. QuarkyLab splash - **done** (now dynamic).
- Optional future: full isolation (remove VLAN 1 footprint) would require moving corosync via the add-link/remove-link procedure - a separate, gated change.

## 12. Appendix
**Addressing**
| Node | VLAN 1 (mgmt, kept) | VLAN 30 (service, added) | Switch port |
|---|---|---|---|
| QuarkyLab | 192.168.10.179 | 192.168.30.179 | ge-0/0/24 |
| Randy | 192.168.10.187 | 192.168.30.187 | xe-0/2/0 |
| Jarvis | 192.168.10.31 | 192.168.30.31 | ge-0/0/22 |
| Gateway | (removed from vmbr0) | 192.168.30.1 (default) | - |

**Key file changes:** node `/etc/network/interfaces` (+`vmbr0.30`, −`vmbr0` gateway); Randy `/etc/exports`; QuarkyLab `/etc/fstab`, `/etc/pve/storage.cfg`, `/usr/local/sbin/pbs-workspace-backup.sh`, `/etc/profile.d/quarkylab_splash.sh`; Jarvis `/opt/scrutiny/*` + systemd units.
**Secrets handling:** EX3400 admin (`mason`), Grafana admin, and iDRAC credentials are stored in **Vaultwarden** - never committed to this repository.
