# Randy Scrutiny - Boot-VD & Replaced-Seagate False Positives (2026-07-10)

**Status:** RESOLVED / verified - dashboard shows zero red devices

**Related:** [[Runbook/Randy-sdb-Monitor-Followup-2026-07-08]] · [[Runbook/DS4246-Pool-Buildout-Plan-2026-07-07]] · `project-netframe-monitor`

## Trigger
Scrutiny (drive-health dashboard, Homepage widget) showed two Randy drives **Failed**:

| Scrutiny entry | Reported |
|---|---|
| `/dev/sdb` - ST2000NX0423, `sat` | Failed, 26 °C, Powered On 6 yr (last update Jul 07) |
| `/dev/sdw` - AVAGO SMC3108, 185.8 GiB | Failed, ∞ °C, no power-on (last update Jul 09) |

Both turned out to be **false positives**. Ground truth pulled from Randy directly (`smartctl`, `storcli64`, `zpool status`) and the Scrutiny API.

## Findings

### 1. `/dev/sdb` = ghost of the Jul-7 replaced Seagate
- The flagged entry is WWN `0x5000c500ac21b85c` - the **old, genuinely-failing** Seagate that was **physically replaced on Jul 7** (see [[Runbook/Randy-sdb-Monitor-Followup-2026-07-08]]). It is no longer installed; its Scrutiny record simply lingered.
- The four Seagates present now (`ac212d63 / ac21b79a / ac21f630 / ac222fb5`, incl. replacement **W460W2XM** = `ac21b79a`) are all SMART **PASSED**, 0 pending / 0 reallocated; `datastore` is ONLINE with no errors.
- After the Jul-8 reboot the `/dev/sd*` letters shifted, so the *current* `/dev/sdb` is the healthy replacement - a **different physical drive** than the flagged ghost.
- Scrutiny had flagged the ghost via its **Backblaze heuristic** (`device_status = 2` = failed_scrutiny), not the drive's own SMART.

### 2. `/dev/sdw` = the AVAGO 3108 boot RAID-1 virtual drive
- `sdw` is the **boot mirror VD**, not a bare disk. `smartctl` can't read real SMART through the MegaRAID VD → temp/POH come back 0/∞ and Scrutiny records a failed self-assessment (`device_status = 1` = failed_smart).
- Ground truth via StorCLI: VD 0 "Boot" RAID1 = **Optimal**; both ST200FM0053 SSDs **Onln**, Health **OK**, endurance used **2 % / 4 %**.

## Fix applied

**Scrutiny web** (pve3 LXC 103, Docker `grafana-scrutiny-1`, config/DB at `/opt/grafana/scrutiny-data/`):
- Deleted both stale device records via `DELETE /api/device/<wwn>` - Seagate ghost `0x5000c500ac21b85c` and boot VD `0x600304801b53ad0131cb62472885ed15`.
- Set status to **SMART-only** via `POST /api/settings` (DB-backed - the yaml is a no-op): `metrics.status_threshold=1`, `metrics.status_filter_attributes=1` (critical). Device colour now follows each drive's own SMART verdict, so Seagate cosmetic raw-attribute quirks can't red-out present drives.
  - **Trade-off:** disables Scrutiny's Backblaze predictive heuristic (ZFS scrubs remain the real integrity net). To keep predictive-but-critical-only instead: `status_threshold=3`, `status_filter_attributes=1`.

**Randy collector** (`/opt/scrutiny/config/collector.yaml`):
- Added `commands.metrics_smartctl_bin: /usr/local/sbin/scrutiny-smartctl-wrapper.sh`.
- The wrapper filters **only** the boot VD out of `smartctl --scan --json` by its stable by-id WWN (`scsi-3600304801b53ad0131cb62472885ed15`) - survives reboots / sd-renumbering, and is fail-safe (any error → unmodified scan, so it can never hide a real drive).
- The two physical boot SSDs stay monitored via `-d megaraid,28/29` (serial-keyed `z3e01fv4` / `z3e01ksv`, both green).

**Backups:** `collector.yaml.bak-*` on Randy; `scrutiny.db.bak-*` in LXC 103.

## Result
Scrutiny dashboard: **zero red devices**. Boot mirror is monitored via the two real SSDs; the opaque VD is no longer scanned.

## Watch item
Replacement Seagate **W460W2XM** is an aged used spare (~52 k POH / ~6 yr) - healthy now, but SMART-only status will still flag it on any real reallocation / pending-sector growth. Carries forward the watch item from [[Runbook/Randy-sdb-Monitor-Followup-2026-07-08]].
