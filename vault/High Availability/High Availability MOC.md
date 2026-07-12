# High Availability

Map of the cluster's HA posture. Two parts: what is **Completed** and the **Projects** still planned. Prioritized. Links out to the detailed runbooks.

Cluster snapshot (verified 2026-07-12): 7 nodes, quorate (needs 4). `ha-manager` has **no resources**, storage is **all local** (no shared storage, no replication), so compute HA is not yet active.

---

## Completed
- **DNS HA** — dual Pi-hole, nebula-sync mirror, DHCP failover on all VLANs. See [[DNS-HA-OPNsense-Resilience-2026-07-10]]
- **RKE2 control plane HA** — 3 node HA control plane, VIP, Cilium, MetalLB. See [[RKE2-Phase1-HA-ControlPlane-2026-07-10]]
- **Cluster quorum** — 7 nodes, healthy, survives loss of up to 3.
- **OPNsense resilience (Tier-A)** — serial console verified, age-encrypted config backup repo, cold-restore runbook. See [[DNS-HA-OPNsense-Resilience-2026-07-10]]
- **Monitoring dead-man's switches** — Grafana to Discord alerting incl. stale-report and backup-verify watchdogs. See [[Monitoring-Alerting-2026-07-10]]

## In progress
- **WAN failover** — FirstNet MR7400 as OPNsense WAN2, gateway-group failover. See [[WAN-Failover-FirstNet-MR7400-Plan-2026-07-12]]
- **Router HA (OPNsense CARP pair)** — second dedicated box, CARP + pfSync + config sync. Planned in the same runbook.

## Projects (planned, prioritized)
1. **Compute HA (foundation, currently missing).** `ha-manager` empty, storage all local, no replication, so no guest auto-recovers on node failure. Enable via **Ceph** (shared storage) OR **ZFS replication + ha-manager** for critical single-instance guests (monitoring, Headscale, Wazuh, Vaultwarden, primary Pi-hole).
2. **Storage SPOF: Randy.** One box serves PBS backups + RKE2 NFS + registry + bare-metal storage. Fix: Ceph (also solves item 1), or a second storage target + replication, or at minimum finish offsite backup (restic to B2).
3. **Switch redundancy.** EX3400 is a single switch carrying everything incl. corosync. Add a second switch with Virtual Chassis or LACP; split corosync and uplinks across both.
4. **Corosync second ring.** Only `ring0` today (mgmt network). Add `ring1` on a separate NIC/VLAN so a network hiccup cannot partition the cluster. Cheap, high value.
5. **Power.** UPS with NUT graceful shutdown; dual PSUs on separate circuits for the R730 and SuperMicro nodes. See [[Power Distribution]]
6. **App and DR layer.** Multi-replica K8s workloads with anti-affinity; Vaultwarden and Headscale redundancy; finish offsite backups; consider a second PBS.

## Key decision
Items 1 and 2 are one choice:
- **Ceph** across nodes: shared storage that enables compute HA and removes the Randy storage SPOF at once. Heavy (disks on 3+ nodes, network, learning curve).
- **ZFS replication + ha-manager**: lighter, works on current local disks, small data-loss window, keep Randy and lean on offsite backups.

## Status legend
🟢 Completed  ·  🟡 In progress  ·  ⚪ Planned
