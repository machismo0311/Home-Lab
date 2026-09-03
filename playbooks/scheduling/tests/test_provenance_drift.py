#!/usr/bin/env python3
"""Tests for the scheduled managed-runtime provenance drift check.

Hermetic by construction: every case drives the wrapper with a RECORDED verifier result. No host is
contacted, no SSH is attempted, no live runtime is read, and nothing here can pass or fail because
of the estate's mood. That matters more than usual for this check, because the thing under test is
the code that decides whether the estate is trustworthy.

Runs without pytest, like release-gate/tests/test_publication_gate.py, so it works on a bare
interpreter and in CI.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCHED = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, SCHED)

import provenance_report as P  # noqa: E402

WRAPPER = os.path.join(SCHED, "provenance-drift.sh")

FAILURES = []


def chk(label, cond, detail=""):
    if cond:
        print("  PASS  %s" % label)
    else:
        print("  FAIL  %s%s" % (label, ("  [%s]" % detail) if detail else ""))
        FAILURES.append(label)


def runtime(name, state, classes=(), sig="VALID", art="OK", ver="CURRENT", act="MATCH",
            intended="87b63f27ee1b", deployed="87b63f2"):
    return {"runtime": name, "composite_state": state, "classes": list(classes),
            "signature_status": sig, "artifact_integrity": art, "version_status": ver,
            "active_target_status": act, "intended_sha": intended, "deployed_sha": deployed}


def verifier_json(*rows):
    return json.dumps({"schema": "netframe.managed-runtime-provenance-report/1",
                       "runtimes": list(rows)})


BOTH_INTACT = verifier_json(runtime("netframe-pipeline-canary", "CURRENT_AND_INTACT"),
                            runtime("netframe-joi-adapter", "CURRENT_AND_INTACT"))


# ---------------------------------------------------------------- A-H: verifier result -> status
def case(label, stdout, rc, expect_status, expect_classes=None, expected_runtimes=2):
    got = P.build(stdout, rc, expected_runtimes)
    ok = got["status"] == expect_status
    if expect_classes is not None:
        ok = ok and got.get("classes", []) == expect_classes
    chk(label, ok, "status=%s reason=%s" % (got["status"], got["reason"]))
    return got


print("== A-H  controlled verifier results map to the right drift result ==")
case("A  both CURRENT_AND_INTACT -> intact", BOTH_INTACT, P.RC_INTACT, P.INTACT)

case("B  VERSION_DRIFT -> drift",
     verifier_json(runtime("netframe-pipeline-canary", "STALE_BUT_INTACT", ["VERSION_DRIFT"],
                           ver="STALE", deployed="a408369"),
                   runtime("netframe-joi-adapter", "CURRENT_AND_INTACT")),
     P.RC_DRIFT, P.DRIFT, ["VERSION_DRIFT"])

case("C  ARTIFACT_MUTATION -> drift",
     verifier_json(runtime("netframe-pipeline-canary", "CURRENT_BUT_MUTATED", ["ARTIFACT_MUTATION"],
                           art="MUTATED"),
                   runtime("netframe-joi-adapter", "CURRENT_AND_INTACT")),
     P.RC_DRIFT, P.DRIFT, ["ARTIFACT_MUTATION"])

case("D  SIGNATURE_FAILURE -> drift",
     verifier_json(runtime("netframe-joi-adapter", "CURRENT_AND_INTACT", ["SIGNATURE_FAILURE"],
                           sig="INVALID"),
                   runtime("netframe-pipeline-canary", "CURRENT_AND_INTACT")),
     P.RC_DRIFT, P.DRIFT, ["SIGNATURE_FAILURE"])

case("E  ACTIVE_TARGET_DRIFT -> drift",
     verifier_json(runtime("netframe-joi-adapter", "CURRENT_AND_INTACT", ["ACTIVE_TARGET_DRIFT"],
                           act="DRIFT"),
                   runtime("netframe-pipeline-canary", "CURRENT_AND_INTACT")),
     P.RC_DRIFT, P.DRIFT, ["ACTIVE_TARGET_DRIFT"])

case("F  UNKNOWN / transport failure -> unknown",
     verifier_json(runtime("netframe-pipeline-canary", "UNKNOWN", sig="UNKNOWN", art="UNKNOWN",
                           ver="UNKNOWN", act="UNKNOWN"),
                   runtime("netframe-joi-adapter", "CURRENT_AND_INTACT")),
     P.RC_UNKNOWN, P.UNKNOWN)

case("G  malformed verifier output -> unknown", "{not json at all", P.RC_INTACT, P.UNKNOWN)
case("H  verifier timeout -> unknown", "", P.RC_TIMEOUT, P.UNKNOWN)

print()
print("== the distinction the whole check exists to preserve ==")
f = P.build("", P.RC_TIMEOUT, 2)
c = P.build(verifier_json(runtime("netframe-joi-adapter", "CURRENT_BUT_MUTATED",
                                  ["ARTIFACT_MUTATION"], art="MUTATED"),
                          runtime("netframe-pipeline-canary", "CURRENT_AND_INTACT")),
            P.RC_DRIFT, 2)
chk("could-not-verify is NOT reported as artifact mutation",
    f["status"] == P.UNKNOWN and "ARTIFACT_MUTATION" not in json.dumps(f))
chk("verified corruption is NOT reported as unknown", c["status"] == P.DRIFT)
chk("the two are different statuses", f["status"] != c["status"])

print()
print("== success needs evidence; failure is believed ==")
chk("exit 0 with a contradicting body is UNKNOWN, not intact",
    P.build(verifier_json(runtime("netframe-joi-adapter", "CURRENT_BUT_MUTATED",
                                  ["ARTIFACT_MUTATION"], art="MUTATED"),
                          runtime("netframe-pipeline-canary", "CURRENT_AND_INTACT")),
            P.RC_INTACT, 2)["status"] == P.UNKNOWN)
chk("exit 0 with no runtimes is UNKNOWN, not intact",
    P.build(verifier_json(), P.RC_INTACT, 2)["status"] == P.UNKNOWN)
chk("exit 0 reporting only ONE of two declared runtimes is UNKNOWN",
    P.build(verifier_json(runtime("netframe-joi-adapter", "CURRENT_AND_INTACT")),
            P.RC_INTACT, 2)["status"] == P.UNKNOWN)
chk("exit 3 with unparseable output stays DRIFT (a real finding is not downgraded)",
    P.build("<<garbage>>", P.RC_DRIFT, 2)["status"] == P.DRIFT)
chk("absent verifier is UNKNOWN", P.build("", P.RC_ABSENT, 2)["status"] == P.UNKNOWN)
chk("stale checkout (exit 2) is UNKNOWN and says so",
    P.build("", P.RC_USAGE, 2)["status"] == P.UNKNOWN
    and "predate" in P.build("", P.RC_USAGE, 2)["reason"])

print()
print("== no remediation, no secrets ==")
src = open(os.path.join(SCHED, "provenance-drift.sh")).read()
body = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
for forbidden in ("systemctl restart", "systemctl start", "ln -sfn", "rsync", "git pull",
                  "git fetch", "git checkout", "scp "):
    chk("wrapper never runs %r" % forbidden, forbidden not in body)
chk("wrapper bounds the verifier with timeout(1)", "timeout \"${timeout_s}\"" in body)
chk("wrapper runs from a configurable pinned deploy, not a hard-coded operator worktree",
    "netframe-current" not in src and ".local/share/netframe/deploy" in src)
rep = P.build(BOTH_INTACT, P.RC_INTACT, 2)
blob = json.dumps(rep).lower()
for secret in ("private", "passphrase", "ssh-ed25519", "begin openssh"):
    chk("report carries no %r" % secret, secret not in blob)
for field in ("runtime", "composite_state", "classes", "intended_sha", "deployed_sha",
              "signature_status", "artifact_integrity", "active_target_status"):
    chk("operator can distinguish %s" % field, field in rep["runtimes"][0])

print()
print("== the wrapper end to end, against recorded verifier output ==")
with tempfile.TemporaryDirectory() as td:
    fx = os.path.join(td, "verifier.json")
    open(fx, "w").write(BOTH_INTACT)
    env = dict(os.environ, NETFRAME_PROVENANCE_FIXTURE=fx, NETFRAME_PROVENANCE_FIXTURE_RC="0")
    p = subprocess.run(["bash", WRAPPER], capture_output=True, text=True, env=env, timeout=60)
    out = json.loads(p.stdout)
    chk("wrapper exits 0 and emits JSON", p.returncode == 0 and out["status"] == P.INTACT)
    chk("a fixture run is stamped as one and can never read as a measurement",
        out.get("fixture") is True and "FIXTURE MODE" in out["reason"])

    open(fx, "w").write(verifier_json(runtime("netframe-joi-adapter", "CURRENT_BUT_MUTATED",
                                              ["ARTIFACT_MUTATION"], art="MUTATED"),
                                      runtime("netframe-pipeline-canary", "CURRENT_AND_INTACT")))
    env["NETFRAME_PROVENANCE_FIXTURE_RC"] = "3"
    p = subprocess.run(["bash", WRAPPER], capture_output=True, text=True, env=env, timeout=60)
    out = json.loads(p.stdout)
    chk("wrapper surfaces drift with its class", out["status"] == P.DRIFT
        and out["classes"] == ["ARTIFACT_MUTATION"])

    env2 = dict(os.environ, NETFRAME_DEPLOY=os.path.join(td, "no-such-checkout"))
    env2.pop("NETFRAME_PROVENANCE_FIXTURE", None)
    p = subprocess.run(["bash", WRAPPER], capture_output=True, text=True, env=env2, timeout=60)
    out = json.loads(p.stdout)
    chk("wrapper with no verifier present is UNKNOWN and contacts nothing",
        out["status"] == P.UNKNOWN and out["exit_code"] == P.RC_ABSENT)
    chk("a real (non-fixture) run is not stamped fixture", out.get("fixture") is not True)

print()
print("== the existing hardening report's consumer must not regress ==")
# netframe_monitor's parse_hardening_drift reads exactly these keys off the daily report. The
# provenance section is ADDITIVE: if adding it ever removed one of them, the dashboard's
# hardening_drift check would go quiet rather than loud, which is the worst possible failure for a
# monitoring change.
wrapper = open(os.path.join(SCHED, "run-hardening-drift-check.sh")).read()
for key in ("generated_epoch", "generated", "any_drift", "drifted_nodes", "nodes"):
    chk("daily report still carries %r for netframe_monitor" % key,
        '"%s"' % key in wrapper)
chk("the provenance section is appended, not substituted for the node report",
    '"nodes":{%s}%s' in wrapper)
chk("an invalid combined document falls back to the original report",
    "write_report \"\"" in wrapper and "without it" in wrapper)
chk("provenance that is not proven-intact raises the flag the dashboard reads",
    'if [[ "${prov_status}" != "intact" ]]; then' in wrapper and 'any_drift="true"' in wrapper)
chk("the daily check still does not enforce anything",
    "--check" in wrapper and "systemctl restart" not in wrapper)
chk("the scheduled path invokes the wrapper rather than reimplementing it",
    "scheduling/provenance-drift.sh" in wrapper)

print()
if FAILURES:
    print("FAILED: %d" % len(FAILURES))
    for f in FAILURES:
        print("  - %s" % f)
    sys.exit(1)
print("ALL PASS")
