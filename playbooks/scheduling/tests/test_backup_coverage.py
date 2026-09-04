#!/usr/bin/env python3
"""Tests for the backup-coverage invariant checker.

Hermetic: every case is a fixture of job definitions. No cluster is contacted and no job is read
from or written to production.

The split that motivated this - moving VM 202 out of the shared RKE2 job into its own - fails
silently in both directions. Drop the guest from both jobs and it stops being backed up while every
remaining job still succeeds. Leave it in both and it competes with itself for the node's global
vzdump lock, which is the contention the split existed to remove. Neither appears in a task log, so
both are pinned here.

Runs without pytest, like the other scheduling tests.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCHED = os.path.abspath(os.path.join(HERE, ".."))
SCRIPT = os.path.join(SCHED, "backup-coverage.py")

FAILURES = []


def chk(label, cond, detail=""):
    if cond:
        print("  PASS  %s" % label)
    else:
        print("  FAIL  %s%s" % (label, ("  [%s]" % detail) if detail else ""))
        FAILURES.append(label)


def job(jid, vmid, schedule, enabled=1):
    return {"id": jid, "type": "vzdump", "vmid": vmid, "schedule": schedule, "enabled": enabled}


# The estate after the split: CT 103 in the 02:00 LXC job, 201/203 still at 04:00, 202 on its own.
AFTER = [
    job("lxc-0200", "101,102,103,105,106,107,108", "02:00"),
    job("obs-0230", "210", "02:30"),
    job("opnsense-0300", "100", "03:00"),
    job("wazuh-0300", "104", "03:00"),
    job("ha-0330", "110", "03:30"),
    job("rke2-0400", "201,203", "04:00"),
    job("am-0430", "109", "04:30"),
    job("obsui-0500", "111", "05:00"),
    job("vm202-1000", "202", "10:00"),
]
EXPECTED = "100,101,102,103,104,105,106,107,108,109,110,111,201,202,203,210"
PAIRS = "103:202"


def run(jobs, expected=EXPECTED, pairs=PAIRS):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(jobs, fh)
        path = fh.name
    try:
        p = subprocess.run(
            [sys.executable, SCRIPT, "--jobs", path, "--expected", expected,
             "--no-share-schedule", pairs],
            capture_output=True, text=True, timeout=60, check=False)
        try:
            return json.loads(p.stdout), p.returncode
        except ValueError:
            return None, p.returncode
    finally:
        os.unlink(path)


print("--- the estate after the split ---")
rep, rc = run(AFTER)
chk("the post-split configuration is coherent", rep["status"] == "ok", json.dumps(rep["findings"]))
chk("...and exits zero", rc == 0)
chk("every expected guest is covered", rep["covered_guests"] == rep["expected_guests"] == 16)
chk("202 sits alone on its own schedule",
    rep["coverage"]["202"] == [{"job": "vm202-1000", "schedule": "10:00", "enabled": 1}])
chk("201 keeps the original job and time",
    rep["coverage"]["201"][0]["job"] == "rke2-0400"
    and rep["coverage"]["201"][0]["schedule"] == "04:00")
chk("203 keeps the original job and time",
    rep["coverage"]["203"][0]["job"] == "rke2-0400"
    and rep["coverage"]["203"][0]["schedule"] == "04:00")
chk("202 no longer shares a schedule with CT 103", rep["schedule_clashes"] == [])

print()
print("--- the ways a split goes wrong ---")
dropped_201 = [j for j in AFTER if j["id"] != "rke2-0400"] + [job("rke2-0400", "203", "04:00")]
rep, rc = run(dropped_201)
chk("dropping 201 from the shared job is caught", rep["status"] == "fail")
chk("...as a missing guest",
    any(f["vmid"] == "201" and f["issue"] == "missing" for f in rep["findings"]))
chk("...and exits nonzero", rc == 1)

dropped_203 = [j for j in AFTER if j["id"] != "rke2-0400"] + [job("rke2-0400", "201", "04:00")]
rep, _ = run(dropped_203)
chk("dropping 203 from the shared job is caught",
    any(f["vmid"] == "203" and f["issue"] == "missing" for f in rep["findings"]))

still_in_both = [j for j in AFTER if j["id"] != "rke2-0400"] + [job("rke2-0400", "201,202,203",
                                                                   "04:00")]
rep, _ = run(still_in_both)
chk("leaving 202 in both jobs is caught", rep["status"] == "fail")
chk("...as a duplicate",
    any(f["vmid"] == "202" and f["issue"] == "duplicated" for f in rep["findings"]))
chk("...naming both jobs",
    any("rke2-0400" in f["detail"] and "vm202-1000" in f["detail"]
        for f in rep["findings"] if f["vmid"] == "202"))

in_neither = [j for j in AFTER if j["id"] not in ("rke2-0400", "vm202-1000")] + [
    job("rke2-0400", "201,203", "04:00")]
rep, _ = run(in_neither)
chk("removing 202 from both jobs is caught", rep["status"] == "fail")
chk("...as a missing guest, not silence",
    any(f["vmid"] == "202" and f["issue"] == "missing" for f in rep["findings"]))

print()
print("--- contention and unrelated drift ---")
clashing = [j for j in AFTER if j["id"] != "vm202-1000"] + [job("vm202-1000", "202", "02:00")]
rep, _ = run(clashing)
chk("scheduling 202 back onto CT 103's slot is caught", rep["status"] == "fail")
chk("...as a schedule clash", rep["schedule_clashes"]
    and rep["schedule_clashes"][0]["schedule"] == "02:00")
chk("...naming both guests", sorted(rep["schedule_clashes"][0]["vmids"]) == ["103", "202"])

moved_other = [j for j in AFTER if j["id"] != "ha-0330"] + [job("ha-0330", "110", "10:00")]
rep, _ = run(moved_other)
chk("an unrelated job moving is visible in the coverage map",
    rep["coverage"]["110"][0]["schedule"] == "10:00")
chk("...while coverage itself stays intact", rep["status"] == "ok")

disabled = [j for j in AFTER if j["id"] != "vm202-1000"] + [job("vm202-1000", "202", "10:00",
                                                               enabled=0)]
rep, _ = run(disabled)
chk("a disabled job does not count as coverage", rep["status"] == "fail")
chk("...the guest reads as missing",
    any(f["vmid"] == "202" and f["issue"] == "missing" for f in rep["findings"]))

extra = AFTER + [job("stray-0600", "999", "06:00")]
rep, _ = run(extra)
chk("a guest covered but not expected is reported",
    any(f["vmid"] == "999" and f["issue"] == "unexpected" for f in rep["findings"]))

print()
print("--- unreadable input is never a pass ---")
with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
    fh.write("not json")
    bad = fh.name
p = subprocess.run([sys.executable, SCRIPT, "--jobs", bad, "--expected", EXPECTED],
                   capture_output=True, text=True, timeout=60, check=False)
os.unlink(bad)
chk("malformed job definitions exit nonzero", p.returncode != 0)
chk("...and report the parse failure", "did not parse" in p.stdout)
chk("...and never report ok", '"status": "ok"' not in p.stdout)

rep, _ = run([])
chk("an empty job list fails rather than passing vacuously", rep["status"] == "fail")
chk("...with every expected guest missing", len(rep["findings"]) == 16)

print()
print("--- the checker only reads ---")
# The property is "cannot execute anything", proven from the import graph rather than by sniffing
# for tool names - `pvesh` and `vzdump` both appear legitimately in help text and prose.
src = open(SCRIPT, encoding="utf-8").read()
tree = ast.parse(src)
imported = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        imported.update(a.name.split(".")[0] for a in node.names)
    elif isinstance(node, ast.ImportFrom) and node.module:
        imported.add(node.module.split(".")[0])
for forbidden in ("subprocess", "os", "shutil", "socket", "urllib", "requests", "paramiko"):
    chk("the checker cannot reach %r" % forbidden, forbidden not in imported, str(sorted(imported)))
calls = {n.func.attr for n in ast.walk(tree)
         if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
chk("the checker never calls system/popen", not ({"system", "popen", "spawn"} & calls))
opens = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
         and isinstance(n.func, ast.Name) and n.func.id == "open"]
chk("the checker opens nothing for writing",
    all(not any(isinstance(a, ast.Constant) and a.value == "w" for a in c.args) for c in opens))

print()
print("----")
print("BACKUP COVERAGE:", "PASS" if not FAILURES else "FAIL %s" % FAILURES)
sys.exit(1 if FAILURES else 0)
