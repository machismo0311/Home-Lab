# 22 — Storage & Backup (Phase 2)

**Scan:** 2026-07-22, read-only. Raw: `audit/live/randy.txt`, `randy-storage.txt`,
`backup-freshness.txt`.

## 🔴 CRITICAL — Randy `bulk` (DS4246) pool is DEGRADED: a drive is FAULTED

```
pool: bulk   state: ONLINE   status: One or more devices are faulted … degraded state
raidz2-2:  … mpathv  FAULTED  3 read / 14 write / 0 cksum  "too many errors"
```
- **Faulted device:** `mpathv` = **Seagate ST4000NM0023, WWN 5000c500631a54fb** (dm-26).
  **Both** SAS paths are down: `sdbo` (11:0:62:0) and `sdbn` (11:0:61:0) = *failed faulty offline*
  → the physical 4 TB drive is dead, not a multipath flap.
- **Redundancy left:** it sits in the **6-wide `raidz2-2`** vdev, which now has **1 of 2 parity
  drives of tolerance remaining**. A second failure in that vdev = data loss.
- **Timeline:** last `bulk` scrub was **Sun Jul 19 02:30 (0 errors)** — so the fault occurred in
  the **last ~3 days** and has not yet been caught by a scrub. `errors: No known data errors` (yet).
- **Action (Kyle — NOT done by this audit, read-only):** replace the drive and `zpool replace
  bulk <old> <new>`; there are **2 free DS4246 bays**. Then bump `backup_verify_ds4246_expected`
  if the layout changes. **First: confirm whether the ZfsPoolDegraded alert fired** — see
  `24-observability.md` (open item).

This is the single highest-value finding of the audit and the spec's premise made real.

> **Corroborated & already in hand (NF-INC-2026-07-22).** A concurrent session independently
> diagnosed this drive (DS4246 **slot 15**, failed 2026-07-21 17:12, `DID_TRANSPORT_DISRUPTED`),
> **reseated it on 07-22 (confirmed dead — links up but never spins ready)**, and has replacement
> pending. See `vault/Runbook/AAR-2026-07-22-Backup-Verify-Scheduler-and-DS4246-Drive.md`. My
> live `zpool status` finding matches theirs. R-01 is therefore *known and being actioned*, not a
> new discovery — kept here as the audit's independent confirmation.

## ZFS pools — live geometry (settles the Phase 1 C-HARD/C-SUPERSEDED)

| Pool | Node | Geometry (LIVE) | Size | Health |
|---|---|---|---|---|
| `datastore` | Randy | 4× RAIDZ2 (3×6-wide Toshiba + 1×4-wide Seagate) | 36.7T / 173G used | ONLINE ✅ |
| **`bulk`** | Randy | **3× RAIDZ2 (8+8+6-wide)** | **80.0T** / 75G used | **DEGRADED 🔴** |
| `workspace` | QuarkyLab | 6-wide raidz1 (+spare) | 10.9T | ONLINE ✅ |
| `tank` | Jarvis | raidz1 5×2TB | 9.09T (7.2T models) | ONLINE ✅ |
| `scratch` | Jarvis | single SSD | 186G | ONLINE ✅ |

→ **Confirms CLAUDE.md and proves `topology/…md:424` + `Proxmox Cluster.md:48` STALE** (they
say `bulk` = 2×8-wide / 58.2T). Live = 3-vdev / 80T. (See `11-contradictions.md` S-Bulk.)

## DS4246 cabling (settles Phase 1 H3)
`mpathv` resolves through the LSI 9207-8e as **SAS multipath** (two IOM paths, `sdbn`/`sdbo`).
DS4246 shelf drives are 4 TB SAS (Seagate ST4000NM0023 / HGST). The connector is standard SAS
external cabling; the repo's `SFF-8644 → SFF-8088` descriptor is plausible for a 9207-8e→shelf run.
**The audit-spec's `QSFP/SFF-8436` claim is a networking connector and does not match** — recommend
keeping the repo's SAS descriptor; verify the exact HBA-port connector physically if it matters.

## Drive enumeration (settles spec §4.2 expectations)
- **`datastore` (internal, AVAGO 3108 JBOD):** storcli `/c0` = 22 JBOD drives (18× Toshiba
  AL15SEB18EQ 1.636T + 4× Seagate 1.819T) + 1 boot VD (RAID-1). ✅ matches CLAUDE.md.
- **`bulk` (DS4246, LSI 9207-8e IT-mode + multipath):** **22× 4TB** (8+8+6), 2 bays free. ✅
- The spec's expected "13× 1.8T + 19× 2T = 32 in the DS4246" is **incorrect** — DS4246 = 22× 4TB;
  the 1.6T Toshibas are internal `datastore` drives.

## Backups — all cluster guests fresh ✅; standalone pve1 unprotected 🟠

**PBS:** datastore `datastore` on Randy. **GC** ran OK today (Jul 22 03:00). **Verify job**
`verify-datastore` weekly Sun 04:00 ✅. **No PBS prune-job** — but **retention is enforced
job-side** (`prune-backups keep-daily=7,keep-weekly=4` on every vzdump job) → not a gap.

Latest backup per guest (all **2026-07-22**, <25h ✅):

| Guest | Type | Job (schedule→store) | Latest |
|---|---|---|---|
| CT 101/102/103/105/106/107/108 | LXC | 02:00 → randy-pbs | 07-22 06:00Z |
| VM 100 OPNsense | VM | 03:00 → randy-pbs | 07-22 07:00Z |
| VM 104 Wazuh | VM | 03:00 → randy-pbs-10g | 07-22 07:00Z |
| VM 110 HomeAssistant | VM | 03:30 → randy-pbs | 07-22 07:30Z |
| VM 201/202/203 RKE2 | VM | 04:00 → randy-pbs | 07-22 08:00Z |

- **F-B1 · HIGH — pve1 (standalone) has NO backups.** No vzdump job, empty `/var/lib/vz/dump`,
  no PBS target. Its **CT 103 = PRIMARY Pi-hole** and CT 104 (old homepage) are unprotected.
  *Mitigated* (not eliminated): the secondary Pi-hole (CT 108, pve5) is backed up and nebula-syncs
  the config, so DNS state is recoverable — but pve1 itself is a backup blind spot. Add pve1 to a
  PBS job (it can reach Randy's datastore).
- **F-B2 · MEDIUM — `bulk` is not a backup source or target.** PBS backs up to `datastore`
  (36.7T). `bulk` (80T media/archive/fernanda) holds `bulk/backups` (54G) but is **not itself in
  PBS**. Fernanda's research data on `bulk/fernanda` has no offsite/second copy. (3-2-1 below.)

## 3-2-1 assessment · HIGH (expected gap, confirmed)
All backups live on **Randy**, in the **same rack, same UPS bus**. No offsite copy, no second
PBS. One fire/theft/flood = total loss (including Fernanda's data). → Tier-1 gap; see
`30-gap-analysis.md` (PBS remote sync / rclone→B2).
