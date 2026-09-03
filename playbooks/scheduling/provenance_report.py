#!/usr/bin/env python3
"""Map the NetFRAME managed-runtime provenance verifier's result into the daily drift report.

WHAT THIS IS NOT. This does not verify anything. It does not hash a file, check a signature, read a
manifest or decide whether a runtime is intact. NetFRAME owns that: it holds the trust root, the
signed manifests and the declared intended versions, and it answers the question. Home-Lab owns
scheduling and reporting, so this file does exactly one thing - turn "what the verifier said" into
"what the daily report carries" - and would be a bug the moment it started forming its own opinion
about an artifact.

THE ASYMMETRY, which is the only interesting decision here. Success must be evidenced; failure is
believed. A verifier that exits 0 but whose output cannot be parsed, or whose output disagrees with
its own exit status, is reported UNKNOWN: nothing was established, so nothing may be claimed. A
verifier that exits 3 (drift) but whose output cannot be parsed is still reported DRIFT, because the
exit status is itself a positive finding and downgrading it to "could not verify" would hide a
confirmed defect. Both surface to the operator; they are not the same event and are not merged.
"""
from __future__ import annotations

import json
import sys

INTACT, DRIFT, UNKNOWN = "intact", "drift", "unknown"

# The verifier's published contract. Mirrored, not re-derived: see ./netframe provenance managed.
RC_INTACT, RC_USAGE, RC_DRIFT, RC_UNKNOWN = 0, 2, 3, 4
RC_TIMEOUT = 124  # GNU timeout(1) kills the child
RC_ABSENT = 127   # the scheduler found no verifier to run at all

EXPECTED_STATE = "CURRENT_AND_INTACT"
REPORT_SCHEMA = "netframe.provenance-drift-report/1"

_FIELDS = ("runtime", "composite_state", "classes", "intended_sha", "deployed_sha",
           "signature_status", "artifact_integrity", "version_status", "active_target_status")


def _runtimes(payload):
    """The per-runtime rows an operator needs, and nothing else. No paths to keys, no secrets."""
    rows = []
    for r in payload.get("runtimes") or []:
        if not isinstance(r, dict):
            continue
        row = {k: r.get(k) for k in _FIELDS}
        row["classes"] = list(row["classes"] or [])
        rows.append(row)
    return rows


def build(stdout: str, rc: int, expected_runtimes=None) -> dict:
    """(verifier stdout, verifier exit code) -> the report object the daily JSON carries."""
    out = {"schema": REPORT_SCHEMA, "status": UNKNOWN, "exit_code": rc,
           "runtimes": [], "reason": ""}

    try:
        payload = json.loads(stdout)
        if not isinstance(payload, dict):
            raise ValueError("not an object")
    except (ValueError, TypeError):
        payload = None

    if payload is None:
        if rc == RC_DRIFT:
            # Believed, not downgraded. The verifier positively determined drift; we simply cannot
            # name the classes, and saying "could not verify" here would erase a real finding.
            out["status"] = DRIFT
            out["reason"] = "verifier reported drift but its output could not be parsed"
        elif rc == RC_TIMEOUT:
            out["reason"] = "verifier timed out"
        elif rc == RC_ABSENT:
            out["reason"] = "no NetFRAME provenance verifier available to run"
        elif rc == RC_USAGE:
            # The specific, expected shape of a stale deployment: a checkout published before this
            # check existed does not recognise the verb, so it refuses rather than guessing.
            out["reason"] = ("verifier rejected its invocation (exit 2): the deployed checkout "
                             "may predate this check")
        elif not stdout.strip():
            out["reason"] = "verifier produced no output (exit %s)" % rc
        else:
            out["reason"] = "malformed verifier output (exit %s)" % rc
        return out

    out["runtimes"] = _runtimes(payload)
    states = [r.get("composite_state") for r in out["runtimes"]]
    classes = sorted({c for r in out["runtimes"] for c in r["classes"]})
    if classes:
        out["classes"] = classes

    if rc == RC_INTACT:
        # Cross-check the exit code against the body. A verifier whose two channels disagree has
        # not established success, whichever one happens to be right.
        if not states:
            out["reason"] = "verifier exited intact but reported no runtimes"
        elif expected_runtimes is not None and len(states) != expected_runtimes:
            out["reason"] = ("verifier exited intact but reported %d of %d declared runtimes"
                             % (len(states), expected_runtimes))
        elif any(s != EXPECTED_STATE for s in states) or classes:
            out["reason"] = "verifier exited intact but its report contradicts that"
        else:
            out["status"] = INTACT
        return out

    if rc == RC_DRIFT:
        out["status"] = DRIFT
        out["reason"] = ("provenance drift: %s" % ", ".join(classes)) if classes else "provenance drift"
        return out

    if rc == RC_TIMEOUT:
        out["reason"] = "verifier timed out"
    elif rc == RC_ABSENT:
        out["reason"] = "no NetFRAME provenance verifier available to run"
    elif rc == RC_UNKNOWN:
        out["reason"] = "verifier could not establish provenance"
    elif rc == RC_USAGE:
        out["reason"] = "verifier rejected its invocation (exit 2)"
    else:
        out["reason"] = "verifier failed (exit %s)" % rc
    return out


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    fixture = "--fixture" in argv
    argv = [a for a in argv if a != "--fixture"]
    if not argv:
        sys.stderr.write("usage: provenance_report.py <verifier-exit-code> [expected-runtimes]\n")
        return 2
    try:
        rc = int(argv[0])
        expected = int(argv[1]) if len(argv) > 1 and argv[1] else None
    except ValueError:
        sys.stderr.write("exit code and expected count must be integers\n")
        return 2
    report = build(sys.stdin.read(), rc, expected)
    if fixture:
        # A fixture-produced report must never be mistakable for a measurement of the estate.
        report["fixture"] = True
        report["reason"] = ("FIXTURE MODE (no host was contacted): " + report["reason"]).strip()
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
