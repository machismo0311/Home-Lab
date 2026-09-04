#!/usr/bin/env python3
"""Tests for the backup-verification drive-health reader.

Hermetic: every case runs the real script against STUB `lsblk` and `smartctl` binaries placed first
on PATH. No disk is read, no SMART command reaches hardware, and the stubs choose their behaviour
from environment data rather than by executing anything injected.

The property under test is not that the check reports health. It is that it refuses to report health
it cannot see. The check this replaces asked a Scrutiny API that answered HTTP 200 with six-week-old
device records; a verification that passes on stale or absent evidence is worse than one that fails,
because it stops anyone looking. So the cases below spend most of their effort on the ways evidence
can be missing - no disks, a disk short of the expected count, a smartctl that will not run, output
that will not parse, a device with no SMART status - and pin every one of them to a failure.

Runs without pytest, like the other scheduling tests.
"""
from __future__ import annotations

import ast
import json
import os
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SCRIPT = os.path.join(ROOT, "roles", "backup_verify", "files", "drive-health.py")

FAILURES = []


def chk(label, cond, detail=""):
    if cond:
        print("  PASS  %s" % label)
    else:
        print("  FAIL  %s%s" % (label, ("  [%s]" % detail) if detail else ""))
        FAILURES.append(label)


LSBLK_STUB = r'''#!/bin/bash
# Stub lsblk. Emits the fixture in LSBLK_OUT, or fails per LSBLK_MODE.
case "${LSBLK_MODE:-ok}" in
  rc)      exit 3 ;;
  hang)    /bin/sleep 30; exit 0 ;;
esac
printf '%s' "$LSBLK_OUT"
'''

SMARTCTL_STUB = r'''#!/bin/bash
# Stub smartctl. The device is the last argument; behaviour comes from environment data only.
dev="${@: -1}"
case "${SMART_MODE:-ok}" in
  missing_bin) exit 127 ;;
  rc)          echo '{"smartctl":{"exit_status":2}}'; exit 2 ;;
  malformed)   echo 'not json at all'; exit 0 ;;
  nostatus)    echo '{"smartctl":{"exit_status":0},"device":{"name":"'"$dev"'"}}'; exit 0 ;;
  hang)        /bin/sleep 30; exit 0 ;;
esac
if [[ -n "$SMART_FAIL_DEV" && "$dev" == *"$SMART_FAIL_DEV" ]]; then
  echo '{"smartctl":{"exit_status":8},"smart_status":{"passed":false}}'; exit 8
fi
echo '{"smartctl":{"exit_status":0},"smart_status":{"passed":true}}'
'''


def _write(path, body):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def run(lsblk_out, expected=3, smart_mode="ok", lsblk_mode="ok", fail_dev="", timeout=20,
        with_smartctl=True):
    """Run the real script with stubbed tools and return its parsed report."""
    with tempfile.TemporaryDirectory() as bindir:
        _write(os.path.join(bindir, "lsblk"), LSBLK_STUB)
        if with_smartctl:
            _write(os.path.join(bindir, "smartctl"), SMARTCTL_STUB)
        env = dict(os.environ)
        # ONLY the stubs: a tool that is not stubbed is genuinely unreachable, which is how
        # the missing-binary case is proven rather than simulated.
        env["PATH"] = bindir
        env["LSBLK_OUT"] = lsblk_out
        env["LSBLK_MODE"] = lsblk_mode
        env["SMART_MODE"] = smart_mode
        env["SMART_FAIL_DEV"] = fail_dev
        p = subprocess.run(
            [sys.executable, SCRIPT, "--expected", str(expected), "--timeout", str(timeout)],
            capture_output=True, text=True, env=env, timeout=120, check=False)
        try:
            return json.loads(p.stdout), p
        except ValueError:
            return None, p


FOUR_TB = 4000787030016
TWO_TB = 2000398934016

# Three physical disks, each dual-pathed, exactly as the shelf presents them.
THREE_DUAL = "\n".join([
    "sda disk %d 0xaaa" % FOUR_TB,
    "sdb disk %d 0xaaa" % FOUR_TB,
    "sdc disk %d 0xbbb" % FOUR_TB,
    "sdd disk %d 0xbbb" % FOUR_TB,
    "sde disk %d 0xccc" % FOUR_TB,
    "sdf disk %d 0xccc" % FOUR_TB,
]) + "\n"

print("--- every expected drive present and healthy ---")
rep, proc = run(THREE_DUAL, expected=3)
chk("the reader emits a parseable report", rep is not None, proc.stderr[-200:] if proc else "")
chk("status is pass", rep["status"] == "pass", rep["detail"])
chk("dual paths collapse to physical disks", rep["found"] == 3, str(rep["drives"]))
chk("...and the surviving path is deterministic",
    [d["device"] for d in rep["drives"]] == ["sda", "sdc", "sde"], str(rep["drives"]))
chk("every drive reports PASSED", rep["counts"]["PASSED"] == 3)
chk("the detail states both counts", "3 of 3" in rep["detail"], rep["detail"])
chk("no serial number is emitted", "serial" not in json.dumps(rep).lower())
chk("the source is recorded as smartctl", rep["source"] == "smartctl")

print()
print("--- absence never becomes health ---")
rep, _ = run("", expected=3)
chk("zero discovered drives is a failure", rep["status"] == "fail", rep["detail"])
chk("...and says so against the expectation", "0 drive(s) discovered" in rep["detail"])

rep, _ = run(THREE_DUAL, expected=0)
chk("zero expected drives is never a pass", rep["status"] != "pass", rep["detail"])
chk("...it is unavailable, not a silent success", rep["status"] == "unavailable")

missing_one = "\n".join(THREE_DUAL.strip().splitlines()[:4]) + "\n"
rep, _ = run(missing_one, expected=3)
chk("a missing expected drive is a failure", rep["status"] == "fail")
chk("...naming the shortfall", "2 drive(s) discovered against 3" in rep["detail"], rep["detail"])

extra = THREE_DUAL + "sdg disk %d 0xddd\n" % FOUR_TB
rep, _ = run(extra, expected=3)
chk("an unexpected extra drive is a failure", rep["status"] == "fail")
chk("...naming the excess", "4 drive(s) discovered against 3" in rep["detail"], rep["detail"])

print()
print("--- one bad drive among many ---")
rep, _ = run(THREE_DUAL, expected=3, fail_dev="sdc")
chk("a single SMART failure fails the whole check", rep["status"] == "fail")
chk("...counted", rep["counts"]["FAILED"] == 1 and rep["counts"]["PASSED"] == 2)
chk("...and the offending disk is named by WWN", rep["failed"] == ["0xbbb"], str(rep["failed"]))
chk("...without hiding the healthy ones", rep["found"] == 3)

print()
print("--- smartctl that cannot answer ---")
rep, _ = run(THREE_DUAL, expected=3, smart_mode="rc")
chk("a nonzero smartctl with no status is unsupported, not passed",
    rep["counts"]["SMART_UNSUPPORTED"] == 3, str(rep["counts"]))
chk("...and the check fails", rep["status"] == "fail")

rep, _ = run(THREE_DUAL, expected=3, smart_mode="malformed")
chk("output that will not parse is unavailable", rep["counts"]["SMART_UNAVAILABLE"] == 3)
chk("...and the check fails", rep["status"] == "fail")
chk("...saying no verdict could be produced", "could not produce a SMART verdict" in rep["detail"])

rep, _ = run(THREE_DUAL, expected=3, smart_mode="nostatus")
chk("a device reporting no SMART status is unsupported", rep["counts"]["SMART_UNSUPPORTED"] == 3)
chk("...and is never a pass", rep["status"] == "fail")

rep, _ = run(THREE_DUAL, expected=3, smart_mode="hang", timeout=1)
chk("a hanging smartctl times out into unavailable",
    rep["counts"]["SMART_UNAVAILABLE"] == 3, str(rep["counts"]))
chk("...and the check fails rather than hanging the report", rep["status"] == "fail")

rep, _ = run(THREE_DUAL, expected=3, with_smartctl=False)
chk("a missing smartctl binary is unavailable", rep["counts"]["SMART_UNAVAILABLE"] == 3)
chk("...and the check fails", rep["status"] == "fail")

print()
print("--- enumeration that cannot answer ---")
rep, _ = run(THREE_DUAL, expected=3, lsblk_mode="rc")
chk("a failing lsblk is unavailable, not zero healthy drives", rep["status"] == "unavailable")
chk("...and reports the enumeration failure", "enumeration failed" in rep["detail"])
chk("...with no drives invented", rep["drives"] == [] and rep["found"] == 0)

rep, _ = run(THREE_DUAL, expected=3, lsblk_mode="hang", timeout=1)
chk("a hanging lsblk times out into unavailable", rep["status"] == "unavailable", rep["detail"])

print()
print("--- the denominator is the shelf inventory, not whatever was found ---")
mixed = THREE_DUAL + "sdz disk %d 0xeee\n" % TWO_TB
rep, _ = run(mixed, expected=3)
chk("a disk outside the shelf capacity band is not counted", rep["found"] == 3, str(rep["drives"]))
chk("...so an unrelated system disk cannot mask a missing shelf disk", rep["status"] == "pass")

partitions = THREE_DUAL + "sda1 part %d 0xaaa\n" % FOUR_TB
rep, _ = run(partitions, expected=3)
chk("partitions are not counted as disks", rep["found"] == 3)

no_wwn = "\n".join([
    "sda disk %d 0xaaa" % FOUR_TB,
    "sdb disk %d" % FOUR_TB,
    "sdc disk %d 0xbbb" % FOUR_TB,
    "sde disk %d 0xccc" % FOUR_TB,
]) + "\n"
rep, _ = run(no_wwn, expected=3)
chk("a disk with no WWN is not counted as a physical disk", rep["found"] == 3, str(rep["drives"]))

single_path = "\n".join([
    "sda disk %d 0xaaa" % FOUR_TB,
    "sdc disk %d 0xbbb" % FOUR_TB,
    "sde disk %d 0xccc" % FOUR_TB,
]) + "\n"
rep, _ = run(single_path, expected=3)
chk("a single-pathed disk counts once, like a dual-pathed one", rep["found"] == 3)
chk("...and still passes", rep["status"] == "pass")

print()
print("--- the Scrutiny API is no longer consulted ---")
src = open(SCRIPT, encoding="utf-8").read()
# Scan executable code only. The module docstring names Scrutiny on purpose - it records why this
# reader exists - and that sentence is not a dependency.
_doc = ast.get_docstring(ast.parse(src)) or ""
body = "\n".join(ln for ln in src.replace(_doc, "").splitlines()
                 if not ln.lstrip().startswith("#"))
for forbidden in ("scrutiny", "8080", "influx", "requests", "urllib", "http"):
    chk("the reader never reaches for %r" % forbidden, forbidden not in body.lower())
chk("no shell is used to run a tool", "shell=True" not in body)
chk("zpool health is not substituted for SMART",
    "zpool" not in body.lower() and "zfs" not in body.lower())

print()
print("--- the role task no longer depends on the Scrutiny API ---")
TASK = os.path.join(ROOT, "roles", "backup_verify", "tasks", "drive_health.yml")
task = open(TASK, encoding="utf-8").read()
task_body = "\n".join(ln for ln in task.splitlines() if not ln.lstrip().startswith("#"))
chk("the task runs the local reader", "drive-health.py" in task_body)
chk("the task makes no HTTP call", "ansible.builtin.uri" not in task_body
    and "uri:" not in task_body)
chk("the task does not reference a Scrutiny URL", "scrutiny_url" not in task_body)
chk("the task keeps the external check identifier", "'scrutiny_drives'" in task_body)
chk("...and records the new evidence source", "'smartctl'" in task_body)
chk("the expected count comes from the shelf inventory, not from the reader",
    "backup_verify_ds4246_expected" in task_body)
chk("a reader that did not run cannot pass",
    "rc == 0" in task_body and "== 'pass'" in task_body)

DEFAULTS = os.path.join(ROOT, "roles", "backup_verify", "defaults", "main.yml")
defaults = open(DEFAULTS, encoding="utf-8").read()
chk("the capacity band is declared once and shared",
    "backup_verify_disk_min_bytes" in defaults
    and "{{ backup_verify_disk_min_bytes }}" in defaults)
chk("no Scrutiny URL default remains", "backup_verify_scrutiny_url" not in defaults)

# A folded YAML scalar keeps the newline on any line indented further than the first, which silently
# split the DS4246 awk program in half and made a healthy 22-disk shelf enumerate as 0. The shared
# band must therefore stay on one physical line with the program that uses it.
awk_lines = [ln for ln in defaults.splitlines() if "$1==\"disk\"" in ln]
chk("the shelf enumeration awk program is one physical line", len(awk_lines) == 1,
    str(awk_lines))
chk("...carrying both bounds of the shared band",
    awk_lines and "backup_verify_disk_min_bytes" in awk_lines[0]
    and "backup_verify_disk_max_bytes" in awk_lines[0], str(awk_lines))
folded = [ln for ln in defaults.splitlines()
          if ln.startswith("  ") and "backup_verify_disk_m" in ln and "{{" in ln]
chk("no continuation line is indented past the folded block's first line",
    all(len(ln) - len(ln.lstrip()) == 2 for ln in folded), str(folded))

print()
print("----")
print("DRIVE HEALTH:", "PASS" if not FAILURES else "FAIL %s" % FAILURES)
sys.exit(1 if FAILURES else 0)
