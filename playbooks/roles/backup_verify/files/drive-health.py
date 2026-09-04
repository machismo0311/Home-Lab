#!/usr/bin/env python3
"""Drive health for backup verification, read directly from the host's own SMART stack.

WHY THIS REPLACED THE SCRUTINY API. The previous check asked a Scrutiny instance for a device
summary. That deployment is incomplete: its collectors last wrote on 2026-07-25 and its web tier
lives on the same container that spends five hours a day being backed up on a saturated disk. The
failure mode that matters is not that it was unreachable - it is that it ANSWERS, with six-week-old
device records. A check that passes on stale data is worse than one that fails, because nobody looks
at it again. So drive health is now read from smartctl on the host that owns the disks.

THE DENOMINATOR IS NOT "WHATEVER WE FOUND". A verification whose expected count is derived from what
it observed can never detect a missing disk, which is the single most important thing it should
catch. The expected count is supplied by the caller and comes from the same authoritative inventory
the DS4246 enumeration check already uses: whole disks inside the shelf's capacity band,
deduplicated by WWN because the shelf is dual-pathed and every physical disk appears twice.

FAIL CLOSED, EVERYWHERE. Zero expected, zero discovered, a count mismatch, a smartctl that will not
run, output that will not parse, a device whose SMART status is absent, or any device reporting
failure - each is a failure. "We could not tell" never becomes "pass". The only PASS is every
expected disk accounted for and every one of them reporting healthy.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys

SCHEMA = "netframe-drive-health/v1"

PASS = "pass"
FAIL = "fail"
UNAVAILABLE = "unavailable"

# Per-drive verdicts. UNSUPPORTED is kept apart from UNAVAILABLE: a disk that cannot report SMART is
# a different fact from a disk we failed to ask, and neither is a healthy disk.
DRIVE_PASS = "PASSED"
DRIVE_FAIL = "FAILED"
DRIVE_UNSUPPORTED = "SMART_UNSUPPORTED"
DRIVE_UNAVAILABLE = "SMART_UNAVAILABLE"

# The shelf's capacity band, matching the DS4246 enumeration check rather than restating a new one.
DEFAULT_MIN_BYTES = 3_500_000_000_000
DEFAULT_MAX_BYTES = 4_600_000_000_000
DEFAULT_TIMEOUT = 20


def _run(cmd, timeout):
    """One bounded local command. Never a shell, so nothing here can execute composed input."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except (OSError, ValueError) as exc:
        return None, type(exc).__name__
    return p, None


def discover(min_bytes, max_bytes, timeout):
    """Whole disks in the shelf band, one device path per physical disk.

    Deduplication is by WWN and the surviving path is the lexicographically first, so two runs on an
    unchanged shelf pick the same device and the report does not churn.
    """
    if not shutil.which("lsblk"):
        return None, "lsblk is not available"
    p, err = _run(["lsblk", "-dnb", "-o", "NAME,TYPE,SIZE,WWN"], timeout)
    if err:
        return None, "lsblk %s" % err
    if p.returncode != 0:
        return None, "lsblk exited %d" % p.returncode
    by_wwn = {}
    for line in p.stdout.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        name, kind, size, wwn = parts[0], parts[1], parts[2], parts[3]
        if kind != "disk" or not wwn:
            continue
        try:
            nbytes = int(size)
        except ValueError:
            continue
        if not (min_bytes < nbytes < max_bytes):
            continue
        if wwn not in by_wwn or name < by_wwn[wwn]:
            by_wwn[wwn] = name
    return by_wwn, None


def smart_status(device, timeout):
    """The device's own SMART overall verdict, via smartctl's JSON output.

    smartctl's exit status is a bit field and a non-zero value does not by itself mean the disk is
    bad; bit 3 is the failing-disk bit. The verdict is therefore taken from smart_status.passed when
    the device reports one, and the absence of that field is recorded as unsupported rather than
    quietly treated as either outcome.
    """
    if not shutil.which("smartctl"):
        return DRIVE_UNAVAILABLE, "smartctl is not available"
    p, err = _run(["smartctl", "-H", "--json=c", "/dev/%s" % device], timeout)
    if err:
        return DRIVE_UNAVAILABLE, "smartctl %s" % err
    try:
        doc = json.loads(p.stdout)
    except (ValueError, TypeError):
        return DRIVE_UNAVAILABLE, "smartctl output did not parse as JSON"
    if not isinstance(doc, dict):
        return DRIVE_UNAVAILABLE, "smartctl output was not an object"
    status = doc.get("smart_status")
    if not isinstance(status, dict) or "passed" not in status:
        # Includes devices behind controllers that do not pass SMART through.
        return DRIVE_UNSUPPORTED, "device reported no SMART status"
    return (DRIVE_PASS if status["passed"] else DRIVE_FAIL), None


def evaluate(expected, drives):
    """The verdict, and the reason for it. Every branch that cannot see the truth is a failure."""
    counts = {DRIVE_PASS: 0, DRIVE_FAIL: 0, DRIVE_UNSUPPORTED: 0, DRIVE_UNAVAILABLE: 0}
    for d in drives:
        counts[d["verdict"]] = counts.get(d["verdict"], 0) + 1
    found = len(drives)

    if expected <= 0:
        return UNAVAILABLE, "no expected drive count was supplied, so nothing can be verified", counts
    if found == 0:
        return FAIL, "0 drive(s) discovered against %d expected" % expected, counts
    if found != expected:
        return FAIL, "%d drive(s) discovered against %d expected" % (found, expected), counts
    if counts[DRIVE_FAIL]:
        return FAIL, "%d of %d drive(s) report SMART failure" % (counts[DRIVE_FAIL], found), counts
    if counts[DRIVE_UNAVAILABLE] or counts[DRIVE_UNSUPPORTED]:
        return FAIL, ("%d of %d drive(s) could not produce a SMART verdict"
                      % (counts[DRIVE_UNAVAILABLE] + counts[DRIVE_UNSUPPORTED], found)), counts
    return PASS, "%d of %d expected drive(s) report SMART healthy" % (counts[DRIVE_PASS],
                                                                     expected), counts


def collect(expected, min_bytes, max_bytes, timeout):
    by_wwn, err = discover(min_bytes, max_bytes, timeout)
    if err:
        return {
            "schema": SCHEMA, "source": "smartctl", "status": UNAVAILABLE,
            "detail": "drive enumeration failed: %s" % err,
            "expected": expected, "found": 0,
            "counts": {DRIVE_PASS: 0, DRIVE_FAIL: 0, DRIVE_UNSUPPORTED: 0, DRIVE_UNAVAILABLE: 0},
            "drives": [],
        }
    drives = []
    for wwn in sorted(by_wwn):
        device = by_wwn[wwn]
        verdict, note = smart_status(device, timeout)
        row = {"wwn": wwn, "device": device, "verdict": verdict}
        if note:
            row["note"] = note
        drives.append(row)
    status, detail, counts = evaluate(expected, drives)
    return {
        "schema": SCHEMA, "source": "smartctl", "status": status, "detail": detail,
        "expected": expected, "found": len(drives), "counts": counts,
        # No serial numbers: the verdict never needs them and an evidence file should not carry
        # identifiers it does not use.
        "drives": drives,
        "failed": [d["wwn"] for d in drives if d["verdict"] != DRIVE_PASS],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="SMART drive health for backup verification")
    ap.add_argument("--expected", type=int, required=True,
                    help="authoritative expected physical-disk count")
    ap.add_argument("--min-bytes", type=int, default=DEFAULT_MIN_BYTES)
    ap.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    a = ap.parse_args(argv)
    print(json.dumps(collect(a.expected, a.min_bytes, a.max_bytes, a.timeout), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
