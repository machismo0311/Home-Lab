#!/usr/bin/env python3
"""Tests for the PBS host-type backup group freshness reader.

Hermetic: every case runs the real script against a STUB `proxmox-backup-debug` placed first on
PATH. No datastore is read, no PBS API is contacted, and the stub chooses its behaviour from
environment data rather than by executing anything injected.

The property under test is not that the check reports fresh backups. It is that it cannot be made
to report freshness that does not belong to the group being asked about, and that it refuses to
report anything at all when it could not ask. The defect this check exists to close was a PASS:
between 2026-07-02 and 2026-09-13 the group host/quarkylab held a single snapshot, and across the
770 hours still in Prometheus the report was green for 578 of them, because the datastore check
looked at the newest snapshot anywhere and the guest check matched numeric VMIDs against a hostname.
Replayed against the complete snapshot record, this reader fails all 72 daily reports in the gap. So the cases below spend most
of their effort on the ways a stale group can be made to look healthy - a fresh sibling group, fresh
guests, a fresh datastore, a guest whose id collides with a host group - and on the ways the source
can fail to answer, and pin every one of them away from `pass`.

Runs without pytest, like the other scheduling tests.
"""
from __future__ import annotations

import ast
import calendar
import json
import os
import stat
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
SCRIPT = os.path.join(ROOT, "roles", "backup_verify", "files", "pbs-host-freshness.py")



def chk(label, cond, detail=""):
    """Assert one invariant.

    Kept as a helper so every check label below is preserved verbatim from the
    original script. It raises instead of appending to a module-level list, so a
    violated invariant is a named failing test rather than a bare exit code.
    """
    assert cond, "%s%s" % (label, ("  [%s]" % detail) if detail else "")


def epoch(iso):
    """The estate's snapshot names are UTC ISO-8601; ages are computed from them."""
    return calendar.timegm(time.strptime(iso, "%Y-%m-%dT%H:%M:%SZ"))


# The real history, so the regression cases below are the incident and not an analogy.
JULY = epoch("2026-07-02T02:39:35Z")          # the only host/quarkylab snapshot for 73 days
SEP_HOST = epoch("2026-09-13T05:02:34Z")      # the first unattended snapshot after the fix
SEP_WORKSPACE = epoch("2026-09-13T05:30:54Z")  # the sibling host group, never stale
NOW = epoch("2026-09-13T10:01:02Z")           # the hour the report is actually generated

STUB = r'''#!/bin/bash
# Stub proxmox-backup-debug. Answers `api get <path> --output-format json` from environment data.
case "${PBSDBG_MODE:-ok}" in
  rc)        exit 5 ;;
  malformed) echo 'not json at all'; exit 0 ;;
  notalist)  echo '{"store":"datastore"}'; exit 0 ;;
  nostores)  echo '[]'; exit 0 ;;
  hang)      /bin/sleep 30; exit 0 ;;
esac
path="$3"
if [ "$path" = "/admin/datastore" ]; then
  printf '%s' "$PBSDBG_STORES"
  exit 0
fi
if [ "${PBSDBG_MODE:-ok}" = "snapfail" ]; then exit 7; fi
printf '%s' "$PBSDBG_SNAPS"
'''


def snap(btype, bid, when, files=("index.json.blob",)):
    return {"backup-type": btype, "backup-id": bid, "backup-time": when,
            "files": [{"filename": f} for f in files]}


def run(snapshots, expected, now=NOW, max_age=25, mode="ok", stores=None, extra=(), timeout=60):
    """Run the real reader against the stub and return (rc, parsed-json-or-None, stderr)."""
    with tempfile.TemporaryDirectory() as tmp:
        stub = os.path.join(tmp, "proxmox-backup-debug")
        with open(stub, "w", encoding="utf-8") as fh:
            fh.write(STUB)
        os.chmod(stub, os.stat(stub).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        env = dict(os.environ)
        env["PATH"] = tmp + os.pathsep + env.get("PATH", "")
        env["PBSDBG_MODE"] = mode
        env["PBSDBG_SNAPS"] = json.dumps(snapshots)
        env["PBSDBG_STORES"] = json.dumps(stores or [{"store": "datastore"}])
        argv = [sys.executable, SCRIPT, "--expected", expected,
                "--max-age-hours", str(max_age), "--now", str(now), "--timeout", "5"]
        argv.extend(extra)
        p = subprocess.run(argv, capture_output=True, text=True, env=env,
                           timeout=timeout, check=False)
    try:
        return p.returncode, json.loads(p.stdout), p.stderr
    except ValueError:
        return p.returncode, None, p.stderr + p.stdout


def run_without_stub(expected):
    """Run with an empty PATH, so the reader cannot find PBS's CLI at all."""
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ)
        env["PATH"] = tmp
        p = subprocess.run([sys.executable, SCRIPT, "--expected", expected,
                            "--now", str(NOW), "--timeout", "5"],
                           capture_output=True, text=True, env=env, timeout=60, check=False)
    try:
        return p.returncode, json.loads(p.stdout), p.stderr
    except ValueError:
        return p.returncode, None, p.stderr + p.stdout


def group(doc, name):
    for g in doc.get("groups", []):
        if g["backup_id"] == name:
            return g
    return None


# --- T1: a fresh host group is healthy --------------------------------------------------------


# T1  fresh host group -> pass
def test_t1_fresh_host_group_pass():
    _rc, d, _err = run([snap("host", "quarkylab", SEP_HOST),
                        snap("host", "quarkylab-workspace", SEP_WORKSPACE)],
                       "quarkylab,quarkylab-workspace")
    chk("T1 status is pass", d and d["status"] == "pass", d and d.get("detail"))
    chk("T1 both groups fresh", d and all(g["state"] == "fresh" for g in d["groups"]))
    chk("T1 age is measured, not assumed",
        d and group(d, "quarkylab")["age_hours"] == round((NOW - SEP_HOST) / 3600.0, 1),
        d and group(d, "quarkylab")["age_hours"])
    chk("T1 counts are zero", d and d["stale"] == 0 and d["missing"] == 0 and d["unknown"] == 0)
    chk("T1 threshold is reported", d and d["threshold_hours"] == 25)

    # --- T2: a stale group fails ------------------------------------------------------------------


# T2  stale host group -> fail
def test_t2_stale_host_group_fail():
    _rc, d, _err = run([snap("host", "quarkylab", JULY),
                        snap("host", "quarkylab-workspace", SEP_WORKSPACE)],
                       "quarkylab,quarkylab-workspace")
    chk("T2 status is fail", d and d["status"] == "fail", d and d.get("detail"))
    chk("T2 quarkylab is stale", d and group(d, "quarkylab")["state"] == "stale")
    chk("T2 stale is not missing", d and d["stale"] == 1 and d["missing"] == 0)
    chk("T2 the sibling stays fresh", d and group(d, "quarkylab-workspace")["state"] == "fresh")
    chk("T2 detail names the group", d and "host/quarkylab stale" in d["detail"], d and d["detail"])
    chk("T2 age reflects the real gap",
        d and group(d, "quarkylab")["age_hours"] > 1700, d and group(d, "quarkylab")["age_hours"])

    # --- T3: an absent group fails, and is distinguishable from stale -----------------------------


# T3  missing host group -> fail
def test_t3_missing_host_group_fail():
    _rc, d, _err = run([snap("host", "quarkylab-workspace", SEP_WORKSPACE)],
                       "quarkylab,quarkylab-workspace")
    chk("T3 status is fail", d and d["status"] == "fail", d and d.get("detail"))
    chk("T3 quarkylab is missing", d and group(d, "quarkylab")["state"] == "missing")
    chk("T3 missing is not stale", d and d["missing"] == 1 and d["stale"] == 0)
    chk("T3 present is false", d and group(d, "quarkylab")["present"] is False)
    chk("T3 age is not fabricated", d and group(d, "quarkylab")["age_hours"] == -1)

    # --- T4: the source cannot be asked -> UNKNOWN, never stale -----------------------------------


# T4  source unavailable -> unavailable/unknown, never stale
def test_t4_source_unavailable_unavailable_unknown_never_stale():
    for label, kwargs in (
        ("binary exits nonzero", {"mode": "rc"}),
        ("output does not parse", {"mode": "malformed"}),
        ("output is not a list", {"mode": "notalist"}),
        ("PBS reports no datastore", {"mode": "nostores"}),
        ("snapshot listing fails", {"mode": "snapfail"}),
        ("the call hangs", {"mode": "hang"}),
    ):
        _rc, d, err = run([snap("host", "quarkylab", SEP_HOST)], "quarkylab", **kwargs)
        chk("T4 %s -> unavailable" % label, d and d["status"] == "unavailable", err)
        chk("T4 %s -> state unknown" % label,
            d and group(d, "quarkylab")["state"] == "unknown")
        chk("T4 %s -> never stale or missing" % label,
            d and d["stale"] == 0 and d["missing"] == 0 and d["unknown"] == 1)
        chk("T4 %s -> never fresh" % label, d and group(d, "quarkylab")["fresh"] is False)
        chk("T4 %s -> source_available false" % label, d and d["source_available"] is False)
        chk("T4 %s -> detail says UNKNOWN, not stale" % label,
            d and "UNKNOWN" in d["detail"] and "stale" not in d["detail"], d and d["detail"])

    _rc, d, err = run_without_stub("quarkylab")
    chk("T4 PBS CLI absent -> unavailable", d and d["status"] == "unavailable", err)
    chk("T4 PBS CLI absent -> unknown", d and group(d, "quarkylab")["state"] == "unknown")

    # --- T5: THE REGRESSION. A fresh datastore must not mask a stale host group -------------------
    # This is the 73-day false green, reconstructed. Everything else in the datastore is current:
    # twelve guests backed up in the last four hours, the sibling host group backed up this morning,
    # and therefore a datastore whose newest snapshot is minutes old. Only host/quarkylab is stale.
    # The old checks passed on exactly this input.


# T5  fresh datastore does NOT mask a stale host group  (the 73-day false green)
def test_t5_fresh_datastore_does_not_mask_a_stale_host_group_the_73():
    POPULATED = [snap("host", "quarkylab", JULY),
                 snap("host", "quarkylab-workspace", SEP_WORKSPACE)]
    for vmid in (100, 101, 102, 103, 104, 105, 106, 107, 108, 201, 202, 203):
        POPULATED.append(snap("vm", str(vmid), NOW - 3600))
    _rc, d, _err = run(POPULATED, "quarkylab,quarkylab-workspace")
    chk("T5 status is fail despite a fresh datastore", d and d["status"] == "fail", d and d.get("detail"))
    chk("T5 the stale group is identified", d and group(d, "quarkylab")["state"] == "stale")
    chk("T5 exactly one group is stale", d and d["stale"] == 1)
    chk("T5 the newest snapshot in the datastore is NOT borrowed",
        d and group(d, "quarkylab")["newest_epoch"] == JULY,
        d and group(d, "quarkylab")["newest_epoch"])
    chk("T5 the group's own snapshot count is used",
        d and group(d, "quarkylab")["snapshots"] == 1)

    # The precise mechanism of the old blind spot, inverted: the guest check matched `backup-id`
    # with no type filter, so a host group named for a hostname was never selected. The mirror of
    # that bug would be a guest whose id equals a host group name satisfying this check. It must not.


# T5b guest snapshots never satisfy a host group, whatever their backup-id
def test_t5b_guest_snapshots_never_satisfy_a_host_group_whatever_th():
    _rc, d, _err = run([snap("vm", "quarkylab", NOW - 600),
                        snap("ct", "quarkylab", NOW - 600)], "quarkylab")
    chk("T5b a same-named guest does not make the host group present",
        d and group(d, "quarkylab")["state"] == "missing", d and d.get("detail"))
    chk("T5b status is fail", d and d["status"] == "fail")

    # --- Boundary: the threshold is a real edge, not a rounding ------------------------------------


# B   threshold boundary
def test_b_threshold_boundary():
    _rc, d, _err = run([snap("host", "quarkylab", NOW - 25 * 3600)], "quarkylab")
    chk("B exactly at the threshold is fresh", d and d["status"] == "pass", d and d.get("detail"))
    _rc, d, _err = run([snap("host", "quarkylab", NOW - 25 * 3600 - 1)], "quarkylab")
    chk("B one second past the threshold is stale", d and d["status"] == "fail", d and d.get("detail"))
    # Every group, in every case, must agree with itself: `fresh` is exactly `state == fresh`.
    for _when in (NOW - 25 * 3600, NOW - 25 * 3600 - 1, SEP_HOST, JULY):
        _rc, d, _err = run([snap("host", "quarkylab", _when)], "quarkylab")
        g = d and group(d, "quarkylab")
        chk("B fresh and state agree at age %ss" % (NOW - _when),
            g and g["fresh"] == (g["state"] == "fresh"), g)
    _rc, d, _err = run([snap("host", "quarkylab", NOW - 25 * 3600)], "quarkylab")
    chk("B at the threshold the fresh FIELD is true, not only the status",
        d and group(d, "quarkylab")["fresh"] is True, d and group(d, "quarkylab"))

    # --- Declared denominator: nothing expected is never a pass -----------------------------------


# D   the denominator is declared, not discovered
def test_d_the_denominator_is_declared_not_discovered():
    _rc, d, _err = run([snap("host", "quarkylab", SEP_HOST)], "")
    chk("D no expected groups -> unavailable", d and d["status"] == "unavailable", d and d.get("detail"))
    chk("D no expected groups -> never pass", d and d["status"] != "pass")
    chk("D an undeclared group is not silently adopted", d and d["groups"] == [])

    # --- Malformed snapshot rows are ignored, not fatal, and never count as freshness --------------


# M   malformed snapshot rows
def test_m_malformed_snapshot_rows():
    _rc, d, _err = run(["not-an-object",
                        {"backup-type": "host", "backup-id": "quarkylab"},
                        {"backup-type": "host", "backup-time": SEP_HOST},
                        {"backup-type": "host", "backup-id": "quarkylab", "backup-time": "soon"},
                        {"backup-type": "host", "backup-id": "quarkylab", "backup-time": True}],
                       "quarkylab")
    chk("M unusable rows do not crash the reader", d is not None)
    chk("M unusable rows are not freshness", d and group(d, "quarkylab")["state"] == "missing",
        d and d.get("detail"))

    # --- Multi-datastore: one unreachable datastore must not produce a false MISSING ---------------


# X   a datastore that will not answer is UNKNOWN, not a missing group
def test_x_a_datastore_that_will_not_answer_is_unknown_not_a_missin():
    _rc, d, _err = run([snap("host", "quarkylab", SEP_HOST)], "quarkylab",
                       mode="snapfail", stores=[{"store": "datastore"}, {"store": "second"}])
    chk("X status is unavailable", d and d["status"] == "unavailable", d and d.get("detail"))
    chk("X the group is unknown, not missing", d and group(d, "quarkylab")["state"] == "unknown")

    # --- The reader is read-only ------------------------------------------------------------------


# R   the reader cannot mutate a datastore
def test_r_the_reader_cannot_mutate_a_datastore():
    def code_only(path):
        """The script with every docstring removed: prose that names a verb is not a call to it."""
        tree = ast.parse(open(path, encoding="utf-8").read())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                body = getattr(node, "body", [])
                if (body and isinstance(body[0], ast.Expr)
                        and isinstance(body[0].value, ast.Constant)
                        and isinstance(body[0].value.value, str)):
                    body.pop(0)
        return ast.unparse(tree)


    SRC = code_only(SCRIPT)
    for verb in ("prune", "forget", "garbage-collect", "\"backup\"", "rm(", "unlink", "rmtree",
                 "shutil.move", "os.remove", "api put", "api post", "api delete"):
        chk("R source contains no %s" % verb.strip('"('), verb not in SRC)
    NORM = SRC.replace("'", '"')
    chk("R there is exactly one API call site and it is a GET",
        NORM.count('"api"') == 1 and NORM.count('"api", "get"') == 1)
    chk("R no shell is ever used", "shell=True" not in SRC)



if __name__ == "__main__":
    fns = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in fns:
        try:
            fn()
            print("  PASS  %s" % name)
        except AssertionError as exc:
            failed += 1
            print("  FAIL  %s: %s" % (name, exc))
        except Exception as exc:
            # Recorded, not swallowed: a non-assertion failure must not abort the rest.
            # `Exception` deliberately does not catch KeyboardInterrupt or SystemExit.
            failed += 1
            print("  FAIL  %s: %s: %s" % (name, type(exc).__name__, exc))
    print("%d/%d passed" % (len(fns) - failed, len(fns)))
    sys.exit(1 if failed else 0)
