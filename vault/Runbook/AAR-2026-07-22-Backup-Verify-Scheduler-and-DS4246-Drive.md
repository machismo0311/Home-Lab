# After Action Report: Backup-Verify Report Stale — dead scheduler masking a failed DS4246 drive

**Incident ID:** NF-INC-2026-07-22
**Date of incident:** Metric frozen 2026-07-19 16:55 EDT → diagnosed/mitigated 2026-07-22 ~16:00 EDT.
Underlying drive failure occurred 2026-07-21 17:12 EDT. All times EDT unless noted.
**Duration:** Backup-verify report stale ~71 h (3 missed nightly runs); DS4246 pool `bulk`
degraded from 2026-07-21 17:12 onward (drive replacement still pending at time of writing).
**Severity:** Low–Medium. No service outage and **no data loss**. A monitoring blind spot
(stale metric) hid a real but non-urgent storage fault: `bulk`'s `raidz2-2` vdev lost one
disk and ran with reduced (still-sufficient) redundancy.
**Report filed:** 2026-07-22, same day.

---

## 1. Executive summary

Grafana fired **`BackupVerifyReportStale`** (instance=randy, job=proxmox-nodes), value
~255,729 s (~71 h) — the backup-verify metric on Randy had not refreshed in ~3 days. The
stated hypothesis going in was a **Randy-side crash** — the in-progress LSI 9207-8e /
DS4246 passthrough work hanging the `ds4246` enumeration step and killing the script before
it wrote the `.prom`.

That hypothesis was **wrong**, and the job's architecture is the reason: backup-verify does
**not** run on Randy. It is a scheduled task **on Ares** (the control laptop) — a user cron
that runs the `backup-verify.yml` Ansible playbook against Randy; the role writes the report
and the node-exporter `.prom` on Randy only as its final step. The metric froze at
**2026-07-19 16:55** — the timestamp of a one-off *manual* reinstatement run — and never
updated again. The cron's own `run.log` had **zero `start` lines** after that (the wrapper
writes one unconditionally), proving the job **never fired** on 07-20, 07-21, or 07-22.

Root cause: **Ares is a laptop that suspends overnight, and a plain user crontab has no
catch-up** (anacron does not service user-crontab lines). Every scheduled 06:00 landed while
the machine was asleep and was silently dropped. This is the *same class* of silent-scheduler
failure as NF-INC-2026-07-19 (the 07-18 Ares rebuild wiping the crontab) — only the trigger
differs: last time the cron line was gone, this time the cron line was present but never got
a chance to run. `DS4246` was fully exonerated: it ran `ok` on the last successful run, and
live the exact count command returned 22 disks in 26 ms — no hang.

The important twist surfaced only *after* the fix. Once the hardened role ran and refreshed
the report, `backup_verify_overall_pass` flipped from **1 → 0**: a real check was failing and
the 3-day staleness had been masking it. **Pool `bulk` (the DS4246 shelf), vdev `raidz2-2`,
device `mpathv` was FAULTED** — a Seagate ST4000NM0023 in enclosure **slot 15** that dropped
**both** SAS ports simultaneously at 2026-07-21 17:12 with `DID_TRANSPORT_DISRUPTED`. A
physical reseat on 07-22 restored the SAS *link* (discovery resumed, transport errors gone)
but the drive would **not** spin up to ready (endless `START_UNIT`/`TEST_UNIT_READY` loop,
never attached) — i.e. the reseat ruled out the slot/backplane/cabling and confirmed a **dead
drive**. Replacement is pending; the pool stayed ONLINE/degraded throughout with no data errors.

Two fixes were shipped (below), turning "the alert that fired was the wrong alert" into "the
right alert can fire": scheduler robustness (a Persistent systemd user timer) and role
hardening (a dead job and an unhappy check are now distinguishable metrics).

## 2. Timeline

| Time (EDT) | Event |
|---|---|
| 07-18 23:28 | Ares rebuilt/booted (per NF-INC-2026-07-19); continuous uptime from here (nightly **suspend**, not reboot). |
| 07-19 16:55:41 | **Last successful backup-verify run** — a manual reinstatement run (rc=0, all checks pass, `overall_pass=1`). Writes `backup_verify.prom` on Randy. This is the last time the metric ever updates. |
| 07-20 06:00 | Scheduled cron **misses** — Ares asleep. No `run.log` start line, no `CRON ... CMD` session. (Repeats 07-21, 07-22.) |
| 07-21 17:12:00 | **DS4246 slot-15 drive fails.** Both SAS ports (`sas_address …631a54f9/fa`) time out (`Test Unit Ready` hangs 30–60 s) → task aborts → `DID_TRANSPORT_DISRUPTED` → `device_offlined` → `rejecting I/O to offline device`. ZFS marks `mpathv` FAULTED (3 read / 14 write errors). Unseen — report already stale. |
| 07-22 ~16:00 | `BackupVerifyReportStale` investigated. Established the job runs on **Ares**, not Randy; `.prom` frozen since 07-19 16:55; `run.log` shows no fires since; DS4246 enumerates 22/22 in 26 ms (hypothesis disproven). |
| 07-22 ~16:10 | **Fix Part 1** — Persistent systemd *user* timer installed (`netframe-backup-verify.{service,timer}`), `enable-linger machismo`, cron line retired. Next run 07-23 06:00. |
| 07-22 ~16:16 | **Fix Part 2** deployed (role hardening) and validated by one manual service run: rc=0, `.prom` refreshed (age ~seconds), `run_error=0`. Stale alert cleared. |
| 07-22 ~16:16 | `overall_pass` now **0** → masked fault surfaced: `bulk`/`raidz2-2`/`mpathv` FAULTED. |
| 07-22 ~16:30 | Read-only triage: **both** multipath legs `failed faulty offline`; `sdbn`/`sdbo` offline then absent; SMART unreachable → isolated to the single drive/slot, not HBA/cable (shelf-mates all ONLINE). |
| 07-22 ~17:10 | **Reseat (owner, at rack).** Rescan + `multipath -r`: HBA **re-detects** slot 15 (link restored, no transport errors) but the drive loops on `START_UNIT`/`TEST_UNIT_READY` for 30 s+, never becomes ready, never attaches. **Verdict: dead drive.** Replacement pending. Pool unchanged (no `zpool clear`/`online` run — device never readied). |

## 3. Root cause

**Primary (the alert):** the backup-verify scheduler was a **user cron on a laptop that
suspends overnight**. Vixie cron does not run jobs whose scheduled time passed while the
machine was asleep, and user crontabs get no anacron catch-up, so a 06:00 job on a nightly-
suspended workstation is structurally unreliable. The daemon, crontab entry, and all
prerequisites (venv, vault-pass, vault.yml, SSH key) were healthy — the job simply never got
a tick.

**Secondary (what staleness hid):** a **single Seagate ST4000NM0023 (DS4246 slot 15) failed**
on 07-21, dropping both SAS ports. The reseat proved it was the drive, not the slot/path
(link recovered but the drive never spun up to ready). Because `raidz2-2` is 6-wide raidz2,
one loss left one parity of tolerance and **no data errors** — real but not urgent.

**Contributing (the blind spot):** the alerting conflated two very different conditions. A
**stale** report (dead scheduler → *no* `.prom` written) and a **failing** check (job ran,
something's wrong) were only distinguishable if the job wrote a fresh `.prom` at all. A dead
job produces staleness, which is *quieter* than a failing check — so the more serious signal
(a faulted pool) was suppressed by the less serious one for ~3 days.

## 4. What went well

- The `.prom`/`run.log` design made the diagnosis fast and unambiguous — the unconditional
  `start` line in `run.log` instantly separated "never fired" from "fired and crashed."
- The prior incident's own documentation (the `ares.crontab` header, NF-INC-2026-07-19) had
  already named this exact silent-scheduler failure mode, which reframed the investigation
  away from the Randy-crash hypothesis quickly.
- raidz2 did its job: a drive died with zero data loss and the pool stayed online.
- The reseat-before-replace step paid off diagnostically: it cleanly separated slot/backplane
  from drive without wasting a replacement or a `zpool clear` on an absent device.

## 5. What went wrong / gaps

- A daily infra check was hosted on the least-reliable always-on assumption in the lab (a
  nightly-suspended laptop) with no catch-up. Second time a scheduler-hosting gap on Ares has
  bitten (cf. NF-INC-2026-07-19).
- Staleness masked a faulted pool for ~3 days. `ZfsPoolDegraded` (the direct textfile-collector
  ZFS alert) either did not cover `bulk`'s FAULTED-device state or was likewise not evaluated —
  **to verify** (see actions). Backup-verify should be a backstop, not the only path.

## 6. Corrective actions

### Shipped 2026-07-22
1. **Persistent systemd user timer** replaces the cron (`playbooks/scheduling/systemd/
   netframe-backup-verify.{service,timer}`). `OnCalendar=06:00`, **`Persistent=true`** (a run
   missed during sleep/downtime fires on next wake), `loginctl enable-linger machismo` (runs
   without an active login). Cron line retired (commented) in the live crontab and in the
   versioned `scheduling/ares.crontab`; README updated so a rebuild reproduces the timer.
2. **Role hardening** (`roles/backup_verify/`): the four checks run inside a `block`/`rescue`
   so a *fatal* error still falls through to `report.yml` and writes a `.prom` with a fresh
   timestamp and a new **`backup_verify_run_error 1`** metric — instead of no file. New metric
   emitted alongside `overall_pass`. DS4246 `lsblk` wrapped in **`timeout 30`** so a wedged HBA
   degrades to a recorded fail rather than hanging the play into staleness (a hang is not a task
   failure, so block/rescue alone cannot catch it). Net alert semantics: **stale ⇒ scheduler
   dead**, **run_error/overall=fail ⇒ job ran, a check is unhappy**.

### Pending
3. **Replace the DS4246 slot-15 drive** (Seagate ST4000NM0023, WWN `5000c500631a54fb`). Two
   bays free; shelf is on the 9207-8e in IT mode (drives pass through — no storcli/JBOD step).
   `zpool replace bulk mpathv /dev/disk/by-id/wwn-0x<new>` → resilver. Expected DS4246 count
   stays 22.
4. **Add a `BackupVerifyRunError` alert** (on `backup_verify_run_error == 1`) in the
   `netframe-monitoring-stack` repo to complete the three-way signal. `BackupVerifyFailing`
   (on `overall_pass == 0`) already covers today's fault and should be firing now.
5. **Verify `ZfsPoolDegraded` coverage of `bulk`** — confirm the ZFS textfile-collector alert
   catches a FAULTED *device* (not just pool state != ONLINE), so a future drive failure is
   caught directly, not only via backup-verify.
6. **Confirm the timer fires 07-23 06:00** (`systemctl --user list-timers`), and consider
   giving the not-yet-reinstated 06:30 hardening-drift job the same Persistent-timer treatment
   when it returns.

## 7. Lessons

- **Host recurring infra checks on something that is actually always on, or make the schedule
  catch-up-safe.** A user cron on a nightly-suspended laptop is neither. `Persistent=true` is
  the minimum bar; an always-on node would be better still.
- **A quiet alert can suppress a loud one.** When "no data" and "bad data" map to different
  alerts, ensure the "no data" (staleness) path cannot mask the "bad data" (failing) path —
  and always emit a heartbeat/failure metric rather than nothing.
- **Reseat before replace** on a dual-ported SAS drive that drops both paths: if the link
  returns but the drive won't ready, it's the drive; if the link stays dead, it's the
  slot/backplane/cabling. Cheap, decisive triage.

---

*Draft — not yet committed. To publish: commit in the `Home-Lab` submodule, push, bump the
superproject pointer, and mirror into `Vaults/homelab-vault/` per the vault-sync convention.*
