#!/usr/bin/env python3
"""Per-group freshness for HOST-type PBS backups.

WHY THIS EXISTS. Backup freshness was evaluated at exactly two granularities, and a host-type
backup group falls through both of them. The per-datastore check asks only for the newest snapshot
anywhere in the datastore, so seventeen healthy groups keep it green. The per-guest check matches
`backup-id` against a list of numeric VMIDs, and a host backup's id is a hostname, so it is never
selected and never missed. Between 2026-07-02 and 2026-09-13 the group host/quarkylab held one
snapshot and grew 73 days stale. For the 770 hours Prometheus still retains (from 2026-08-12), the
report was green for 578 of them; the red hours were other checks, because no check could see a host
group at all. That is worse than no check: a green light is the reason nobody looked.

WHAT IT CHECKS. Each expected host group is evaluated ON ITS OWN. The age of a group is the age of
its own newest snapshot, so a fresh snapshot belonging to any other group - the datastore's newest,
a sibling host group, any guest - cannot contribute to it. That is the whole point, and the
regression test for it is the one that matters.

ABSENCE IS NOT FRESHNESS, AND NEITHER IS SILENCE. Four outcomes are kept distinct because they call
for different actions: FRESH (a snapshot inside the window), STALE (the producer stopped), MISSING
(the group was never created, or was removed), and UNKNOWN (we could not ask PBS at all). A source
that will not answer is never reported as a stale backup - that would blame the producer for the
monitor's own blindness, and it is the mirror image of the false green this check was built to end.
Both STALE and MISSING fail. UNKNOWN is `unavailable`, which the role records as an error, which
still fails the report - "we could not tell" never becomes "pass".

THE DENOMINATOR IS DECLARED, NOT DISCOVERED. Expected groups are supplied by the caller. A check
that enumerated whatever groups happen to exist could never report one that vanished, which is
exactly the MISSING case.

This reads snapshot metadata. It never writes a snapshot, prunes one, or touches a datastore.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time

SCHEMA = "netframe-pbs-host-freshness/v1"

PASS = "pass"
FAIL = "fail"
UNAVAILABLE = "unavailable"

FRESH = "fresh"
STALE = "stale"
MISSING = "missing"
UNKNOWN = "unknown"

# The host-type namespace. A guest snapshot is `vm`/`ct`; only `host` groups are this check's
# business, and filtering on it is what stops a VMID that happens to equal a hostname from matching.
HOST_TYPE = "host"

# PBS's own local CLI. Root on the storage host, no API token, no secret on the command line - the
# same reasoning that moved drive health from a remote API to smartctl on the host that owns the
# disks. A token that silently expires would turn this check into the stale-evidence failure the
# Scrutiny reader taught us to avoid.
DEBUG_BIN = "proxmox-backup-debug"

DEFAULT_TIMEOUT = 30
DEFAULT_MAX_AGE_HOURS = 25


def _run(cmd, timeout):
    """One bounded local command. Never a shell, so nothing here can execute composed input."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired:
        return None, "timeout"
    except (OSError, ValueError) as exc:
        return None, type(exc).__name__
    return p, None


def _api(path, timeout):
    """A read-only GET against the local PBS API, decoded. Returns (doc, error)."""
    if not shutil.which(DEBUG_BIN):
        return None, "%s is not available" % DEBUG_BIN
    p, err = _run([DEBUG_BIN, "api", "get", path, "--output-format", "json"], timeout)
    if err:
        return None, "%s %s" % (DEBUG_BIN, err)
    if p.returncode != 0:
        return None, "%s exited %d" % (DEBUG_BIN, p.returncode)
    try:
        doc = json.loads(p.stdout)
    except (ValueError, TypeError):
        return None, "%s output did not parse as JSON" % DEBUG_BIN
    if not isinstance(doc, list):
        return None, "%s output was not a list" % DEBUG_BIN
    return doc, None


def datastores(timeout, declared):
    """The datastores to search: the caller's list, or every one PBS reports."""
    if declared:
        return declared, None
    doc, err = _api("/admin/datastore", timeout)
    if err:
        return None, err
    names = [d.get("store") for d in doc if isinstance(d, dict) and d.get("store")]
    if not names:
        return None, "PBS reported no datastores"
    return names, None


def host_snapshots(timeout, declared):
    """Every host-type snapshot across the datastores, as (backup_id, backup_time) pairs.

    A datastore that will not answer aborts the whole collection. Searching the ones that did reply
    would silently shrink the search space, and a group living only on the unreachable datastore
    would then be reported MISSING - a monitor failure dressed up as a backup failure.
    """
    stores, err = datastores(timeout, declared)
    if err:
        return None, err
    found = []
    for store in stores:
        doc, err = _api("/admin/datastore/%s/snapshots" % store, timeout)
        if err:
            return None, "datastore %s: %s" % (store, err)
        for snap in doc:
            if not isinstance(snap, dict) or snap.get("backup-type") != HOST_TYPE:
                continue
            bid, btime = snap.get("backup-id"), snap.get("backup-time")
            if not bid or not isinstance(btime, (int, float)) or isinstance(btime, bool):
                continue
            found.append((str(bid), int(btime)))
    return found, None


def evaluate(expected, snapshots, now, max_age_hours):
    """Per-group verdicts. Every group is judged only against snapshots that are its own."""
    window = int(max_age_hours) * 3600
    groups = []
    for bid in expected:
        times = [t for (gid, t) in snapshots if gid == bid]
        if not times:
            groups.append({"group": "%s/%s" % (HOST_TYPE, bid), "backup_id": bid,
                           "present": False, "snapshots": 0, "newest_epoch": 0,
                           "age_hours": -1, "state": MISSING, "fresh": False})
            continue
        newest = max(times)
        age = now - newest
        # One comparison, used for both fields. Computed twice, `state` and `fresh` could disagree
        # at the boundary, and a consumer reading one would contradict a consumer reading the other.
        fresh = age <= window
        groups.append({"group": "%s/%s" % (HOST_TYPE, bid), "backup_id": bid,
                       "present": True, "snapshots": len(times), "newest_epoch": newest,
                       "age_hours": round(age / 3600.0, 1),
                       "state": (FRESH if fresh else STALE), "fresh": fresh})
    return groups


def _unknown(expected, max_age_hours, detail):
    """The shape returned when PBS could not be asked. Never STALE - we do not know that."""
    return {
        "schema": SCHEMA, "source": DEBUG_BIN, "source_available": False,
        "status": UNAVAILABLE, "detail": detail,
        "threshold_hours": int(max_age_hours),
        "expected": len(expected), "stale": 0, "missing": 0, "unknown": len(expected),
        "groups": [{"group": "%s/%s" % (HOST_TYPE, b), "backup_id": b, "present": None,
                    "snapshots": 0, "newest_epoch": 0, "age_hours": -1,
                    "state": UNKNOWN, "fresh": False} for b in expected],
    }


def collect(expected, now, max_age_hours, declared_datastores, timeout):
    if not expected:
        # Nothing declared is nothing verified, and that is a finding, not a pass.
        return {
            "schema": SCHEMA, "source": DEBUG_BIN, "source_available": None,
            "status": UNAVAILABLE,
            "detail": "no expected host backup group was supplied, so nothing can be verified",
            "threshold_hours": int(max_age_hours),
            "expected": 0, "stale": 0, "missing": 0, "unknown": 0, "groups": [],
        }
    snapshots, err = host_snapshots(timeout, declared_datastores)
    if err:
        return _unknown(expected, max_age_hours,
                        "PBS snapshot source unavailable, host group freshness UNKNOWN: %s" % err)
    groups = evaluate(expected, snapshots, now, max_age_hours)
    stale = [g for g in groups if g["state"] == STALE]
    missing = [g for g in groups if g["state"] == MISSING]
    bad = missing + stale
    if bad:
        detail = ("%d expected host group(s); %d missing/stale: %s (threshold %dh)"
                  % (len(groups), len(bad),
                     ", ".join("%s %s" % (g["group"], g["state"]) for g in bad),
                     int(max_age_hours)))
    else:
        detail = ("%d expected host group(s); 0 missing/stale (threshold %dh)"
                  % (len(groups), int(max_age_hours)))
    return {
        "schema": SCHEMA, "source": DEBUG_BIN, "source_available": True,
        "status": (PASS if not bad else FAIL), "detail": detail,
        "threshold_hours": int(max_age_hours),
        "expected": len(groups), "stale": len(stale), "missing": len(missing), "unknown": 0,
        "groups": groups,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="PBS host-type backup group freshness")
    ap.add_argument("--expected", default="",
                    help="comma-separated host backup ids that must each have a fresh snapshot")
    ap.add_argument("--max-age-hours", type=int, default=DEFAULT_MAX_AGE_HOURS)
    ap.add_argument("--now", type=int, default=None,
                    help="epoch to measure ages against; defaults to now")
    ap.add_argument("--datastore", default="",
                    help="comma-separated datastores to search; default is every one PBS reports")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    a = ap.parse_args(argv)
    expected = [v.strip() for v in a.expected.split(",") if v.strip()]
    stores = [v.strip() for v in a.datastore.split(",") if v.strip()]
    now = a.now if a.now is not None else int(time.time())
    print(json.dumps(collect(expected, now, a.max_age_hours, stores, a.timeout), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
