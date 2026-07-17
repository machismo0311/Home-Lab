# QuarkyLab Storage Expansion - 2026-07-13

**Tags:** #runbook #storage #zfs #quarkylab #raidz #perc
**Related:** [[Infrastructure/QuarkyLab Storage]] · [[Compute/Dell R730 - ML Node]] · [[Runbook/QuarkyLab-Containerd-Relocate-to-ZFS-2026-07-10]]

---

## Summary

Added **two 2TB HGST SAS drives** (HGST Ultrastar 7K4000, `HUS724020ALS640`) to QuarkyLab (`.10.179`):

- **`sdc`** (SN `P6JRLE5V`, slot 2) - **expanded the `workspace` `raidz1-0` vdev from 5-wide to 6-wide** via ZFS RAIDZ expansion. Raw pool 9.09 TB → **10.9 TB**.
- **`sdh`** (SN `P6HK5U6V`, slot 7) - added as a **ZFS hot spare** (`AVAIL`).

Also pulled the undersized **931 GB Hitachi HUA722010CLA330** (SN `JPW9K0N13BHTVL`) that had been sitting unused in slot 2 (too small to join a 2TB vdev).

Pool stayed **ONLINE with zero errors** throughout. Final: `workspace` 6-wide raidz1, 10.9 TB raw (~9.1 TB usable), 1× 2TB SAS hot spare.

---

## Environment (discovered)

- **Controller:** Dell **PERC H330 Mini** (LSI SAS-3 3008 "Fury" ASIC), ctrl SN `4AM00EM`, FW `25.2.1.0037`, **RAID-Mode personality with JBOD ON**. `storcli64` at `/usr/local/bin/storcli64`, controller `/c0`.
- **Backplane:** Dell **BP13G+**, 8-bay, enclosure `EID 32`, slots 0-7.
- **ZFS:** `zfs-kmod 2.3.4-pve1`; pool had `feature@raidz_expansion` **enabled** (now `active`), which made the in-place widen possible.
- Disks are JBOD pass-through (`/dev/sd*`); ZFS owns redundancy. No hardware RAID VD.

---

## The slot-7 "dead bay" that wasn't (root cause: paper)

The first drive was inserted into the empty 8th bay (**slot 7**) and was **completely undetected** - absent from `lsblk`, from `storcli64 /c0 /eall /sall show`, and not even present as Unconfigured Good or Foreign. The controller logged:

```
megaraid_sas 0000:02:00.0: (CRIT) - Enclosure PD 20(c None/p1) phy bad for slot 7
```

Multiple reseats did not help. It looked like a dead bay / bad backplane PHY. **Actual root cause: a piece of paper was lodged in the bay**, holding the drive's connector off the backplane pins. After removal, slot 7 negotiated a clean **6.0 Gb/s** link and passed a sustained-read test with **zero I/O errors**. The bay is fine.

> [!TIP] `Other Error Count` on a slot bumps ~4 per hotplug/reseat - that is SAS link renegotiation, **not** data errors. It stays flat under sustained I/O on a healthy link (verified: 5 GB read at 183 MB/s, delta 0).

Before the paper was found, the drive was moved to the **1TB drive's bay (slot 2)** as an isolation test (the 931 GB disk was unused / not in any pool, so it was the safe bay to borrow). It came up fine there, which is how it ended up as the pool member in slot 2.

---

## Procedure - expose a new PERC drive to ZFS

A new disk on this PERC lands as **Unconfigured Good**, usually with a stale **Foreign** config, and is **not** passed to the OS until set to JBOD:

```bash
# 1. Confirm the controller sees it (Physical Drives count rises; new slot shows UGood/F)
storcli64 /c0 show
storcli64 /c0 /eall /sall show

# 2. Clear any leftover foreign config, then flip the slot to JBOD
storcli64 /c0 /fall del
storcli64 /c0 /e32 /s2 set jbod            # slot 2 here

# 3. Rescan so the OS enumerates /dev/sdX
for h in /sys/class/scsi_host/host*/scan; do echo "- - -" > "$h"; done
lsblk -d -o NAME,SIZE,MODEL,SERIAL,TRAN

# identify a physical drive by blinking its bay LED:
storcli64 /c0 /e32 /s2 start locate        # ... /s2 stop locate  when found
```

---

## Procedure - add to the pool (by stable by-id path)

```bash
# WIDEN the raidz1 vdev 5→6 (RAIDZ expansion) - grows capacity, keeps single parity
zpool attach workspace raidz1-0 /dev/disk/by-id/wwn-0x5000cca02899d158

# OR add a standby that auto-resilvers on a member failure
zpool add workspace spare /dev/disk/by-id/wwn-0x5000cca028579e88
```

> [!WARNING] Do **not** `zpool add workspace <disk>` bare
> That stripes a single unprotected disk onto the pool and destroys raidz redundancy. Use `attach … raidz1-0` to grow, or `add … spare` for a standby.

**Expansion notes:** the reflow ran online and copied 119 G in ~8 min (pool was ~1% full). Existing data **retains its old 5-wide parity ratio** until rewritten, so realised usable growth is slightly under a full disk at first - expected ZFS behaviour, not a fault. `zpool list` SIZE updates only when the reflow completes.

---

## Verification

```
workspace  raidz1-0  ONLINE   (6 members: 5× SATA + sdc SAS)
spares     wwn-0x5000cca028579e88  AVAIL
zpool list workspace  → SIZE 10.9T (was 9.09T)
errors: No known data errors
```

- Wazuh VM 104 lives on the **OS disk's LVM thin pool** (`sda`), not `workspace` - unaffected.
- Slot map, serials and steady-state geometry: [[Infrastructure/QuarkyLab Storage]] § Physical drives & RAID controller.

---

## Follow-ups

- **Monitoring:** the Grafana `ZfsPoolDegraded` alert + ZFS textfile collector already cover `workspace`; the hot spare and wider vdev need no config change.
- **Watch item (minor):** slot 7 has two historical `phy bad` CRIT log entries from the paper episode. It is healthy now and, being a spare bay, any future glitch there is non-destructive - but it is the one bay with a blemished history.

## Post-swap step discovered 2026-07-17: restart smartd

After ANY drive add/swap/remove, `systemctl restart smartmontools`. smartd only
enumerates devices at startup (DEVICESCAN), so after the 07-13 swap it kept
probing the new `/dev/sdc` (2TB SAS) with the OLD registration (1TB SATA Hitachi,
SAT protocol) - every SMART read failed and it nagged Discord daily for 4 days
("FailedReadSmartErrorLog ... JPW9K0N13BHTVL"). Not a failing drive: a stale
device table + protocol mismatch on shifted device letters. Restart -> clean
re-enumeration (8/8 drives, correct SAS/SATA protocols, zero errors). Add the
restart to this procedure's checklist whenever bays change.
