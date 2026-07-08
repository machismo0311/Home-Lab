# Jarvis `tank` — SMART Long-Test Qualification (2026-07-08)

**Status:** procedure + tooling committed; tests to be run on Jarvis
**Related:** [[Runbook/Jarvis-LLM-Platform-2026-07-05]] · [[Runbook/Cluster-Health-Fixes-2026-07-07]] · [[Runbook/Randy-sdb-Monitor-Followup-2026-07-08]] · [[Infrastructure/Storage]]

## Why
Jarvis's local `tank` pool (raidz1, 5× 2 TB **ST2000NX046x** on the onboard HBA330
SAS-3 3008, IT mode) was built 2026-07-08 and verified `ONLINE`, but — unlike
Randy's DS4246 drives — the five members were **never given a long SMART self-test
to qualify them**. They are used enterprise drives, so a read-failure sweep is
worthwhile before they hold the model library and bulk datasets. This mirrors the
qualification pass done on Randy's disks.

## Tooling
`scripts/jarvis-tank-smart-qualify.sh` — resolves the pool members from
`zpool status` (not fixed `sdX` letters, which aren't stable across reboots) and
wraps launch / poll / summarize:

| Command | Action |
|---|---|
| `start`  | kick the SAS extended self-test on every `tank` member (parallel, background on-drive) |
| `status` | show `% of test remaining` / in-progress per drive (default) |
| `result` | pass/fail per drive + grown-defect list + uncorrected/non-medium error counts; exits non-zero on any failure |

## Procedure (run ON Jarvis, as root)
```bash
# from Ares:  ssh jarvis
cd /path/to/Home-Lab/scripts     # or copy the one script over
sudo ./jarvis-tank-smart-qualify.sh start
# ~7-8 h per drive; tests run on the drives themselves, non-disruptive to I/O
sudo ./jarvis-tank-smart-qualify.sh status    # re-run anytime to watch progress
# when all read 0% remaining / complete:
sudo ./jarvis-tank-smart-qualify.sh result
```

## Reading the result
- **Pass** = SAS self-test log newest entry says `Completed` (without error), grown
  defect list ~0, `uncorrected`/`Non-medium error count` = 0.
- **Fail** = any `... failure` in the self-test log (e.g. `Completed: read failure`,
  as Randy's sdb hit at LBA 3875904942). The script prints a `>>> FAIL` line and
  exits non-zero. `tank` is raidz1 (single-parity), so replace a failed member
  promptly:
  ```bash
  zpool status tank
  zpool replace tank <old-by-id> /dev/disk/by-id/<new-disk>
  zpool status tank      # watch resilver -> ONLINE
  ```

## After the tests
Refresh the Scrutiny hub so the dashboard reflects the qualification results
(the collector otherwise only fires on its 00/06/12/18:00 calendar):
```bash
systemctl start scrutiny-collector.service
```
> Note: Jarvis's ST200FM0053 SAS SSDs (OS + `scratch`) return `smartctl` exit 4
> ("checksum error in SMART data structure") every run — cosmetic, drives are
> healthy. The `tank` HDDs are on the same HBA; if a new disk shows the same
> exit-4 noise it is not a fault. See [[Runbook/Cluster-Health-Fixes-2026-07-07]] §3.4.

## Follow-up
- [ ] Run `start` on Jarvis, let complete (~7-8 h), capture `result`.
- [ ] Record pass/fail + any grown-defect counts back here.
- [ ] Re-run scrutiny collector to populate the hub.
