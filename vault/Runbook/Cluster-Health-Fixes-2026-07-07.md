# 📄 Maintenance Report — Cluster Health Sweep & Fixes

**Tags:** #report #maintenance #proxmox #systemd #backup #smart #vfio #changerecord
**Related:** [[00 - Homelab MOC]] · [[Runbook/Daily Operations]] · [[Runbook/randy-commissioning-runbook]] · [[Runbook/Jarvis-LLM-Platform-2026-07-05]] · [[Runbook/VLAN30-Migration-Report-2026-07-02]]

| | |
|---|---|
| **Change ID** | OPS-2026-07-07-HEALTH |
| **Date executed** | 2026-07-07 |
| **Author / operator** | K. Mason (with Claude Code) |
| **Systems** | pve2, pve3, pve4, pve5, Randy, QuarkyLab, Jarvis |
| **Change type** | Housekeeping / remediation — low-risk, reversible |
| **Trigger** | Full cluster health + log sweep after the 2026-07-06 ~16:37 cluster-wide reboot |
| **Result** | ✅ All flagged issues resolved or confirmed self-healed; 0 failed units cluster-wide |

---

## 1. Executive summary
A health sweep across all 7 km-cluster nodes (plus Pi-hole, PBS, EX3400 reachability) surfaced one real problem — **VM 100 (OPNsense) had not backed up since 2026-07-02** — and a set of cosmetic failed-unit / boot-log items left over from an unfinished config and the 07-06 reboot. All were fixed or confirmed benign. Cluster was **quorate (7/7)** throughout; no downtime.

Context: the whole cluster rebooted ~16:37 on 2026-07-06 (nodes showed ~9.5 h uptime). Many one-time `corosync`/`pmxcfs crit` and `no quorum!` log entries were **transient boot-window noise** and are not tracked as issues here.

## 2. Baseline (sweep findings)
| Node | Uptime | Root FS | Notable |
|---|---|---|---|
| pve2 | 9.5 h | 21% | openipmi failed; `/etc/modules` vfio typos; **VM 100 backup failing** |
| pve3 | 9.5 h | 17% | openipmi failed; NUT UPS driver noisy at boot |
| pve4 | 9.5 h | 12% | openipmi failed |
| pve5 | 9.5 h | 12% | openipmi failed |
| Randy | 5 d | 22% | **sdb 23 pending sectors** (smartd) |
| QuarkyLab | 4.5 d | 82% ⚠ | root fs trending high (noted, not changed) |
| Jarvis | 9.5 h | 24% | scrutiny-collector failed at boot |

---

## 3. Fixes

### 3.1 VM 100 (OPNsense) backup failure — FIXED 🔴→✅
**Symptom:** every `vzdump` of VM 100 aborted with `qmp command 'query-backup' failed - got timeout`; last good PBS snapshot was `vm/100/2026-07-02`. The backup would start, copy ~680 MiB, then QMP write speed collapsed to ~8 MiB/s and `query-backup` hung ~13 min before timing out.
**Diagnosis:** `qemu-guest-agent` is *not* enabled on VM 100 (so not the cause). QMP itself tested healthy (`query-backup` returned in 0.2 s). The last failed attempt (07-06 03:00) was **before** the 07-06 16:37 reboot, and no backup had run since — i.e. the fresh qemu process had never re-attempted. Root cause was a **wedged in-VM backup/QMP state** cleared by the reboot.
**Action:** ran a manual snapshot backup on the fresh qemu process (non-disruptive to OPNsense):
```bash
ssh pve2 "vzdump 100 --mode snapshot --compress zstd --storage randy-pbs \
  --prune-backups 'keep-daily=7,keep-weekly=4'"
```
**Result:** completed in **26 s** (1.2 GiB/s read, incremental — reused 96%). New snapshot `vm/100/2026-07-07T06:12:36Z` confirmed in PBS. Nightly job (`vzdump 100 104`, 03:00) should now succeed unattended.
**Watch:** if it wedges again on a future run, suspect a persistent PBS-write / QMP interaction specific to VM 100 and investigate deeper. Backup is crash-consistent (no agent/fsfreeze) — expected & acceptable for a firewall appliance.

### 3.2 openipmi.service failed on pve2–pve5 — FIXED ⚪→✅
**Cause:** the four EliteDesk nodes have **no BMC/IPMI hardware** (no DMI type-38 device, no `/dev/ipmi*`). The `openipmi` LSB init script tries to load IPMI drivers, finds none, exits 1 → systemd marks it failed every boot. Purely cosmetic.
**Action (each of pve2, pve3, pve4, pve5):**
```bash
systemctl stop openipmi.service
systemctl mask openipmi.service        # → /dev/null, won't start/fail on future boots
systemctl reset-failed openipmi.service
```
**Result:** all four report `masked`, **0 failed units**. R730s (QuarkyLab/Jarvis) and Randy have real IPMI and were **left untouched**. Reversible via `systemctl unmask openipmi.service`.

### 3.3 pve2 `/etc/modules` vfio typos — FIXED ⚪→✅
**Cause:** `/etc/modules` listed misspelled modules (`vifo`, `vifo_iomu_type1`, `vifo_pci`, `vifo_virqfd`) → `systemd-modules-load` "Failed to find module" errors each boot. Part of an **unfinished PCI-passthrough setup**: `intel_iommu=on` (10 IOMMU groups) but **no VM uses `hostpci`**, so nothing functional was broken — and passthrough could never have worked since the modules never loaded.
**Action:** rewrote `/etc/modules` (backup `/etc/modules.bak-20260707`) with corrected names, **dropping `vfio_virqfd`** (does not exist on kernel 7.0.12 — merged into vfio core):
```
vfio
vfio_iommu_type1
vfio_pci
```
**Result:** all three `modprobe` cleanly and are resident; `systemd-modules-load` re-run reports no failures. pve2 is now correctly primed for passthrough (add `hostpci0: <PCI-ID>` to a VM when needed; stack already loaded, no reboot required).

### 3.4 Jarvis scrutiny-collector failed at boot — FIXED ⚪→✅
**Cause:** the collector POSTs SMART data to the scrutiny hub API `http://192.168.10.183:8080`. Its timer used a fragile monotonic chain (`OnBootSec=2min` bootstrap + `OnUnitActiveSec=6h`). During the cluster reboot it fired 2 min into boot (15:40) **before the hub host was up** → non-zero exit → "Failed to start". Regular 6 h runs since then succeeded (self-healing cosmetic failure).
**Action:** replaced the monotonic chain with a **fixed calendar schedule** via drop-in `/etc/systemd/system/scrutiny-collector.timer.d/override.conf`:
```ini
[Timer]
OnBootSec=
OnUnitActiveSec=
OnCalendar=*-*-* 00,06,12,18:00:00
RandomizedDelaySec=90
Persistent=false
```
**Result:** next run **Tue 06:00**, timer active, service not failed. Reboot-proof, can't race the hub, no fragile anchor.
**Note (benign):** Jarvis's 2× **SEAGATE ST200FM0053** SAS SSDs (behind the megaraid HBA) make `smartctl` return **exit code 4** ("checksum error in SMART data structure") every run — scrutiny logs it but still collects. Drives are healthy: **0 uncorrected / 0 non-medium errors**, only a link-layer "running disparity count = 4". Not a device fault. *Jarvis is getting additional drives soon — expect the same exit-4 noise from any new disk on the same controller; re-run the collector after install to populate the dashboard immediately.*

### 3.5 pve3 NUT UPS driver — CONFIRMED HEALTHY (self-healed) ⚪
The sweep saw 8× "Failed to start `nut-driver@midatlantic`" at boot — the SNMP UPS simply didn't answer immediately after a cold boot. NUT's retry logic connected at 16:44; now `active (running)`, UPS `ups.status: OL`, `battery.charge: 100`, `nut-server`/`nut-monitor`/`nut-driver.target` all active. No action needed.

---

## 4. Randy `/dev/sdb` pending sectors — assessed + exercised (open)
**Disk:** Seagate ST2000NX0423, 2 TB 7200 rpm, S/N W460W2Y3, **~5.98 yr** powered on (52,416 h). Member of the **`raidz2-3`** vdev (4-wide Seagate) of the `datastore` pool.

| Attribute | Value |
|---|---|
| Current_Pending_Sector | **23** |
| Reallocated_Sector_Ct | 869 |
| Reported_Uncorrect / Offline_Uncorrectable | 0 / 0 |
| UDMA_CRC_Error_Count | 0 |
| SMART overall | PASSED |

**ZFS reality:** pool `ONLINE`, `No known data errors`, sdb **READ/WRITE/CKSUM = 0**; no kernel medium errors. The 23 pending sectors are LBAs that failed a background patrol read but haven't been rewritten — **no data at risk** (raidz2 double parity + heal on scrub).

**Actions taken 2026-07-07 ~02:14:**
- **ZFS scrub** of `datastore` → `repaired 0B in 00:00:28 with 0 errors` (pool holds only ~72 G).
- **Long SMART self-test** on sdb (`smartctl -t long /dev/sdb`), started ~02:14, finished ~07:39 EDT.

**Self-test result (07-07 ~07:39): `Completed: read failure` — hard unreadable sector at LBA 3875904942.** The scan lingered ~25 min in its final segment retrying the marginal region, then aborted on an unrecoverable read. Pending sectors dropped **23 → 21** (a couple re-read/reallocated), but the hard read failure **confirms real, non-transient media damage** rather than soft/transient errors. `Reported_Uncorrect` and `Offline_Uncorrectable` remain 0 (this Seagate doesn't tick 187 for the event); `Reallocated_Sector_Ct` unchanged at 869.

**Data impact: none.** ZFS still `ONLINE` / `No known data errors`, sdb READ/WRITE/CKSUM = 0, and no kernel medium errors — the bad LBA sits in **unused space** (pool ~72 G of ~23 T used), so it was never read by live I/O, and raidz2 covers the vdev regardless.

**Recommendation (upgraded → REPLACE): the self-test read failure changes this from "watch" to "replace."** This is the oldest, most-worn disk in the pool (6 yr / 52,421 h, 869 reallocations, 21 pending + a confirmed unreadable LBA). No emergency (raidz2 + no data affected), but **order a spare 2 TB (Seagate ST2000NX0423-class) and `zpool replace datastore sdb <new>`** at the next convenient window. Until then, a scrub will heal any parity mismatch if that region ever gets live data; consider a periodic scrub to keep coverage confirmed.

---

## 5. Post-change state
- **0 failed units** on all 7 nodes; `systemctl is-system-running = running` everywhere.
- Cluster quorate 7/7 throughout.
- VM 100 protected again (last backup 07-07 vs. 07-02).
- Cosmetic boot-log noise eliminated (openipmi, vfio typos, scrutiny race).

## 6. Follow-ups
- [x] Randy sdb long self-test (07-07 07:39) → **read failure @ LBA 3875904942, confirms media damage; pending 23→21; no data impact.**
- [ ] **Order spare 2 TB + `zpool replace` sdb on Randy** — self-test confirmed a hard bad sector (was "watch," now "replace").
- [ ] QuarkyLab root fs at 82% — cleanup pass before it bites (OS root; the big ZFS workspace datasets are near-empty).
- [ ] Confirm VM 100 nightly backup (03:00) succeeds unattended on 07-08.
- [ ] Re-run scrutiny collector on Jarvis after the new drives are installed.
