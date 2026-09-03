"""Tests for the PBS disposable guest restore drill.

Hermetic: the real script runs against stub `pct` and `pvesh` binaries placed first on PATH. No
Proxmox node is contacted, no backup is read, no guest is created.

The property under test is not that the drill works. It is that the drill REFUSES, in every way it
could otherwise do damage: restoring over an occupied id, restoring onto the source guest itself,
booting a clone that still has a network device, booting one that is HA-managed or replicated or
set to autostart, and claiming LEVEL 3 when the disposable guest was left behind. A restore drill
that is merely usually careful is a production outage with extra steps.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REC = os.path.abspath(os.path.join(HERE, ".."))
SCRIPT = os.path.join(REC, "pbs-guest-restore-drill.sh")

FAILURES = []


def chk(label, cond, detail=""):
    if cond:
        print("  PASS  %s" % label)
    else:
        print("  FAIL  %s%s" % (label, ("  [%s]" % detail) if detail else ""))
        FAILURES.append(label)


STUB_PVESH = r'''#!/usr/bin/env bash
echo "pvesh $*" >> "$STUB_CALLS"
case "$*" in
  *"/cluster/nextid"*) echo "${STUB_NEXTID:-112}" ;;
  *"/cluster/resources"*)
    if [[ "${STUB_ID_OCCUPIED:-0}" == "1" ]]; then
      echo "[{\"vmid\":${STUB_NEXTID:-112},\"status\":\"running\",\"type\":\"lxc\"},{\"vmid\":106,\"status\":\"running\",\"type\":\"lxc\"}]"
    else
      echo '[{"vmid":106,"status":"running","type":"lxc"}]'
    fi ;;
  *"/cluster/ha/resources"*)
    [[ "${STUB_HA:-0}" == "1" ]] && echo "[{\"sid\":\"ct:${STUB_NEXTID:-112}\"}]" || echo '[]' ;;
  *"/cluster/replication"*)
    [[ "${STUB_REPL:-0}" == "1" ]] && echo "[{\"guest\":\"${STUB_NEXTID:-112}\"}]" || echo '[]' ;;
  *"/content"*)
    case "${STUB_CONTENT:-ok}" in
      malformed) echo "not json at all" ;;
      missing)   echo '[]' ;;
      unverified) echo '[{"volid":"randy-pbs:backup/ct/106/S","verification":{"state":"none"}}]' ;;
      none)      echo '[{"volid":"randy-pbs:backup/ct/106/S"}]' ;;
      failed)    echo '[{"volid":"randy-pbs:backup/ct/106/S","verification":{"state":"failed"}}]' ;;
      *)         echo '[{"volid":"randy-pbs:backup/ct/106/S","verification":{"state":"ok"}}]' ;;
    esac ;;
esac
exit 0
'''

STUB_PCT = r'''#!/usr/bin/env bash
echo "pct $*" >> "$STUB_CALLS"
CFG="$PBSDRILL_CONF_DIR/$2.conf"
case "$1" in
  restore)
    [[ "${STUB_RESTORE_FAIL:-0}" == "1" ]] && exit 1
    if [[ "${STUB_RESTORE_SLOW:-0}" == "1" ]]; then sleep 30; fi
    [[ "${STUB_RESTORE_NOCONFIG:-0}" == "1" ]] && exit 0
    { echo "arch: amd64"; echo "hostname: drill"
      [[ "${STUB_NO_ROOTFS:-0}" == "1" ]] || echo "rootfs: local-lvm:vm-$2-disk-0,size=8G"
      echo "net0: name=eth0,bridge=vmbr0,hwaddr=AA:BB:CC:DD:EE:FF,ip=192.168.10.148/24"
      [[ "${STUB_ONBOOT:-0}" == "1" ]] && echo "onboot: 1" || echo "onboot: 0"
      echo "unprivileged: 1"; } > "$CFG"
    echo stopped > "$STUB_STATE/status"
    exit 0 ;;
  config) cat "$PBSDRILL_CONF_DIR/$2.conf" 2>/dev/null; exit 0 ;;
  set)
    if [[ "$3" == "--delete" ]]; then
      [[ "${STUB_DELETE_FAIL:-0}" == "1" ]] && exit 1
      [[ "${STUB_DELETE_SILENT_NOOP:-0}" == "1" ]] && exit 0
      sed -i "/^$4:/d" "$PBSDRILL_CONF_DIR/$2.conf"; fi
    exit 0 ;;
  status) echo "status: $(cat "$STUB_STATE/status" 2>/dev/null || echo missing)"; exit 0 ;;
  start)
    [[ "${STUB_START_FAIL:-0}" == "1" ]] && exit 1
    [[ "${STUB_BOOT_HANG:-0}" == "1" ]] || echo running > "$STUB_STATE/status"
    exit 0 ;;
  exec)
    [[ "$(cat "$STUB_STATE/status" 2>/dev/null)" == "running" ]] || exit 1
    case "$*" in
      *"ps -p 1"*) [[ "${STUB_NO_INIT:-0}" == "1" ]] && echo "" || echo "systemd"; exit 0 ;;
      *"test -r /etc/os-release"*) [[ "${STUB_FS_UNREADABLE:-0}" == "1" ]] && exit 1 || exit 0 ;;
      *"is-system-running"*) echo "${STUB_SYSSTATE:-degraded}"; exit 0 ;;
      *) exit 0 ;;
    esac ;;
  shutdown|stop) echo stopped > "$STUB_STATE/status"; exit 0 ;;
  destroy)
    [[ "${STUB_DESTROY_FAIL:-0}" == "1" ]] && exit 1
    rm -f "$PBSDRILL_CONF_DIR/$2.conf"; exit 0 ;;
esac
exit 0
'''


def run(**env):
    td = tempfile.mkdtemp(prefix="drill-test.")
    bindir = os.path.join(td, "bin")
    os.makedirs(bindir)
    for name, body in (("pvesh", STUB_PVESH), ("pct", STUB_PCT)):
        p = os.path.join(bindir, name)
        with open(p, "w") as fh:
            fh.write(body)
        os.chmod(p, 0o755)
    state = os.path.join(td, "state")
    os.makedirs(state)
    pve = os.path.join(td, "etc-pve-lxc")
    os.makedirs(pve)
    ev = os.path.join(td, "evidence")
    e = dict(os.environ)
    e.update({
        "PATH": bindir + ":" + os.environ["PATH"],
        "STUB_CALLS": os.path.join(td, "calls"),
        "STUB_STATE": state,
        "PBSDRILL_EVIDENCE_DIR": ev,
        "PBSDRILL_CONF_DIR": pve,
        "PBSDRILL_BOOT_TIMEOUT": "6",
        "PBSDRILL_RESTORE_TIMEOUT": "10",
        "PBSDRILL_STOP_TIMEOUT": "10",
        "PBSDRILL_CMD_TIMEOUT": "10",
    })
    e.update({k: str(v) for k, v in env.items()})
    args = ["/bin/bash", SCRIPT, "--source-ctid", e.pop("_SRC", "106"),
            "--snapshot", "randy-pbs:backup/ct/106/S"]
    p = subprocess.run(args, capture_output=True, text=True, env=e, timeout=180, cwd=td)
    art = None
    if os.path.isdir(ev):
        for f in os.listdir(ev):
            with open(os.path.join(ev, f)) as fh:
                art = json.load(fh)
    calls = open(e["STUB_CALLS"]).read() if os.path.exists(e["STUB_CALLS"]) else ""
    shutil.rmtree(td, ignore_errors=True)
    return p.returncode, (p.stdout + p.stderr), art, calls


# The script keys "config exists" off /etc/pve/lxc/<id>.conf, which a test cannot create. Every
# case below therefore exercises the gates that run BEFORE that point, plus the artifact contract.
print("== refusals before anything is created ==")
rc, out, art, calls = run(STUB_CONTENT="missing")
chk("missing backup is refused", rc != 0 and "not found in the datastore" in out)
chk("no restore is attempted for a missing backup", "pct restore" not in calls)

rc, out, art, calls = run(STUB_CONTENT="unverified")
chk("unverified backup is refused", rc != 0 and "unverified backup" in out)
chk("no restore is attempted for an unverified backup", "pct restore" not in calls)

rc, out, art, calls = run(STUB_CONTENT="failed")
chk("a backup whose verification FAILED is refused", rc != 0 and "verification state is 'failed'" in out)

rc, out, art, calls = run(STUB_CONTENT="none")
chk("a backup with no verification record is refused", rc != 0)

rc, out, art, calls = run(STUB_CONTENT="malformed")
chk("malformed PBS metadata is refused", rc != 0 and "malformed" in out)

rc, out, art, calls = run(STUB_ID_OCCUPIED=1)
chk("an occupied target id is refused", rc != 0 and "occupied" in out)
chk("no restore is attempted onto an occupied id", "pct restore" not in calls)

rc, out, art, calls = run(STUB_NEXTID=106)
chk("source == target is refused", rc != 0 and "equals the source" in out)
chk("no restore is attempted when ids collide", "pct restore" not in calls)

print()
print("== the drill never claims what it did not prove ==")
for label, env in (("missing backup", {"STUB_CONTENT": "missing"}),
                   ("occupied id", {"STUB_ID_OCCUPIED": 1}),
                   ("id collision", {"STUB_NEXTID": 106})):
    rc, out, art, calls = run(**env)
    chk("%s -> artifact status fail" % label, art is not None and art["status"] == "fail")
    chk("%s -> evidence_level 0" % label, art is not None and art["evidence_level"] == 0)
    chk("%s -> level name NOTHING_PROVEN" % label,
        art is not None and art["evidence_level_name"] == "NOTHING_PROVEN")

rc, out, art, calls = run(_SRC="106")
chk("a dry-run-less failed run still records the source id and snapshot",
    art is not None and art["source_guest_id"] == "106" and art["source_snapshot"].endswith("/S"))

print()
print("== dry-run stops before any mutation ==")
td = tempfile.mkdtemp(prefix="drill-dry.")
try:
    bindir = os.path.join(td, "bin")
    os.makedirs(bindir)
    for name, body in (("pvesh", STUB_PVESH), ("pct", STUB_PCT)):
        p = os.path.join(bindir, name)
        with open(p, "w") as fh:
            fh.write(body)
        os.chmod(p, 0o755)
    st = os.path.join(td, "state")
    os.makedirs(st)
    ev = os.path.join(td, "ev")
    e = dict(os.environ, PATH=bindir + ":" + os.environ["PATH"],
             STUB_CALLS=os.path.join(td, "calls"), STUB_STATE=st, PBSDRILL_EVIDENCE_DIR=ev,
             PBSDRILL_CONF_DIR=os.path.join(td, "conf"))
    os.makedirs(os.path.join(td, "conf"), exist_ok=True)
    p = subprocess.run(["/bin/bash", SCRIPT, "--source-ctid", "106",
                        "--snapshot", "randy-pbs:backup/ct/106/S", "--dry-run"],
                       capture_output=True, text=True, env=e, timeout=120)
    calls = open(e["STUB_CALLS"]).read() if os.path.exists(e["STUB_CALLS"]) else ""
    art = None
    if os.path.isdir(ev):
        for f in os.listdir(ev):
            art = json.load(open(os.path.join(ev, f)))
    chk("dry-run exits 0", p.returncode == 0)
    chk("dry-run performs no restore, start or destroy",
        all(x not in calls for x in ("pct restore", "pct start", "pct destroy")))
    chk("dry-run claims no level", art is not None and art["evidence_level"] == 0)
finally:
    shutil.rmtree(td, ignore_errors=True)

print()
print("== the full path: restore, isolate, boot, prove, destroy ==")
rc, out, art, calls = run()
chk("a healthy drill succeeds", rc == 0, out.strip().splitlines()[-1] if out.strip() else "")
chk("it claims LEVEL 3 only on success",
    art is not None and art["evidence_level"] == 3 and art["status"] == "pass")
chk("the level name is RESTORED_SYSTEM_BOOTABLE, never application recovery",
    art is not None and art["evidence_level_name"] == "RESTORED_SYSTEM_BOOTABLE")
chk("isolation method is recorded", art is not None
    and art["network_isolation_method"] == "all_net_devices_removed")
chk("the network device really was deleted before start",
    calls.index("pct set") < calls.index("pct start"))
chk("the guest was destroyed", "pct destroy" in calls and art["cleanup_result"] == "ok")

# The call trace is the evidence. Source-level greps cannot see an extra command injected at the
# end of a successful run, and "one destructive command too many" is exactly how a drill turns into
# an outage: a second restore, a destroy aimed at the snapshot, or any command aimed at the source.
restores = [ln for ln in calls.splitlines() if ln.startswith("pct restore")]
destroys = [ln for ln in calls.splitlines() if ln.startswith("pct destroy")]
chk("exactly one restore is ever performed", len(restores) == 1, str(restores))
chk("exactly one destroy is ever performed", len(destroys) == 1, str(destroys))
chk("every destroy targets the disposable id and nothing else",
    all(ln.split()[2] == "112" for ln in destroys), str(destroys))
chk("no destroy is ever aimed at a PBS snapshot",
    not any("backup/ct/" in ln for ln in destroys), str(destroys))
chk("no pct command is ever aimed at the source guest",
    not any(ln.startswith("pct ") and len(ln.split()) > 2 and ln.split()[2] == "106"
            for ln in calls.splitlines()),
    str([ln for ln in calls.splitlines() if ln.startswith("pct ") and len(ln.split()) > 2
         and ln.split()[2] == "106"]))
chk("the snapshot is only ever an argument to restore, never to anything else",
    all(ln.startswith("pct restore") for ln in calls.splitlines() if "backup/ct/106/S" in ln
        and ln.startswith("pct ")),
    str([ln for ln in calls.splitlines() if "backup/ct/106/S" in ln and ln.startswith("pct ")]))

rc, out, art, calls = run(STUB_NO_INIT=1)
chk("a guest with no PID 1 is not LEVEL 3", rc != 0 and art["evidence_level"] == 0)
chk("...and it is cleaned up anyway", "pct destroy" in calls)

rc, out, art, calls = run(STUB_FS_UNREADABLE=1)
chk("an unreadable restored filesystem is not LEVEL 3", rc != 0 and art["evidence_level"] == 0)

rc, out, art, calls = run(STUB_SYSSTATE="starting")
chk("an init stuck in 'starting' is not a settled boot", rc != 0 and art["evidence_level"] == 0)

rc, out, art, calls = run(STUB_SYSSTATE="degraded")
chk("'degraded' IS accepted, because isolation makes network units fail by design",
    rc == 0 and art["evidence_level"] == 3)

rc, out, art, calls = run(STUB_BOOT_HANG=1)
chk("a guest that never boots times out and is not LEVEL 3", rc != 0 and art["evidence_level"] == 0)

rc, out, art, calls = run(STUB_START_FAIL=1)
chk("a failed start is not LEVEL 3", rc != 0 and art["evidence_level"] == 0)

rc, out, art, calls = run(STUB_RESTORE_FAIL=1)
chk("a failed restore is not LEVEL 3", rc != 0 and art["restore_result"] == "failed")
chk("no boot is attempted after a failed restore", "pct start" not in calls)

rc, out, art, calls = run(STUB_RESTORE_NOCONFIG=1)
chk("restore exiting 0 with no config is still a failure",
    rc != 0 and "no config exists" in out)

rc, out, art, calls = run(STUB_NO_ROOTFS=1)
chk("a restored guest with no rootfs is refused", rc != 0 and "no rootfs" in out)

rc, out, art, calls = run(STUB_DELETE_SILENT_NOOP=1)
chk("a network device that survives deletion aborts before boot",
    rc != 0 and "isolation failed" in out)
chk("...and the guest is never started", "pct start" not in calls)

rc, out, art, calls = run(STUB_ONBOOT=1)
chk("autostart left enabled aborts before boot", rc != 0 and "autostart" in out)

rc, out, art, calls = run(STUB_HA=1)
chk("HA membership aborts before boot", rc != 0 and "HA-managed" in out)

rc, out, art, calls = run(STUB_REPL=1)
chk("a replication job aborts before boot", rc != 0 and "replication job" in out)

rc, out, art, calls = run(STUB_DESTROY_FAIL=1)
chk("a failed cleanup is reported and never claims LEVEL 3",
    rc != 0 and art["evidence_level"] == 0 and art["cleanup_result"] == "failed")
chk("...and says so plainly", "cleanup failed" in out)

print()
print("== the safety properties are structural, not incidental ==")
src = open(SCRIPT).read()
body = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
chk("restore always passes --onboot 0", "--onboot 0" in body)
chk("restore always passes --start 0", "--start 0" in body)
chk("every network device is deleted before boot",
    "--delete" in body and "grep -cE '^net[0-9]+'" in body)
chk("a surviving network device aborts before boot",
    'refusing to boot' in body and 'network isolation failed' in body)
chk("HA membership aborts before boot", "HA-managed; refusing to boot" in body)
chk("replication aborts before boot", "replication job; refusing to boot" in body)
chk("autostart aborts before boot", "autostart is enabled" in body)
chk("source/target collision is checked before restore",
    body.index("equals the source ctid") < body.index("pct restore"))
chk("the drill never deletes a PBS snapshot",
    all(x not in body for x in ("proxmox-backup-client snapshot forget", "prune", "forget")))
chk("cleanup refuses if the target id equals the source",
    "refused_source_collision" in body)
chk("LEVEL 3 is only set after cleanup succeeds",
    body.index("cleanup_result=\"ok\"") < body.index("level=3"))
chk("no generic shell runner exists in the tool",
    all(x not in body for x in ("eval ", "$(cat ", "bash -c \"$")))
for t in ("t_restore", "t_stop", "t_cmd"):
    chk("bounded timeout %s wraps its command" % t, ('timeout "${%s}"' % t) in body)
# t_boot bounds a polling loop rather than a single command, so it is asserted on its own mechanism:
# a deadline computed from SECONDS, and a failure path when the deadline passes.
chk("the boot wait is bounded by a deadline, not unbounded polling",
    "deadline=$((SECONDS + t_boot))" in body and "(( SECONDS < deadline ))" in body)
chk("a boot that never settles is recorded as a timeout and cleaned up",
    'boot_result="timeout"' in body)
chk("'starting' is not accepted as a settled boot",
    "unsettled" in body and "running|degraded" in body)

print()
if FAILURES:
    print("FAILED: %d" % len(FAILURES))
    for f in FAILURES:
        print("  - %s" % f)
    sys.exit(1)
print("ALL PASS")
