"""Tests for the QEMU disposable restore drill.

Hermetic: the real script runs against stub `qm`, `qmrestore` and `pvesh` binaries on PATH. No
Proxmox node is contacted and no VM is created.

Two things distinguish this from the LXC suite. First, a QEMU VM can carry devices bolted to the
physical host, so the tests check that each one is a REFUSAL rather than a silent fixup: a drill
that quietly strips a passthrough device is no longer testing the thing it claims to test. Second,
`qm status` reporting `running` is worthless as boot evidence, because a VM with an unbootable disk
reports exactly that forever while sitting at a firmware prompt. So the suite's central assertion is
that a running QEMU process with no guest-agent answer never reaches LEVEL 3.
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
SCRIPT = os.path.join(REC, "pbs-qemu-restore-drill.sh")

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
    occ=""
    [[ "${STUB_ID_OCCUPIED:-0}" == "1" ]] && occ=",{\"vmid\":${STUB_NEXTID:-112},\"type\":\"qemu\",\"node\":\"pve2\",\"status\":\"running\"}"
    if [[ "${STUB_SRC_MISSING:-0}" == "1" ]]; then echo "[${occ#,}]"
    else echo "[{\"vmid\":110,\"type\":\"qemu\",\"node\":\"pve2\",\"status\":\"running\"}$occ]"; fi ;;
  *"/cluster/ha/resources"*)
    [[ "${STUB_HA:-0}" == "1" ]] && echo "[{\"sid\":\"vm:${STUB_NEXTID:-112}\"}]" || echo '[]' ;;
  *"/cluster/replication"*)
    [[ "${STUB_REPL:-0}" == "1" ]] && echo "[{\"guest\":\"${STUB_NEXTID:-112}\"}]" || echo '[]' ;;
  *"/qemu/110/config"*)
    if [[ "${STUB_NO_AGENT:-0}" == "1" ]]; then echo '{"digest":"abc123","name":"src"}'
    else echo '{"digest":"abc123","name":"src","agent":"enabled=1"}'; fi ;;
  *"/content"*)
    case "${STUB_CONTENT:-ok}" in
      malformed) echo "not json" ;;
      missing)   echo '[]' ;;
      unverified) echo '[{"volid":"randy-pbs:backup/vm/110/S","verification":{"state":"none"}}]' ;;
      failed)    echo '[{"volid":"randy-pbs:backup/vm/110/S","verification":{"state":"failed"}}]' ;;
      *)         echo '[{"volid":"randy-pbs:backup/vm/110/S","verification":{"state":"ok"}}]' ;;
    esac ;;
esac
exit 0
'''

STUB_QMRESTORE = r'''#!/usr/bin/env bash
echo "qmrestore $*" >> "$STUB_CALLS"
[[ "${STUB_RESTORE_FAIL:-0}" == "1" ]] && exit 1
[[ "${STUB_RESTORE_NOCONFIG:-0}" == "1" ]] && exit 0
vmid="$2"
{ echo "agent: enabled=1"; echo "bios: ovmf"; echo "boot: order=scsi0"
  echo "efidisk0: local-lvm:vm-$vmid-disk-0,size=4M"
  [[ "${STUB_NO_DISK:-0}" == "1" ]] || echo "scsi0: local-lvm:vm-$vmid-disk-1,size=64G"
  echo "net0: virtio=AA:BB:CC:DD:EE:FF,bridge=vmbr0"
  [[ "${STUB_HOSTPCI:-0}" == "1" ]] && echo "hostpci0: 0000:01:00.0"
  [[ "${STUB_USB:-0}" == "1" ]] && echo "usb0: host=1234:5678"
  [[ "${STUB_ARGS:-0}" == "1" ]] && echo "args: -device foo"
  [[ "${STUB_HOOKSCRIPT:-0}" == "1" ]] && echo "hookscript: local:snippets/h.pl"
  [[ "${STUB_RAWDISK:-0}" == "1" ]] && echo "scsi1: /dev/sdb"
  [[ "${STUB_ONBOOT:-0}" == "1" ]] && echo "onboot: 1" || echo "onboot: 0"
  echo "tags: iot"; } > "$PBSDRILL_QEMU_CONF_DIR/$vmid.conf"
echo stopped > "$STUB_STATE/status"
exit 0
'''

STUB_QM = r'''#!/usr/bin/env bash
echo "qm $*" >> "$STUB_CALLS"
CFG="$PBSDRILL_QEMU_CONF_DIR/$2.conf"
case "$1" in
  config) cat "$CFG" 2>/dev/null; exit 0 ;;
  set)
    if [[ "$3" == "--delete" ]]; then
      [[ "${STUB_DELETE_SILENT_NOOP:-0}" == "1" && "$4" == net* ]] && exit 0
      sed -i "/^$4:/d" "$CFG"
    elif [[ "$3" == "--onboot" ]]; then
      [[ "${STUB_ONBOOT_SET_NOOP:-0}" == "1" ]] || sed -i "s/^onboot:.*/onboot: $4/" "$CFG"
    fi
    exit 0 ;;
  status) echo "status: $(cat "$STUB_STATE/status" 2>/dev/null || echo missing)"; exit 0 ;;
  start)
    [[ "${STUB_START_FAIL:-0}" == "1" ]] && exit 1
    echo running > "$STUB_STATE/status"; exit 0 ;;
  agent)
    # The whole point: a running QEMU process does not imply the agent answers.
    [[ "$(cat "$STUB_STATE/status" 2>/dev/null)" == "running" ]] || exit 1
    [[ "${STUB_AGENT_DEAD:-0}" == "1" ]] && exit 1
    case "$3" in
      ping) exit 0 ;;
      get-osinfo) echo '{"id":"haos","version":"18.1"}'; exit 0 ;;
    esac
    exit 0 ;;
  shutdown|stop)
    [[ "${STUB_SHUTDOWN_FAIL:-0}" == "1" ]] && exit 1
    echo stopped > "$STUB_STATE/status"; exit 0 ;;
  destroy)
    [[ "${STUB_DESTROY_FAIL:-0}" == "1" ]] && exit 1
    rm -f "$CFG"; exit 0 ;;
esac
exit 0
'''


def run(**env):
    td = tempfile.mkdtemp(prefix="qdrill.")
    bindir = os.path.join(td, "bin")
    os.makedirs(bindir)
    for name, body in (("pvesh", STUB_PVESH), ("qm", STUB_QM), ("qmrestore", STUB_QMRESTORE)):
        p = os.path.join(bindir, name)
        with open(p, "w") as fh:
            fh.write(body)
        os.chmod(p, 0o755)
    state = os.path.join(td, "state")
    os.makedirs(state)
    conf = os.path.join(td, "conf")
    os.makedirs(conf)
    ev = os.path.join(td, "ev")
    e = dict(os.environ)
    e.update({
        "PATH": bindir + ":" + os.environ["PATH"],
        "STUB_CALLS": os.path.join(td, "calls"),
        "STUB_STATE": state,
        "PBSDRILL_EVIDENCE_DIR": ev,
        "PBSDRILL_QEMU_CONF_DIR": conf,
        "PBSDRILL_BOOT_TIMEOUT": "6",
        "PBSDRILL_RESTORE_TIMEOUT": "20",
        "PBSDRILL_STOP_TIMEOUT": "10",
        "PBSDRILL_CMD_TIMEOUT": "10",
    })
    src = e.pop("_SRC", "110")
    e.update({k: str(v) for k, v in env.items()})
    p = subprocess.run(["/bin/bash", SCRIPT, "--source-vmid", src,
                        "--snapshot", "randy-pbs:backup/vm/110/S"],
                       capture_output=True, text=True, env=e, timeout=180, cwd=td)
    art = None
    if os.path.isdir(ev):
        for f in os.listdir(ev):
            with open(os.path.join(ev, f)) as fh:
                art = json.load(fh)
    calls = open(e["STUB_CALLS"]).read() if os.path.exists(e["STUB_CALLS"]) else ""
    leftover = os.listdir(conf)
    shutil.rmtree(td, ignore_errors=True)
    return p.returncode, (p.stdout + p.stderr), art, calls, leftover


print("== the healthy path ==")
rc, out, art, calls, left = run()
chk("a healthy drill succeeds", rc == 0, out.strip().splitlines()[-1] if out.strip() else "")
chk("LEVEL 3 is claimed only on success", art and art["evidence_level"] == 3)
chk("guest_type is qemu", art and art["source_guest_type"] == "qemu")
chk("boot evidence method is recorded", art and art["boot_evidence_method"] == "guest_agent")
chk("the agent answer is the evidence", art and "guest-agent responded" in art["boot_detail"])
chk("application recovery is never claimed", art and art["application_recovery_claimed"] is False)
chk("the level name is RESTORED_SYSTEM_BOOTABLE, never application recovery",
    art and art["evidence_level_name"] == "RESTORED_SYSTEM_BOOTABLE")
chk("no VALUE anywhere claims application recovery",
    art and not any("APPLICATION_RECOVERY" in str(v).upper() for v in art.values()))
chk("isolation method recorded", art and art["network_isolation_method"] == "all_nics_removed")
chk("removed devices recorded", art and art["removed_devices"] == ["net0"])
chk("no config left behind", left == [])
chk("exactly one restore", len([x for x in calls.splitlines() if x.startswith("qmrestore")]) == 1)
chk("exactly one destroy", len([x for x in calls.splitlines() if x.startswith("qm destroy")]) == 1)
chk("every destroy targets the disposable id",
    all(x.split()[2] == "112" for x in calls.splitlines() if x.startswith("qm destroy")))
chk("no command is ever aimed at the source vm",
    not any(x.startswith(("qm ", "qmrestore ")) and len(x.split()) > 2 and x.split()[2] == "110"
            for x in calls.splitlines()))
chk("no destroy is aimed at a PBS snapshot",
    not any("backup/vm/" in x for x in calls.splitlines() if x.startswith("qm destroy")))
chk("restore never uses --force, --start or --ha-managed",
    not any(f in calls for f in ("--force", "--start", "--ha-managed")))
chk("the NIC is removed before the VM is started",
    calls.index("qm set 112 --delete net0") < calls.index("qm start"))

print()
print("== a running QEMU process is not a booted guest ==")
rc, out, art, calls, left = run(STUB_AGENT_DEAD=1)
chk("qemu running with no agent answer is NOT level 3",
    rc != 0 and art and art["evidence_level"] == 0)
chk("...it is recorded as no_guest_evidence", art and art["boot_result"] == "no_guest_evidence")
chk("...and says the process ran but the guest did not answer",
    art and "qemu process ran" in art["boot_detail"])
chk("...and the vm is still cleaned up", "qm destroy" in calls and left == [])

rc, out, art, calls, left = run(STUB_NO_AGENT=1)
chk("a source vm without an agent is refused before any restore",
    rc != 0 and "no guest agent" in out and "qmrestore" not in calls)

print()
print("== host-coupled devices are refusals, not silent fixups ==")
for label, env in (("hostpci", {"STUB_HOSTPCI": 1}), ("usb", {"STUB_USB": 1}),
                   ("args", {"STUB_ARGS": 1}), ("hookscript", {"STUB_HOOKSCRIPT": 1})):
    rc, out, art, calls, left = run(**env)
    chk("%s present -> refused before boot" % label,
        rc != 0 and "host-coupled" in out and "qm start" not in calls)
    chk("%s present -> not level 3, and cleaned up" % label,
        art and art["evidence_level"] == 0 and left == [])

rc, out, art, calls, left = run(STUB_RAWDISK=1)
chk("a raw host block device is refused before boot",
    rc != 0 and "raw host block device" in out and "qm start" not in calls)

print()
print("== the other refusals ==")
cases = [
    ("occupied vmid", {"STUB_ID_OCCUPIED": 1}, "occupied"),
    ("source == target", {"STUB_NEXTID": 110}, "equals the source"),
    ("missing snapshot", {"STUB_CONTENT": "missing"}, "not found"),
    ("verification none", {"STUB_CONTENT": "unverified"}, "unverified backup"),
    ("verification failed", {"STUB_CONTENT": "failed"}, "unverified backup"),
    ("malformed metadata", {"STUB_CONTENT": "malformed"}, "malformed"),
    ("restore failure", {"STUB_RESTORE_FAIL": 1}, "qmrestore failed"),
    ("restore exit 0 with no config", {"STUB_RESTORE_NOCONFIG": 1}, "no config exists"),
    ("no boot disk", {"STUB_NO_DISK": 1}, "no boot disk"),
    ("nic survives deletion", {"STUB_DELETE_SILENT_NOOP": 1}, "isolation failed"),
    ("autostart disable silently fails", {"STUB_ONBOOT": 1, "STUB_ONBOOT_SET_NOOP": 1},
     "autostart is enabled"),
    ("HA membership", {"STUB_HA": 1}, "HA-managed"),
    ("replication job", {"STUB_REPL": 1}, "replication job"),
    ("start failure", {"STUB_START_FAIL": 1}, "qm start failed"),
    ("cleanup failure", {"STUB_DESTROY_FAIL": 1}, "cleanup failed"),
]
for label, env, needle in cases:
    rc, out, art, calls, left = run(**env)
    chk("%s -> refused" % label, rc != 0 and needle in out, out.strip().splitlines()[-2:] if out else "")
    chk("%s -> never claims LEVEL 3" % label,
        art and art["evidence_level"] == 0 and art["evidence_level_name"] == "NOTHING_PROVEN")

rc, out, art, calls, left = run(STUB_ONBOOT=1, STUB_ONBOOT_SET_NOOP=1)
chk("autostart refusal happens before the vm is started", "qm start" not in calls)
rc, out, art, calls, left = run(STUB_ONBOOT=1)
chk("a restored onboot=1 is actively disabled, not merely detected",
    rc == 0 and "qm set 112 --onboot 0" in calls and art["evidence_level"] == 3)
rc, out, art, calls, left = run(STUB_HA=1)
chk("HA refusal happens before the vm is started", "qm start" not in calls)

print()
print("== dry-run mutates nothing ==")
rc, out, art, calls, left = run(_DRY=1) if False else (None, None, None, None, None)
td = tempfile.mkdtemp(prefix="qdry.")
try:
    bindir = os.path.join(td, "bin")
    os.makedirs(bindir)
    for name, body in (("pvesh", STUB_PVESH), ("qm", STUB_QM), ("qmrestore", STUB_QMRESTORE)):
        p = os.path.join(bindir, name)
        with open(p, "w") as fh:
            fh.write(body)
        os.chmod(p, 0o755)
    st = os.path.join(td, "state")
    os.makedirs(st)
    cf = os.path.join(td, "conf")
    os.makedirs(cf)
    ev = os.path.join(td, "ev")
    e = dict(os.environ, PATH=bindir + ":" + os.environ["PATH"],
             STUB_CALLS=os.path.join(td, "calls"), STUB_STATE=st,
             PBSDRILL_EVIDENCE_DIR=ev, PBSDRILL_QEMU_CONF_DIR=cf)
    p = subprocess.run(["/bin/bash", SCRIPT, "--source-vmid", "110",
                        "--snapshot", "randy-pbs:backup/vm/110/S", "--dry-run"],
                       capture_output=True, text=True, env=e, timeout=120)
    calls = open(e["STUB_CALLS"]).read() if os.path.exists(e["STUB_CALLS"]) else ""
    art = None
    if os.path.isdir(ev):
        for f in os.listdir(ev):
            with open(os.path.join(ev, f)) as fh:
                art = json.load(fh)
    chk("dry-run exits 0", p.returncode == 0)
    chk("dry-run performs no restore, start or destroy",
        all(x not in calls for x in ("qmrestore", "qm start", "qm destroy")))
    chk("dry-run claims no level", art and art["evidence_level"] == 0)
finally:
    shutil.rmtree(td, ignore_errors=True)

print()
print("== structural properties ==")
src = open(SCRIPT).read()
body = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
chk("LEVEL 3 is only set after cleanup succeeds",
    body.index('cleanup_result="ok"') < body.index("level=3"))
chk("the drill never prunes or forgets a backup",
    all(x not in body for x in ("prune", "forget", "--remove-vanished")))
chk("destroy always uses --destroy-unreferenced-disks so EFI/TPM volumes go too",
    "--destroy-unreferenced-disks 1" in body)
chk("no generic shell runner", all(x not in body for x in ("eval ", 'bash -c "$')))
for t in ("t_restore", "t_stop", "t_cmd"):
    chk("bounded timeout %s wraps its command" % t, ('timeout "${%s}"' % t) in body)
chk("the boot wait is bounded by a deadline",
    "deadline=$((SECONDS + t_boot))" in body and "(( SECONDS < deadline ))" in body)
chk("cleanup refuses on a source/target collision", "refused_source_collision" in body)

print()
if FAILURES:
    print("FAILED: %d" % len(FAILURES))
    for f in FAILURES:
        print("  - %s" % f)
    sys.exit(1)
print("ALL PASS")
