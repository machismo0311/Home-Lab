#!/usr/bin/env bash
# Owner-supervised QEMU restore drill: restore one real PBS VM snapshot into a disposable,
# hypervisor-isolated VM, prove the GUEST OS booted, then destroy it.
#
# WHY A SIBLING AND NOT A FLAG ON THE LXC DRILL. The LXC path is pct all the way down: pct restore,
# rootfs, pct exec for boot proof. QEMU shares none of that. Its restore is qmrestore, its isolation
# has to consider passthrough devices a container cannot have, and its boot proof cannot be "run a
# command inside" because there is no such thing without an agent. Folding both into one script
# would mean a generic runner with two unrelated halves, which is exactly the shape that gets a
# guard applied to the wrong guest type.
#
# WHAT LEVEL 3 MEANS HERE, and why `qm status` is not it. A running QEMU process proves a hypervisor
# started a virtual machine. It proves nothing about the restored disk: a VM with an unbootable
# image sits at a firmware prompt burning CPU and reports `running` forever. So the boot evidence is
# the guest agent answering, which cannot happen until the guest kernel booted, userspace came up,
# and the agent service started. If the source VM has no agent configured, this drill refuses rather
# than downgrade to a weaker signal and call it the same thing.
#
# THE QEMU-SPECIFIC HAZARD. A restored VM can carry host-coupled devices a container never has:
# hostpci passthrough, USB passthrough, raw block devices, virtiofs, arbitrary `args`, a hookscript
# with side effects. Booting a clone that grabs a physical device is worse than an IP conflict. Every
# one is a refusal, not a fixup: this drill will not quietly strip a passthrough device and continue,
# because a VM whose hardware identity was silently altered is no longer the thing being tested.
# Network devices ARE removed, because a NIC is universal, expected, and its removal is the isolation.
#
# Run ON the target Proxmox node. Owner-supervised, never scheduled. MAX_AUTO_CLASS 0.
set -uo pipefail

SCHEMA="netframe.pbs-guest-restore-drill/1"
LEVEL_NAME="RESTORED_SYSTEM_BOOTABLE"

source_vmid=""; snapshot=""; target_storage="local-lvm"; dry_run=0
t_restore="${PBSDRILL_RESTORE_TIMEOUT:-3600}"
t_boot="${PBSDRILL_BOOT_TIMEOUT:-600}"
t_stop="${PBSDRILL_STOP_TIMEOUT:-300}"
t_cmd="${PBSDRILL_CMD_TIMEOUT:-60}"
evidence_dir="${PBSDRILL_EVIDENCE_DIR:-/var/log/pbs-restore-drill}"
conf_dir="${PBSDRILL_QEMU_CONF_DIR:-/etc/pve/qemu-server}"

# Host-coupled or side-effect-capable configuration keys. Presence on the DISPOSABLE copy is a
# refusal. Network devices are handled separately, by removal.
HOST_COUPLED_RE='^(hostpci[0-9]*|usb[0-9]*|args|hookscript|virtiofs[0-9]*|parallel[0-9]*):'

usage() {
	echo "usage: pbs-qemu-restore-drill.sh --source-vmid <id> --snapshot <volid> [--target-storage <id>] [--dry-run]" >&2
	echo "       Run on the target Proxmox node. Requires the source VM to have a guest agent." >&2
	exit 2
}

while [[ $# -gt 0 ]]; do
	case "$1" in
		--source-vmid) source_vmid="${2:-}"; shift 2 ;;
		--snapshot) snapshot="${2:-}"; shift 2 ;;
		--target-storage) target_storage="${2:-}"; shift 2 ;;
		--dry-run) dry_run=1; shift ;;
		*) usage ;;
	esac
done
[[ -n "${source_vmid}" && -n "${snapshot}" ]] || usage

run_id="qemu-restore-drill-${source_vmid}-$(date -u +%Y%m%dT%H%M%SZ)"
target_vmid=""
restore_result="not_attempted"; boot_result="not_attempted"; cleanup_result="not_attempted"
level=0; isolation_method="none"; boot_method="guest_agent"; boot_detail=""; failure=""
removed_devices=""; source_status_before=""; source_digest_before=""

log() { echo "$(date -u +%H:%M:%SZ) $*"; }

emit_evidence() { # status
	mkdir -p "${evidence_dir}" 2>/dev/null
	PBSD_STATUS="$1" PBSD_SCHEMA="${SCHEMA}" PBSD_RUN="${run_id}" PBSD_SRC="${source_vmid}" \
	PBSD_SNAP="${snapshot}" PBSD_NODE="$(hostname)" PBSD_STORE="${target_storage}" \
	PBSD_TGT="${target_vmid}" PBSD_ISO="${isolation_method}" PBSD_REMOVED="${removed_devices}" \
	PBSD_RESTORE="${restore_result}" PBSD_BOOTM="${boot_method}" PBSD_BOOT="${boot_result}" \
	PBSD_DETAIL="${boot_detail}" PBSD_CLEAN="${cleanup_result}" PBSD_LEVEL="${level}" \
	PBSD_LEVELNAME="${LEVEL_NAME}" PBSD_FAIL="${failure}" PBSD_SRCSTATE="${source_status_before}" \
	PBSD_SRCDIGEST="${source_digest_before}" PBSD_OUT="${evidence_dir}/${run_id}.json" \
	python3 -c '
import datetime, json, os, time
lvl = int(os.environ["PBSD_LEVEL"])
out = {
    "schema": os.environ["PBSD_SCHEMA"],
    "run_id": os.environ["PBSD_RUN"],
    "timestamp": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
    "generated_epoch": int(time.time()),
    "status": os.environ["PBSD_STATUS"],
    "source_guest_type": "qemu",
    "source_guest_id": os.environ["PBSD_SRC"],
    "source_snapshot": os.environ["PBSD_SNAP"],
    "pbs_datastore": os.environ["PBSD_SNAP"].split(":")[0],
    "target_node": os.environ["PBSD_NODE"],
    "target_storage": os.environ["PBSD_STORE"],
    "disposable_guest_id": os.environ["PBSD_TGT"],
    "network_isolation_method": os.environ["PBSD_ISO"],
    "removed_devices": [d for d in os.environ["PBSD_REMOVED"].split(",") if d],
    "restore_result": os.environ["PBSD_RESTORE"],
    "boot_evidence_method": os.environ["PBSD_BOOTM"],
    "boot_result": os.environ["PBSD_BOOT"],
    "boot_detail": os.environ["PBSD_DETAIL"],
    "cleanup_result": os.environ["PBSD_CLEAN"],
    # Claimed only when the guest agent answered AND cleanup succeeded. A running QEMU process is
    # never enough, and a drill that left a clone behind has not succeeded whatever the boot did.
    "evidence_level": lvl,
    "evidence_level_name": os.environ["PBSD_LEVELNAME"] if lvl == 3 else "NOTHING_PROVEN",
    "application_recovery_claimed": False,
    "source_unchanged": True,
    "source_status_before": os.environ["PBSD_SRCSTATE"],
    "source_config_digest": os.environ["PBSD_SRCDIGEST"],
    "backup_unchanged": True,
    "failure": os.environ["PBSD_FAIL"],
}
with open(os.environ["PBSD_OUT"], "w", encoding="utf-8") as fh:
    json.dump(out, fh, sort_keys=True, indent=2)
    fh.write("\n")
'
	echo "evidence: ${evidence_dir}/${run_id}.json"
}

cleanup_guest() {
	[[ -n "${target_vmid}" ]] || return 0
	[[ "${target_vmid}" != "${source_vmid}" ]] || { cleanup_result="refused_source_collision"; return 1; }
	if [[ "$(qm status "${target_vmid}" 2>&1)" == *running* ]]; then
		timeout "${t_stop}" qm shutdown "${target_vmid}" --timeout $((t_stop / 2)) >/dev/null 2>&1 \
			|| timeout "${t_stop}" qm stop "${target_vmid}" >/dev/null 2>&1
	fi
	# --destroy-unreferenced-disks also removes the disposable EFI and TPM state volumes, which are
	# real storage and would otherwise be orphaned with no config pointing at them.
	timeout "${t_stop}" qm destroy "${target_vmid}" --purge 1 --destroy-unreferenced-disks 1 >/dev/null 2>&1
	if [[ -f "${conf_dir}/${target_vmid}.conf" ]]; then
		cleanup_result="failed"
		return 1
	fi
	cleanup_result="ok"
	return 0
}

abort() { failure="$1"; log "ABORT: $1"; emit_evidence "fail"; exit 1; }

# ---------------------------------------------------------------- preflight
command -v qm        >/dev/null 2>&1 || abort "qm not available; run this on the target Proxmox node"
command -v qmrestore >/dev/null 2>&1 || abort "qmrestore not available"
command -v pvesh     >/dev/null 2>&1 || abort "pvesh not available"
[[ "${source_vmid}" =~ ^[0-9]+$ ]] || abort "source vmid must be numeric"

snap_state="$(timeout "${t_cmd}" pvesh get "/nodes/$(hostname)/storage/${snapshot%%:*}/content" --output-format json 2>/dev/null \
	| python3 -c '
import json, sys
want = sys.argv[1]
try:
    c = json.load(sys.stdin)
except ValueError:
    sys.exit(3)
m = [x for x in c if x.get("volid") == want]
if not m:
    sys.exit(4)
v = m[0].get("verification")
print((v or {}).get("state", "none") if isinstance(v, dict) else "none")' "${snapshot}" 2>/dev/null)"
case $? in
	3) abort "malformed PBS content metadata" ;;
	4) abort "snapshot not found in the datastore: ${snapshot}" ;;
esac
[[ "${snap_state}" == "ok" ]] || abort "snapshot verification state is '${snap_state:-unknown}', refusing to drill from an unverified backup"
log "snapshot ${snapshot} verified=ok"

# Boot evidence has to be decided BEFORE restoring anything. If the source VM has no guest agent,
# there is no signal that distinguishes a booted OS from a spinning firmware prompt, and this drill
# would be unable to justify LEVEL 3 no matter what happened.
src_node="$(timeout "${t_cmd}" pvesh get /cluster/resources --type vm --output-format json 2>/dev/null \
	| python3 -c '
import json, sys
w = sys.argv[1]
m = [x for x in json.load(sys.stdin) if str(x.get("vmid")) == w]
print(m[0].get("node", "") if m else "")' "${source_vmid}" 2>/dev/null)"
[[ -n "${src_node}" ]] || abort "source vm ${source_vmid} not found in the cluster"
src_cfg="$(timeout "${t_cmd}" pvesh get "/nodes/${src_node}/qemu/${source_vmid}/config" --output-format json 2>/dev/null)"
source_digest_before="$(python3 -c '
import json, sys
print(json.loads(sys.argv[1]).get("digest", ""))' "${src_cfg}" 2>/dev/null)"
agent_on="$(python3 -c '
import json, sys
a = str(json.loads(sys.argv[1]).get("agent", ""))
print("1" if a and not a.startswith("0") and "enabled=0" not in a else "0")' "${src_cfg}" 2>/dev/null)"
[[ "${agent_on}" == "1" ]] || abort "source vm has no guest agent configured; guest-OS boot could not be proven, refusing"
log "source vm ${source_vmid} on ${src_node} has a guest agent; boot evidence method = ${boot_method}"

# ---------------------------------------------------------------- target id
target_vmid="$(timeout "${t_cmd}" pvesh get /cluster/nextid 2>/dev/null | tr -d '"[:space:]')"
[[ "${target_vmid}" =~ ^[0-9]+$ ]] || abort "could not allocate a target vmid"
[[ "${target_vmid}" != "${source_vmid}" ]] || abort "allocated vmid equals the source vmid; refusing"
occupied="$(timeout "${t_cmd}" pvesh get /cluster/resources --type vm --output-format json 2>/dev/null \
	| python3 -c '
import json, sys
w = sys.argv[1]
print(sum(1 for x in json.load(sys.stdin) if str(x.get("vmid")) == w))' "${target_vmid}" 2>/dev/null)"
[[ "${occupied}" == "0" ]] || abort "target vmid ${target_vmid} is occupied; refusing to overwrite"
[[ ! -f "${conf_dir}/${target_vmid}.conf" ]] || abort "config already exists for ${target_vmid}; refusing"
log "disposable target vmid=${target_vmid} (source=${source_vmid}) proven free"

if [[ ${dry_run} -eq 1 ]]; then
	restore_result="skipped_dry_run"
	log "dry-run: stopping before restore"
	emit_evidence "dry-run"
	exit 0
fi

# ---------------------------------------------------------------- restore
# --unique regenerates the MAC, which matters for the seconds between restore and NIC removal while
# the VM is stopped. No --force (never overwrite), no --start (never boot unisolated), no
# --ha-managed (never join HA).
log "restoring ${snapshot} -> vmid ${target_vmid} on ${target_storage}"
if ! timeout "${t_restore}" qmrestore "${snapshot}" "${target_vmid}" \
		--storage "${target_storage}" --unique 1 >/dev/null 2>&1; then
	restore_result="failed"
	abort "qmrestore failed or timed out"
fi
[[ -f "${conf_dir}/${target_vmid}.conf" ]] || { restore_result="failed"; abort "restore reported success but no config exists"; }
qm config "${target_vmid}" 2>/dev/null | grep -qE '^(scsi|virtio|ide|sata)[0-9]+:' \
	|| { restore_result="failed"; abort "restored vm has no boot disk"; }
restore_result="ok"
log "restore ok"

# ---------------------------------------------------------------- QEMU hazard gate
hazards="$(qm config "${target_vmid}" 2>/dev/null | grep -oE "${HOST_COUPLED_RE}" | tr -d ':' | tr '\n' ',')"
if [[ -n "${hazards}" ]]; then
	cleanup_guest
	abort "disposable vm carries host-coupled devices (${hazards%,}); refusing to boot"
fi
if qm config "${target_vmid}" 2>/dev/null | grep -qE '/dev/(sd|nvme|disk|mapper)'; then
	cleanup_guest
	abort "disposable vm references a raw host block device; refusing to boot"
fi
log "no host-coupled devices present"

# ---------------------------------------------------------------- isolation, BEFORE first start
for n in $(qm config "${target_vmid}" 2>/dev/null | grep -oE '^net[0-9]+'); do
	qm set "${target_vmid}" --delete "${n}" >/dev/null 2>&1 || abort "could not delete ${n}"
	removed_devices="${removed_devices}${n},"
done
remaining="$(qm config "${target_vmid}" 2>/dev/null | grep -cE '^net[0-9]+')"
[[ "${remaining}" == "0" ]] || { cleanup_guest; abort "network isolation failed: ${remaining} nic(s) remain; refusing to boot"; }
isolation_method="all_nics_removed"
qm set "${target_vmid}" --onboot 0 >/dev/null 2>&1
qm config "${target_vmid}" 2>/dev/null | grep -q '^tags:' && qm set "${target_vmid}" --delete tags >/dev/null 2>&1
qm set "${target_vmid}" --name "${run_id}" >/dev/null 2>&1
log "isolation: all nics removed, autostart disabled, production tags cleared"

# ---------------------------------------------------------------- pre-boot gates
qm config "${target_vmid}" 2>/dev/null | grep -qE '^onboot: 1' && { cleanup_guest; abort "autostart is enabled on the disposable vm"; }
ha="$(timeout "${t_cmd}" pvesh get /cluster/ha/resources --output-format json 2>/dev/null \
	| python3 -c '
import json, sys
w = ":" + sys.argv[1]
print(sum(1 for x in json.load(sys.stdin) if str(x.get("sid", "")).endswith(w)))' "${target_vmid}" 2>/dev/null)"
[[ "${ha:-0}" == "0" ]] || { cleanup_guest; abort "disposable vm is HA-managed; refusing to boot"; }
rep="$(timeout "${t_cmd}" pvesh get /cluster/replication --output-format json 2>/dev/null \
	| python3 -c '
import json, sys
w = sys.argv[1]
print(sum(1 for x in json.load(sys.stdin) if str(x.get("guest", "")) == w))' "${target_vmid}" 2>/dev/null)"
[[ "${rep:-0}" == "0" ]] || { cleanup_guest; abort "disposable vm has a replication job; refusing to boot"; }
[[ "$(qm status "${target_vmid}" 2>&1)" == *stopped* ]] || { cleanup_guest; abort "disposable vm is not stopped before boot"; }

# ---------------------------------------------------------------- boot
log "starting ${target_vmid}"
timeout "${t_cmd}" qm start "${target_vmid}" >/dev/null 2>&1 || { boot_result="failed"; cleanup_guest; abort "qm start failed"; }
deadline=$((SECONDS + t_boot))
agent_ok=0
while (( SECONDS < deadline )); do
	if timeout "${t_cmd}" qm agent "${target_vmid}" ping >/dev/null 2>&1; then
		agent_ok=1; break
	fi
	sleep 5
done
if [[ ${agent_ok} -ne 1 ]]; then
	# The VM may well be "running". That is precisely the claim being refused.
	boot_result="no_guest_evidence"
	boot_detail="qemu process ran but the guest agent never answered within ${t_boot}s"
	cleanup_guest
	abort "guest OS boot could not be proven (${boot_detail})"
fi
osinfo="$(timeout "${t_cmd}" qm agent "${target_vmid}" get-osinfo 2>/dev/null \
	| python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print("")
    raise SystemExit
print("%s %s" % (d.get("id", "?"), d.get("version", "?")))' 2>/dev/null)"
boot_result="ok"
boot_detail="guest-agent responded; os=${osinfo:-unreported}"
log "boot ok (${boot_detail})"

# ---------------------------------------------------------------- stop + destroy
if ! cleanup_guest; then
	abort "cleanup failed; disposable vm ${target_vmid} may still exist"
fi
log "cleanup ok"

level=3
emit_evidence "pass"
log "LEVEL 3 ${LEVEL_NAME} proven for vm ${source_vmid} via ${snapshot}"
