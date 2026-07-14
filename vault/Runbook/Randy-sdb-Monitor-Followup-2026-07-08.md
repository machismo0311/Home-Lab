# Randy /dev/sdb - Monitor Follow-up & Closure (2026-07-08)

**Status:** RESOLVED / verified - no action required (watch item noted below)

## Trigger
First run of the new NetFRAME cluster health monitor (deployed on Jarvis 2026-07-08,
see `project-netframe-monitor`) flagged `/dev/sdb` on **Randy** via its `journal_errors`
check: `smartd` lines reporting *21–23 Currently unreadable (pending) sectors* and
*previous self-test completed with error (read test element)*.

## Reconciliation
Those `smartd` entries are **historical**, timestamped **Jul 07 04:21–07:51** - i.e.
*before* the sdb replacement already recorded in git ("Randy sdb replacement complete").
The monitor's `journal_errors` check reads the whole current boot journal, so it replays
pre-replacement noise until Randy's next reboot rotates the boot journal.

Live SMART on the **current** sdb is clean:

| Field | Value |
|---|---|
| Device | ST2000NX0423 (DELL), FW NB33 |
| Serial | **W460W2XM** |
| `by-id` | `ata-ST2000NX0423_W460W2XM` (symlink dated Jul 07 10:18 = replacement) |
| SMART health | PASSED |
| Current_Pending_Sector | **0** |
| Reallocated_Sector_Ct | **0** |
| Offline_Uncorrectable | **0** |
| Last self-test | completed without error |
| Post-replacement smartd errors | **none** since Jul 07 10:18 |

## Conclusion
The Jul 7 replacement fixed the failing disk; the new W460W2XM is healthy. The monitor
alert was a stale-journal artifact, not a live fault. No replacement needed.

## Watch item
Replacement is a used spare - **Power_On_Hours ≈ 52,186 (~6 yr)**. Healthy now (0
pending / 0 reallocated) but aged; Scrutiny/this monitor will catch any future
degradation. Consider a fresher spare if reallocations begin.

## Note for the monitor
Consider tightening the `journal_errors` window on Randy to `--since` last boot-of-interest
or filtering resolved-device noise, so historical pre-replacement `smartd` lines stop
surfacing until reboot. Low priority - informational only, does not affect verdicts.
