# pve3 Outage + Remote Recovery - 2026-07-16

## Incident

- **06:55:03 EDT (10:55 UTC):** pve3 (EliteDesk, 192.168.10.201) dropped from corosync
  with a sudden KNET link-down - no graceful leave, consistent with instant power loss
  or hard crash. Cluster stayed quorate (6/7).
- **Root-cause suspicion (unconfirmed):** power/UPS fault at pve3's position. pve3 is
  the NUT host (Tripp Lite USB + Middle Atlantic SNMP), and Wake-on-LAN to its MAC
  `c8:d9:d2:17:5c:d0` got no response - a NIC with standby power would normally wake,
  so the box likely has no AC at all. Physical check needed: UPS state, outlet, PSU.
- **Why no alert fired:** Grafana (the alerting stack) lived on pve3. Known
  monitoring-on-the-monitored SPOF; see also the new OPEN-ITEMS entry - the netframe
  collector has no UNREACHABLE verdict, so a dead node reads as scattered WARNs.

## Impact while down

CT 101 NPM (all `*.kylemason.org` fronts), CT 102 Vaultwarden, CT 103
Grafana/Prometheus/Loki/InfluxDB/Scrutiny, CT 105 Headscale, CT 106
Homepage/PeaNUT, CT 107 OpenWebUI, VM 201 RKE2 CP1 (etcd stayed quorate 2/3),
host-native NUT + CrowdSec. DNS unaffected (Pi-holes on pve1/pve5).

## Remote recovery performed (owner-approved, from Ares)

All pve3 guests are on its **local** LVM - nothing could migrate. PBS backups on
Randy were fresh (all CTs 06:00-06:02 UTC same day, ~5h before the crash).

Restored **CT 101 (NPM)** and **CT 103 (Grafana stack)** onto **pve4**:

```bash
# config copies first
mkdir -p /root/pve3-recovery-20260716        # on pve4; copies of original confs live here
cp /etc/pve/nodes/pve3/lxc/{101,103}.conf /root/pve3-recovery-20260716/
mv /etc/pve/nodes/pve3/lxc/101.conf /etc/pve/nodes/pve4/lxc/   # claim VMID on live node
pct restore 101 randy-pbs:backup/ct/101/2026-07-16T06:00:07Z --storage local-lvm
pct start 101   # same for 103 (2026-07-16T06:00:33Z)
```

**Gotcha hit:** `pct restore --force` over a config whose rootfs LV lives on the dead
node fails (`no such logical volume pve/vm-101-disk-0`) AND deletes the config. That
turned out to be the cleaner path anyway: with the VMID unowned, a plain restore
(no `--force`) recreates config + disk fresh on the target node. Do it that way
deliberately next time: **delete/move the config away, restore without --force.**

Verified after restore: NPM .181 + Grafana .183 up with original MACs/IPs (DHCP
static mappings held); health/console/homepage 401 (auth enforced), grafana 302,
Grafana `/api/health` database ok, Loki ready; vault.kylemason.org 502 =
Vaultwarden backend still down, expected.

**Vaultwarden (CT 102) deliberately NOT restored:** it is VLAN 30-only (`tag=30`)
and pve4's bridge is not VLAN-aware / port not trunked, so a restore there has no
network without re-IP hacks. Cached Bitwarden clients keep working offline.

## Revival checklist (when physically at pve3)

1. Check UPS/outlet/PSU before powering on; note what actually failed.
2. Power on. CTs 102/105/106/107 + VM 201 autostart (onboot=1) - **101 and 103 will
   NOT start on pve3** (their configs now live on pve4); no IP/MAC conflict.
3. Verify: Vaultwarden `https://vault.kylemason.org` (NPM backend .30.182), Headscale
   .186:8080, Homepage CT106, OpenWebUI CT107, VM 201 rejoined etcd
   (`kubectl get nodes`), NUT (`upsc` / PeaNUT widgets), CrowdSec.
4. Investigate root cause: `journalctl -b -1 -e` on pve3, UPS logs, temps.
5. Decide: migrate 101/103 back to pve3 (offline `pct migrate` copies local disks) or
   leave them on pve4. Either way delete the **orphaned LVs on pve3**:
   `lvremove pve/vm-101-disk-0 pve/vm-103-disk-0` (old pre-crash disks, superseded by
   the restores; only after confirming the restored CTs are good).
6. Remove `/root/pve3-recovery-20260716/` on pve4 once settled.
7. Grafana/Loki have a metrics/logs gap 06:00-12:52 UTC (restore LVs created 12:48/12:52 UTC;
   history restored from the 06:00 backup). Expect a burst of Discord alerts as rules
   re-evaluate - triage, they may include a *legitimate* pve3-down alert.

## Follow-ups filed

- OPEN-ITEMS (netframe-monitor): collector UNREACHABLE verdict gap; pve3 revival item.
- Consider: alerting SPOF (Grafana on one node) is now demonstrated, not theoretical -
  feeds the Compute HA roadmap item.

## Addendum (same day, ~22:40 UTC): RKE2 control-plane cascade + recovery

The evening health check found the "HA" control plane had NOT survived losing one
node. When cp1 (VM 201, pve3) died, etcd lost its leader; `rke2-server` on cp2 and
cp3 then hit a startup-fatal ("failed to reconcile with local datastore: context
deadline exceeded") and **crash-looped ~2,000+ times each for ~12h**, taking
containerd down with it and leaving zombie apiserver/etcd containers under orphaned
shims (they answered TLS, logs frozen, no leader electable, VIP .54 unclaimed,
kubectl dead). Peer network was fine - pure process-state wedge.

**Fix (owner-approved, verified):** on cp2 AND cp3: `systemctl stop rke2-server`,
`rke2-killall.sh` (clears shims/zombies), then `systemctl start rke2-server` on both
near-simultaneously so the two surviving etcd members form 2/3 quorum. etcd data on
disk was untouched (no writes were possible all day). Outcome: cp2/cp3/randy Ready,
VIP .54 answering, registry 200, uptime-kuma up, 45 pods Running, cp1 NotReady
(expected until pve3 revives - it should rejoin the now-healthy quorum on boot).

**Root cause (confirmed from journals, same evening):** the crash was NOT caused by
losing cp1 - etcd ran fine on 2/3 members for two hours. The trigger was the
**emergency PBS restores of CT 101/103 onto pve4 (12:48-12:52 UTC, LV timestamps)**:
the 20GB restore stream + grafana-stack cold start saturated pve4's thin pool, which
also backs rke2-cp2's VM disk. etcd on cp2 logged 1,096 "apply request took too
long" (5-10s vs 100ms budget); with only 2 members a single stalled member =
leaderless. At 12:56:00 BOTH survivors' rke2 leader leases (renewed via the
apiserver -> etcd) expired and rke2-server fatal-exited by design on both
simultaneously ("leaderelection lost for rke2/rke2-etcd"). The restart then
deadlocked: bootstrap needs a quorate etcd read, but the crash killed containerd,
orphaning zombie etcd containers that never re-elected.

**Lessons:**
1. `pct restore --bwlimit` (or schedule restores off-peak) when the target node
   hosts etcd or other latency-critical VMs - recovery IO is a failure vector.
2. A 2-member etcd has zero stall tolerance: any single-member IO pause = leaderless.
3. rke2 v1.35.6 fatal-on-lost-lease + containerd-zombie deadlock amplifies a ~60s
   stall into a permanent outage - the OPEN-ITEMS failover test now has a repro
   recipe (IO-stall a CP node's disk while a member is already down).
