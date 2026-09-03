"""Tests for publishing the Ares restore-verify evidence to Randy.

Hermetic: the ansible transport is replaced by a stub that copies into a local directory standing
in for Randy. No host is contacted. The stub performs a REAL copy so the delivery digest check is
exercised end to end rather than mocked away.

The property under test is not "the copy command exited 0". It is that what arrives is the complete,
unaltered evidence, and that anything less is reported as a publication failure rather than quietly
accepted.
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
PUBLISH = os.path.join(SCHED, "publish-restore-evidence.sh")
DRILL = os.path.join(SCHED, "ares-restore-verify.sh")

FAILURES = []


def chk(label, cond, detail=""):
    if cond:
        print("  PASS  %s" % label)
    else:
        print("  FAIL  %s%s" % (label, ("  [%s]" % detail) if detail else ""))
        FAILURES.append(label)


STUB_ANSIBLE = r'''#!/usr/bin/env bash
echo "$@" >> "$STUB_ANSIBLE_CALLS"
src=""; dest=""; sha_path=""
for a in "$@"; do
  case "$a" in
    *"ansible.builtin.copy"*) op=copy ;;
    *"ansible.builtin.command"*) op=cmd ;;
  esac
  case "$a" in
    *src=*dest=*)
      src="$(sed -n 's/.*src=\([^ ]*\).*/\1/p' <<<"$a")"
      dest="$(sed -n 's/.*dest=\([^ ]*\).*/\1/p' <<<"$a")" ;;
    "sha256sum "*) sha_path="${a#sha256sum }" ;;
  esac
done
if [[ "${op:-}" == "copy" ]]; then
  [[ "${STUB_COPY_FAIL:-0}" == "1" ]] && exit 1
  mkdir -p "$(dirname "$STUB_REMOTE_ROOT$dest")"
  if [[ "${STUB_PARTIAL:-0}" == "1" ]]; then
    head -c 20 "$src" > "$STUB_REMOTE_ROOT$dest"
  else
    cp "$src" "$STUB_REMOTE_ROOT$dest"
  fi
  exit 0
fi
if [[ "${op:-}" == "cmd" ]]; then
  [[ "${STUB_READBACK_FAIL:-0}" == "1" ]] && exit 1
  if [[ -n "${STUB_READBACK_SHA:-}" ]]; then echo "randy | CHANGED | rc=0 >>"; echo "$STUB_READBACK_SHA  $sha_path"; exit 0; fi
  [[ -f "$STUB_REMOTE_ROOT$sha_path" ]] || exit 1
  echo "randy | CHANGED | rc=0 >>"
  sha256sum "$STUB_REMOTE_ROOT$sha_path"
  exit 0
fi
exit 0
'''

EVIDENCE_PASS = {
    "schema": "netframe.ares-restore-verify/1", "status": "pass", "failure_class": "",
    "detail": "", "level": 2, "level_name": "RESTORE_EXTRACTED", "snapshot": "33102858",
    "stale_lock_recovered": False, "probe_path": "/home/machismo/.bashrc",
    "restored_bytes": 3797, "restored_sha256": "a" * 64, "matches_live_probe": "identical",
    "generated": "2026-09-02T22:03:22-04:00", "generated_epoch": 1788401002,
    "repository": "sftp:randy:/mnt/bulk/backups/ares",
}
EVIDENCE_FAIL = dict(EVIDENCE_PASS, status="fail", failure_class="REPOSITORY_LOCKED",
                     level=0, level_name="NOTHING_PROVEN", snapshot="",
                     detail="repository is locked and stale locks could not be removed")


def run_publish(evidence=EVIDENCE_PASS, raw=None, write_evidence=True, **env):
    td = tempfile.mkdtemp(prefix="pub-test.")
    bindir = os.path.join(td, "bin")
    os.makedirs(bindir)
    stub = os.path.join(bindir, "ansible")
    with open(stub, "w") as fh:
        fh.write(STUB_ANSIBLE)
    os.chmod(stub, 0o755)
    ev = os.path.join(td, "evidence.json")
    if write_evidence:
        with open(ev, "w") as fh:
            fh.write(raw if raw is not None else json.dumps(evidence, sort_keys=True) + "\n")
    log = os.path.join(td, "drill.log")
    remote = os.path.join(td, "remote")
    os.makedirs(remote)
    e = dict(os.environ)
    e.update({
        "ARES_RESTORE_VERIFY_EVIDENCE": ev,
        "ARES_RESTORE_VERIFY_LOG": log,
        "ARES_PUBLISH_ANSIBLE": stub,
        "ARES_RESTORE_PUBLISH_DEST": "/var/log/netframe-monitor/restore-verify.json",
        "ARES_RESTORE_PUBLISH_TARGET": "randy",
        "ANSIBLE_VAULT_PASSWORD_FILE": os.path.join(td, "no-such-vault"),
        "STUB_ANSIBLE_CALLS": os.path.join(td, "calls"),
        "STUB_REMOTE_ROOT": remote,
    })
    e.update({k: str(v) for k, v in env.items()})
    p = subprocess.run(["/bin/bash", PUBLISH], capture_output=True, text=True, env=e, timeout=120)
    landed = os.path.join(remote, "var/log/netframe-monitor/restore-verify.json")
    delivered = open(landed).read() if os.path.exists(landed) else None
    src_after = open(ev).read() if os.path.exists(ev) else None
    logtxt = open(log).read() if os.path.exists(log) else ""
    calls = open(e["STUB_ANSIBLE_CALLS"]).read() if os.path.exists(e["STUB_ANSIBLE_CALLS"]) else ""
    shutil.rmtree(td, ignore_errors=True)
    return p.returncode, delivered, src_after, logtxt, calls


print("== a PASS result publishes verbatim ==")
rc, delivered, src, log, calls = run_publish()
chk("publication succeeds", rc == 0, "rc=%s stdout" % rc)
chk("the destination holds the complete document", delivered is not None
    and json.loads(delivered)["snapshot"] == "33102858")
chk("the evidence is copied verbatim, not rewritten",
    delivered == json.dumps(EVIDENCE_PASS, sort_keys=True) + "\n")
chk("the source evidence is unchanged by publication",
    src == json.dumps(EVIDENCE_PASS, sort_keys=True) + "\n")
chk("delivery is confirmed by reading the destination back", "sha256sum" in calls)
chk("the transport used is an atomic copy, not a shell redirect",
    "ansible.builtin.copy" in calls and ">" not in calls.split("\n")[0])

print()
print("== a FAIL result is published too, so it surfaces as FAIL and not as staleness ==")
rc, delivered, src, log, calls = run_publish(EVIDENCE_FAIL)
chk("a failed drill still publishes", rc == 0)
chk("the failure class survives transport",
    delivered and json.loads(delivered)["failure_class"] == "REPOSITORY_LOCKED")
chk("a failed drill does not publish a passing status",
    delivered and json.loads(delivered)["status"] == "fail")

print()
print("== publication failures are reported, never assumed ==")
rc, delivered, src, log, calls = run_publish(STUB_COPY_FAIL=1)
chk("transport failure exits non-zero", rc != 0)
chk("transport failure is logged as a publication failure", "PUBLISH: FAILED" in log)
chk("nothing is left at the destination", delivered is None)

rc, delivered, src, log, calls = run_publish(STUB_READBACK_FAIL=1)
chk("an unverifiable delivery is a failure", rc != 0 and "could not read back" in log)

rc, delivered, src, log, calls = run_publish(STUB_READBACK_SHA="b" * 64)
chk("a delivered copy that does not match the source is a failure",
    rc != 0 and "does not match" in log)

rc, delivered, src, log, calls = run_publish(STUB_PARTIAL=1)
chk("a truncated delivery is detected and reported, never accepted", rc != 0)
chk("a partial document is never treated as published", "does not match" in log)

print()
print("== it refuses to publish what it should not ==")
rc, delivered, src, log, calls = run_publish(raw="{not json at all")
chk("malformed local evidence is not published", rc != 0 and delivered is None)
chk("refusal says why", "not valid JSON" in log)
rc, delivered, src, log, calls = run_publish(write_evidence=False)
chk("missing local evidence is not published", rc != 0 and delivered is None)
chk("no transport is even attempted when there is nothing valid to send", calls == "")

print()
print("== no secrets, and the two verdicts stay separate ==")
rc, delivered, src, log, calls = run_publish()
blob = (delivered or "") + log + calls
for secret in ("ares-randy.pass", "RESTIC_PASSWORD", "vault-pass", "BEGIN OPENSSH"):
    chk("published material carries no %r" % secret, secret not in blob)

pub_src = open(PUBLISH).read()
drill_src = open(DRILL).read()
chk("the drill treats publication as non-fatal to the restore verdict",
    "publish_evidence" in drill_src and "restore verdict unaffected" in drill_src)
chk("a failed publication cannot change the drill's exit code",
    "|| echo" in drill_src and "return 0" in drill_src)
chk("publication never touches the restic repository",
    all(t not in pub_src for t in ("restic ", "unlock", "forget", "prune")))
chk("the drill publishes on failure as well as success",
    drill_src.count("publish_evidence") >= 4, drill_src.count("publish_evidence"))
chk("the shipping unit does not disable publication",
    "ARES_RESTORE_VERIFY_PUBLISH" not in
    open(os.path.join(SCHED, "systemd", "ares-restore-verify.service")).read())

print()
if FAILURES:
    print("FAILED: %d" % len(FAILURES))
    for f in FAILURES:
        print("  - %s" % f)
    sys.exit(1)
print("ALL PASS")
