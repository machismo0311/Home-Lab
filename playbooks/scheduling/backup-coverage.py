#!/usr/bin/env python3
"""Does every guest still have exactly one backup job?

WHY THIS EXISTS. Splitting VM 202 out of the shared RKE2 job is two edits - remove it from one job,
add it to another - and the failure modes are silent in both directions. Remove it and forget to add
it and a guest stops being backed up while every job still reports success. Add it and forget to
remove it and the guest is backed up twice, competing with itself for the node's global vzdump lock,
which is the exact contention this split was meant to end. Neither shows up in a task log.

So the invariant is checked directly against the canonical job definitions: every expected guest
appears in exactly one enabled job, and nothing else moved.

This reads job definitions. It never writes one.
"""
from __future__ import annotations

import argparse
import json
import sys

SCHEMA = "netframe-backup-coverage/v1"

OK = "ok"
MISSING = "missing"
DUPLICATED = "duplicated"
UNEXPECTED = "unexpected"


def parse_jobs(doc):
    """Normalise `pvesh get /cluster/backup` output into {vmid: [(job_id, schedule, enabled)]}."""
    cover = {}
    for job in doc or []:
        if job.get("type") not in (None, "vzdump"):
            continue
        enabled = int(job.get("enabled", 1) or 0)
        vmids = str(job.get("vmid") or "")
        for raw in vmids.split(","):
            vmid = raw.strip()
            if not vmid:
                continue
            cover.setdefault(vmid, []).append({
                "job": job.get("id"),
                "schedule": job.get("schedule"),
                "enabled": enabled,
            })
    return cover


def evaluate(cover, expected):
    """Coverage verdict against the expected guest list. Absence is never silence."""
    findings = []
    expected = [str(v) for v in expected]
    for vmid in expected:
        entries = [e for e in cover.get(vmid, []) if e["enabled"]]
        if not entries:
            findings.append({"vmid": vmid, "issue": MISSING,
                             "detail": "no enabled backup job covers this guest"})
        elif len(entries) > 1:
            findings.append({"vmid": vmid, "issue": DUPLICATED,
                             "detail": "covered by %d enabled jobs: %s"
                                       % (len(entries), ", ".join(sorted(
                                           "%s@%s" % (e["job"], e["schedule"]) for e in entries)))})
    for vmid in sorted(cover):
        if vmid not in expected and any(e["enabled"] for e in cover[vmid]):
            findings.append({"vmid": vmid, "issue": UNEXPECTED,
                             "detail": "covered by a job but not in the expected guest list"})
    return findings


def schedule_of(cover, vmid):
    entries = [e for e in cover.get(str(vmid), []) if e["enabled"]]
    return entries[0]["schedule"] if len(entries) == 1 else None


def check_contention(cover, pairs):
    """Guests that must not share a schedule, because they share a node's global vzdump lock."""
    clashes = []
    for a, b in pairs:
        sa, sb = schedule_of(cover, a), schedule_of(cover, b)
        if sa is not None and sa == sb:
            clashes.append({"vmids": [str(a), str(b)], "schedule": sa,
                            "detail": "both guests are scheduled at the same time on one node"})
    return clashes


def report(doc, expected, contention_pairs=()):
    cover = parse_jobs(doc)
    findings = evaluate(cover, expected)
    clashes = check_contention(cover, contention_pairs)
    return {
        "schema": SCHEMA,
        "status": OK if not findings and not clashes else "fail",
        "expected_guests": len(expected),
        "covered_guests": len([v for v in cover if any(e["enabled"] for e in cover[v])]),
        "findings": findings,
        "schedule_clashes": clashes,
        "coverage": {v: sorted(cover[v], key=lambda e: str(e["job"])) for v in sorted(cover)},
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Backup job coverage invariants")
    ap.add_argument("--jobs", required=True,
                    help="file holding `pvesh get /cluster/backup --output-format json` output, "
                         "or - for stdin")
    ap.add_argument("--expected", required=True,
                    help="comma-separated vmids that must each be covered exactly once")
    ap.add_argument("--no-share-schedule", default="",
                    help="comma-separated a:b vmid pairs that must not share a schedule")
    a = ap.parse_args(argv)
    raw = sys.stdin.read() if a.jobs == "-" else open(a.jobs, encoding="utf-8").read()
    try:
        doc = json.loads(raw)
    except ValueError as exc:
        print(json.dumps({"schema": SCHEMA, "status": "fail",
                          "findings": [{"issue": "unreadable",
                                        "detail": "job definitions did not parse: %s" % exc}]},
                         sort_keys=True))
        return 2
    pairs = [tuple(p.split(":", 1)) for p in a.no_share_schedule.split(",") if ":" in p]
    out = report(doc, [v.strip() for v in a.expected.split(",") if v.strip()], pairs)
    print(json.dumps(out, sort_keys=True, indent=2))
    return 0 if out["status"] == OK else 1


if __name__ == "__main__":
    sys.exit(main())
