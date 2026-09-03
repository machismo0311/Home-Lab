#!/usr/bin/env python3
"""Tests for the Ares restore-verify drill.

Hermetic: every case runs the real script against a STUB restic placed first on PATH. No repository
is contacted, no snapshot is read, no backup is touched, and nothing here can corrupt a real
backup to prove a negative.

The point of most of these is not that the drill fails, but that it fails DISTINGUISHABLY. The
2026-09-01 outage was a stale lock reported as "restic check (repo integrity)", which reads as
corruption; a month later nobody had looked, because the message discouraged looking. So the cases
that matter most are the pair that the old script collapsed into one: a lock in the way, and data
that genuinely does not verify.

Runs without pytest, like the other scheduling tests.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCHED = os.path.abspath(os.path.join(HERE, ".."))
SCRIPT = os.path.join(SCHED, "ares-restore-verify.sh")

FAILURES = []


def chk(label, cond, detail=""):
    if cond:
        print("  PASS  %s" % label)
    else:
        print("  FAIL  %s%s" % (label, ("  [%s]" % detail) if detail else ""))
        FAILURES.append(label)


STUB = r'''#!/usr/bin/env bash
# Stub restic. Behaviour is chosen by environment DATA, never by executing injected code.
echo "$@" >> "$STUB_CALLS"
case "$1" in
  check)
    n=0; [[ -f "$STUB_STATE" ]] && n="$(cat "$STUB_STATE")"
    n=$((n+1)); echo "$n" > "$STUB_STATE"
    if [[ "${STUB_CHECK_SLEEP:-0}" != "0" ]]; then sleep "$STUB_CHECK_SLEEP"; fi
    if [[ "$n" == "1" && -n "${STUB_CHECK1_ERR:-}" ]]; then echo "$STUB_CHECK1_ERR" >&2; exit 1; fi
    if [[ -n "${STUB_CHECK_ERR:-}" ]]; then echo "$STUB_CHECK_ERR" >&2; exit 1; fi
    echo "no errors were found"; exit 0 ;;
  unlock)
    [[ "${STUB_UNLOCK_FAIL:-0}" == "1" ]] && exit 1
    echo "successfully removed 1 locks"; exit 0 ;;
  snapshots)
    if [[ -n "${STUB_SNAPSHOTS:-}" ]]; then printf '%s' "$STUB_SNAPSHOTS"
    else printf '%s' '[{"short_id":"aa11bb22","id":"aa11bb22cc"}]'; fi
    exit 0 ;;
  restore)
    [[ "${STUB_RESTORE_FAIL:-0}" == "1" ]] && exit 1
    target=""; prev=""
    for a in "$@"; do [[ "$prev" == "--target" ]] && target="$a"; prev="$a"; done
    mkdir -p "$target$(dirname "$STUB_PROBE")"
    if [[ "${STUB_RESTORE_EMPTY:-0}" == "1" ]]; then : > "$target$STUB_PROBE";
    else printf 'restored-content\n' > "$target$STUB_PROBE"; fi
    if [[ "${STUB_BLOCK_CLEANUP:-0}" == "1" ]]; then
      mkdir -p "$target/stuck"; printf 'x' > "$target/stuck/file"; chmod 500 "$target/stuck"; fi
    exit 0 ;;
esac
exit 0
'''


def run(**env):
    """Run the drill with a stubbed restic. Returns (rc, evidence dict or None, log text, calls)."""
    td = tempfile.mkdtemp(prefix="arv-test.")
    bindir = os.path.join(td, "bin")
    os.makedirs(bindir)
    stub = os.path.join(bindir, "restic")
    with open(stub, "w") as fh:
        fh.write(STUB)
    os.chmod(stub, 0o755)
    probe = "/probe/.bashrc"
    passfile = os.path.join(td, "pass")
    with open(passfile, "w") as fh:
        fh.write("x\n")
    log = os.path.join(td, "drill.log")
    ev = os.path.join(td, "drill.json")
    tmpd = os.path.join(td, "tmp")
    os.makedirs(tmpd)
    e = dict(os.environ)
    e.update({
        "PATH": bindir + ":" + os.environ["PATH"],
        "RESTIC_PASSWORD_FILE": passfile,
        "RESTIC_REPOSITORY": "sftp:stub:/nowhere",
        "ARES_RESTORE_VERIFY_LOG": log,
        "ARES_RESTORE_VERIFY_EVIDENCE": ev,
        "ARES_RESTORE_VERIFY_PROBE": probe,
        "TMPDIR": tmpd,
        "STUB_CALLS": os.path.join(td, "calls"),
        "STUB_STATE": os.path.join(td, "state"),
        "STUB_PROBE": probe,
    })
    if env.pop("_no_restic", False):
        # A PATH that genuinely has no restic on it. Ares carries TWO restic binaries
        # (~/.local/bin and /usr/bin), so simply trimming PATH to the system directories finds the
        # real one and tests nothing. Build a minimal bin directory instead, holding only the few
        # tools the drill needs before its dependency check.
        minbin = os.path.join(td, "minbin")
        os.makedirs(minbin, exist_ok=True)
        for tool in ("mkdir", "dirname", "mktemp", "date", "python3", "rm", "cat"):
            src = shutil.which(tool)
            if src:
                os.symlink(src, os.path.join(minbin, tool))
        e["PATH"] = minbin
    e.update({k: str(v) for k, v in env.items()})
    p = subprocess.run(["/bin/bash", SCRIPT], capture_output=True, text=True, env=e, timeout=180)
    data = None
    if os.path.exists(ev):
        try:
            data = json.load(open(ev))
        except ValueError:
            data = "MALFORMED_EVIDENCE"
    calls = open(e["STUB_CALLS"]).read() if os.path.exists(e["STUB_CALLS"]) else ""
    logtxt = open(log).read() if os.path.exists(log) else ""
    for root, dirs, _ in os.walk(td):
        for d in dirs:
            os.chmod(os.path.join(root, d), 0o755)
    shutil.rmtree(td, ignore_errors=True)
    return p.returncode, data, logtxt, calls


print("== the happy path ==")
rc, ev, log, calls = run()
chk("a healthy repository passes", rc == 0 and ev and ev["status"] == "pass", "rc=%s" % rc)
chk("it reaches LEVEL 2 RESTORE_EXTRACTED and says so",
    ev and ev["level"] == 2 and ev["level_name"] == "RESTORE_EXTRACTED")
chk("the evidence names the snapshot it restored", ev and ev["snapshot"] == "aa11bb22")
chk("the evidence records restored size and digest",
    ev and ev["restored_bytes"] > 0 and len(ev["restored_sha256"]) == 64)
chk("it restores the resolved snapshot id, not 'latest'",
    "restore aa11bb22" in calls and "restore latest" not in calls, calls.replace("\n", " | "))
chk("the log records the level, not just OK", "LEVEL 2 RESTORE_EXTRACTED" in log)

print()
print("== the 2026-09-01 failure, and the distinction it destroyed ==")
rc, ev, log, calls = run(STUB_CHECK1_ERR="unable to create lock in backend: repository is already"
                                         " locked by PID 3814969 on ares by machismo")
chk("a stale lock is now recovered rather than fatal", rc == 0 and ev and ev["status"] == "pass")
chk("recovery ran unlock exactly once", calls.count("unlock") == 1, calls.replace("\n", " | "))
chk("the recovery is recorded in the evidence, not hidden",
    ev and ev["stale_lock_recovered"] is True)

rc, ev, log, calls = run(STUB_CHECK1_ERR="repository is already locked", STUB_UNLOCK_FAIL=1)
chk("a lock that cannot be cleared fails as REPOSITORY_LOCKED",
    rc != 0 and ev and ev["failure_class"] == "REPOSITORY_LOCKED", ev and ev["failure_class"])
chk("a lock is NEVER reported as an integrity problem",
    ev and ev["failure_class"] != "INTEGRITY_FAILED")

rc, ev, log, calls = run(STUB_CHECK_ERR="Pack ID does not match, want 1a2b, got 9f8e")
chk("genuine integrity failure is INTEGRITY_FAILED",
    rc != 0 and ev and ev["failure_class"] == "INTEGRITY_FAILED", ev and ev["failure_class"])
chk("the captured restic error is preserved in the evidence",
    ev and "Pack ID does not match" in ev["detail"], ev and ev["detail"])
chk("integrity failure and lock failure are different classes",
    ev["failure_class"] != "REPOSITORY_LOCKED")

print()
print("== no false PASS (section 17) ==")
cases = [
    ("backup absent", {"STUB_SNAPSHOTS": "[]"}, "BACKUP_UNAVAILABLE"),
    ("verification command failure", {"STUB_CHECK_ERR": "fatal: repository not found"},
     "INTEGRITY_FAILED"),
    ("restore extraction failure", {"STUB_RESTORE_FAIL": 1}, "RESTORE_FAILED"),
    ("restored file empty", {"STUB_RESTORE_EMPTY": 1}, "RESTORE_FAILED"),
    ("malformed verifier output", {"STUB_SNAPSHOTS": "{not json"}, "MALFORMED_OUTPUT"),
    ("snapshot record without an id", {"STUB_SNAPSHOTS": '[{"time":"x"}]'}, "MALFORMED_OUTPUT"),
    ("timeout", {"STUB_CHECK_SLEEP": 3, "ARES_RESTORE_VERIFY_CHECK_TIMEOUT": 1}, "TIMEOUT"),
    ("cleanup failure", {"STUB_BLOCK_CLEANUP": 1}, "CLEANUP_FAILED"),
    ("restic missing", {"_no_restic": True}, "MISSING_DEPENDENCY"),
]
for label, env, want in cases:
    rc, ev, log, calls = run(**env)
    chk("%s -> exit non-zero" % label, rc != 0, "rc=%s" % rc)
    chk("%s -> classified %s" % (label, want),
        isinstance(ev, dict) and ev["failure_class"] == want,
        ev.get("failure_class") if isinstance(ev, dict) else str(ev))
    chk("%s -> never reports status pass" % label,
        isinstance(ev, dict) and ev["status"] != "pass")
    chk("%s -> evidence is still valid JSON" % label, isinstance(ev, dict))
    if want != "CLEANUP_FAILED":
        # Cleanup failure is the one case where LEVEL 2 is still truthful: the extraction really did
        # happen, and only the removal of the temporary directory failed. Zeroing the level there
        # would erase a fact that was actually established. `status` is what says the drill failed.
        chk("%s -> never claims LEVEL 2" % label,
            isinstance(ev, dict) and ev["level"] < 2, ev.get("level") if isinstance(ev, dict) else "")

chk("a failed drill NEVER reports status pass at any level",
    all(run(**e)[1]["status"] != "pass" for _, e, _ in cases if "_no_restic" not in e))

print()
print("== it stays non-destructive ==")
src = open(SCRIPT).read()
body = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
for forbidden in ("restic forget", "restic prune", "--remove-all", "systemctl", "pct ", "qm ",
                  "mkfs", "dd if="):
    chk("the drill never runs %r" % forbidden, forbidden not in body)
chk("it only ever restores into a mktemp directory",
    "--target \"${dest}\"" in body and 'dest="$(mktemp -d' in body)
# Look only at EXECUTION, not at prose. Quoted spans are stripped first, so a failure message that
# mentions "restic check" cannot be mistaken for an unbounded invocation of it.
import re  # noqa: E402
_unbounded = []
for line in body.splitlines():
    bare = re.sub(r'"[^"]*"', " ", re.sub(r"'[^']*'", " ", line))
    if re.search(r"\brestic (check|unlock|snapshots|restore)\b", bare) and "timeout" not in bare:
        _unbounded.append(line.strip())
chk("every restic invocation is bounded by timeout(1)", not _unbounded, "; ".join(_unbounded))
chk("stderr from check is captured, not discarded",
    'check_err="$(timeout "${t_check}" restic check 2>&1 >/dev/null)"' in body)

print()
if FAILURES:
    print("FAILED: %d" % len(FAILURES))
    for f in FAILURES:
        print("  - %s" % f)
    sys.exit(1)
print("ALL PASS")
