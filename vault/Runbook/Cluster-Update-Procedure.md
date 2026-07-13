# Cluster Update Procedure (km-cluster)

**Tags:** #runbook #updates #maintenance #ops

Safely apply apt and PVE updates across the 7-node cluster without losing quorum, breaking the GPU driver stack, or causing an avoidable outage. Reusable; not a one-time report.
Related: [[Runbook/Recovery Procedures]] · [[Runbook/Daily Operations]] · [[ADR/0010-gpu-node-kernel-pinning]] · [[High Availability/High Availability MOC]] · [[Operations and Onboarding]]

---

## Golden rules
- **One node at a time.** Never reboot two cluster nodes at once. Quorum needs 4 of 7.
- **Only one RKE2 control-plane node (pve3/pve4/pve5) down at a time.** etcd needs 2 of 3.
- **GPU nodes (QuarkyLab, Jarvis): the kernel is HELD.** Do not let `dist-upgrade` pull or boot a newer kernel. It breaks the NVIDIA 550 stack. See [[ADR/0010-gpu-node-kernel-pinning]].
- **pve2 reboot = whole-network outage.** It hosts OPNsense (the router/DHCP/DNS gateway). Do it in a planned window, last.
- **Verify quorum and guest recovery after each node before moving to the next.**

## Pre-flight (once, before starting)
1. Health: `ssh pve3 corosync-quorumtool -s` shows 7 nodes, Quorate Yes. ZFS pools ONLINE. `backup_verify` overall pass.
2. Backups current (especially before a large upgrade). RKE2 CP VMs 201/202/203 now covered by a nightly job.
3. Pick a window and expect a brief full-network outage during the pve2 step.

## Standard node procedure (pve3, pve4, pve5, Randy)
One node at a time:
1. `apt-get update && apt-get -y dist-upgrade`
2. Guests with a guest agent (VM 100 OPNsense, VM 104 Wazuh) shut down gracefully on host reboot; `onboot=1` guests auto-start.
3. `systemctl reboot`
4. Wait for return, then verify: `corosync-quorumtool -s` back to 7/7, guests auto-started, and (CP nodes) the RKE2 VM rejoined etcd.
5. Only then do the next node.

Node-specific notes:
- **pve3** hosts the service LXCs (101-107) + RKE2 cp1 (VM 201). Its reboot briefly drops Grafana, NPM, Vaultwarden, Headscale, monitoring, Open WebUI, and one etcd member. All auto-start; verify services after.
- **pve5** hosts the **secondary Pi-hole (CT 108)** + RKE2 cp3 (VM 203). Primary Pi-hole `.177` is on pve1 (standalone, not in this pass), so DNS HA holds. Do not reboot pve5 while pve1 is also down.
- **Randy** is storage + PBS. Its reboot drops NFS (k8s PVCs), PBS, and Jellyfin briefly. Do it off the 02:00-04:00 backup window. After reboot verify: `zpool status` all ONLINE (`bulk` auto-imports), PBS reachable, NFS re-exported. JBOD mode on the AVAGO 3108 may need re-asserting (see Randy commissioning notes).

## GPU node procedure (QuarkyLab, Jarvis) - kernel HELD
Pinned to `6.14.11-9-pve` for NVIDIA 550.163.01. Do NOT upgrade the kernel or the NVIDIA driver.
1. **Inspect the upgrade first:** `apt-get update && apt list --upgradable 2>/dev/null | grep -iE 'kernel|nvidia'`. Hold anything that matches: `apt-mark hold proxmox-default-kernel 'proxmox-kernel-6*' 'pve-kernel-6*' 'nvidia-*'` then confirm with `apt-mark showhold`.
2. `apt-get -y dist-upgrade` (held packages are skipped).
3. Confirm `GRUB_DEFAULT` still targets 6.14.11-9-pve. Do NOT run `proxmox-boot-tool` kernel changes on these nodes.
4. QuarkyLab hosts Wazuh VM 104 (graceful via agent). Jarvis runs Ollama + the `gpu-fan-control` daemon.
5. `systemctl reboot`. After reboot verify: `uname -r` == `6.14.11-9-pve`, `nvidia-smi` shows the GPU(s) with full VRAM on driver 550.163.01, `gpu-fan-control` active (Jarvis), Wazuh healthy (QuarkyLab).
6. If `nvidia-smi` fails after reboot, the kernel changed: reboot into 6.14.11 via the GRUB menu and re-pin. See [[ADR/0010-gpu-node-kernel-pinning]].

## pve2 (OPNsense) - planned outage window, do last
Rebooting pve2 takes OPNsense (VM 100) down: no LAN routing, DHCP, inter-VLAN, or internet for the whole network until pve2 returns (~2-5 min).
1. Expect a brief full-network outage.
2. `apt-get update && apt-get -y dist-upgrade` on pve2.
3. OPNsense shuts down gracefully (agent installed). `systemctl reboot`.
4. Verify: VM 100 auto-started (`onboot=1`), gateway `.1` answers, DNS/DHCP working, internet restored, quorum back to 7. Console fallback: `qm terminal 100` (exit Ctrl-O).
5. This single-node dependency is what the planned MR7400 WAN failover + OPNsense CARP pair will remove. See [[Runbook/WAN-Failover-FirstNet-MR7400-Plan-2026-07-12]].

## Suggested order (least impact first, pve2 last)
1. **Randy** (off-hours, no backup running)
2. **pve4** (RKE2 cp2)
3. **pve5** (RKE2 cp3 + secondary Pi-hole) - verify etcd + DNS HA
4. **pve3** (services + RKE2 cp1) - heaviest; verify all LXCs + services
5. **QuarkyLab** (kernel held) - verify GPU + Wazuh
6. **Jarvis** (kernel held) - verify GPU + Ollama
7. **pve2** (OPNsense) - in the announced outage window

Reboot one, confirm quorum returns to 7 and its guests recovered, then the next.

## Post-update verification (whole cluster)
- `corosync-quorumtool -s`: 7/7 quorate.
- All `onboot=1` guests running.
- ZFS pools ONLINE on every node.
- RKE2: `kubectl get nodes` all Ready; etcd healthy.
- DNS: both Pi-holes answering.
- Monitoring: `backup_verify` pass; no new firing alerts in Discord; UPS + quorum metrics present.
- GPU nodes: `nvidia-smi` OK, kernel still 6.14.11-9-pve.

## Rollback
- Bad kernel/driver: boot the previous kernel from the GRUB menu.
- Bad package: `apt-get install <pkg>=<old-version>` to downgrade.
- Broken guest: restore from PBS.
- Node will not rejoin quorum: see [[Runbook/Recovery Procedures]] (Randy corosync-singleton recovery is documented there).
