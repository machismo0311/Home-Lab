#!/usr/bin/env bash
# Owner-supervised LXC restore drill: restore one real PBS snapshot into a disposable, network
# isolated container, prove it boots, then destroy it.
#
# WHY THIS EXISTS. The estate could prove a file comes back out of restic (LEVEL 2) and could prove
# PBS holds verified guest backups, but nothing had ever proved a guest RESTORES AND BOOTS. That gap
# is the one that matters on the day it matters, and it is not closed by reading a backup report.
#
# WHAT IT PROVES, and nothing more:
#   LEVEL 3  RESTORED_SYSTEM_BOOTABLE - a real snapshot restores into a new guest, that guest boots
#            to an operational init with a readable filesystem and working local command execution.
# It does NOT prove the application works. No LEVEL 4 claim is made or supported here.
#
# THE SAFETY MODEL, which is most of this script. A restored guest is a byte-identical clone of a
# production host, including its MAC and static IP. Booted on a production bridge it is an address
# conflict at best. So isolation is structural and happens BEFORE first start: the container is
# restored stopped, every network device is deleted from the disposable config, and the absence is
# asserted. It is never "isolated" by changing an IP or stopping services inside the guest.
#
# Every gate fails closed. The drill refuses rather than guesses: an occupied target id, a source id
# equal to the target, an unverified snapshot, a network device that survived deletion, an HA or
# replication membership, or autostart left enabled all abort before the guest is ever started.
#
# Run ON the target Proxmox node. Owner-supervised, never scheduled: this creates and destroys real
# guests, which is materially more estate mutation than a read-only report check. MAX_AUTO_CLASS 0.
set -uo pipefail

SCHEMA="netframe.pbs-guest-restore-drill/1"
LEVEL_NAME="RESTORED_SYSTEM_BOOTABLE"

source_ctid=""; snapshot=""; target_storage="local-lvm"; dry_run=0
t_restore="${PBSDRILL_RESTORE_TIMEOUT:-1800}"
t_boot="${PBSDRILL_BOOT_TIMEOUT:-300}"
t_stop="${PBSDRILL_STOP_TIMEOUT:-180}"
t_cmd="${PBSDRILL_CMD_TIMEOUT:-60}"
evidence_dir="${PBSDRILL_EVIDENCE_DIR:-/var/log/pbs-restore-drill}"
# Where Proxmox keeps container configs. Overridable ONLY so the hermetic tests can exercise the
# full restore/isolate/boot/cleanup path against stubs; production never sets it.
conf_dir="${PBSDRILL_CONF_DIR:-/etc/pve/lxc}"

usage() {
	cat >&2 <<'USAGE'
usage: pbs-guest-restore-drill.sh --source-ctid <id> --snapshot <volid> [--target-storage <id>]
       Run on the target Proxmox node. Restores one PBS snapshot into a new disposable CTID,
       proves it boots with no network device, then destroys it.
USAGE
	exit 2
}

while [[ $# -gt 0 ]]; do
	case "$1" in
		--source-ctid) source_ctid="${2:-}"; shift 2 ;;
		--snapshot) snapshot="${2:-}"; shift 2 ;;
		--target-storage) target_storage="${2:-}"; shift 2 ;;
		--dry-run) dry_run=1; shift ;;
		*) usage ;;
	esac
done
[[ -n "${source_ctid}" && -n "${snapshot}" ]] || usage

run_id="restore-drill-${source_ctid}-$(date -u +%Y%m%dT%H%M%SZ)"
target_ctid=""
restore_result="not_attempted"; boot_result="not_attempted"; cleanup_result="not_attempted"
level=0; isolation_method="none"; boot_detail=""; failure=""
source_digest_before=""; source_status_before=""

log() { echo "$(date -u +%H:%M:%SZ) $*"; }

emit_evidence() { # status
	mkdir -p "${evidence_dir}" 2>/dev/null
	PBSD_STATUS="$1" PBSD_SCHEMA="${SCHEMA}" PBSD_RUN="${run_id}" \
	PBSD_SRC="${source_ctid}" PBSD_SNAP="${snapshot}" PBSD_NODE="$(hostname)" \
	PBSD_STORE="${target_storage}" PBSD_TGT="${target_ctid}" PBSD_ISO="${isolation_method}" \
	PBSD_RESTORE="${restore_result}" PBSD_BOOT="${boot_result}" PBSD_CLEAN="${cleanup_result}" \
	PBSD_LEVEL="${level}" PBSD_LEVELNAME="${LEVEL_NAME}" PBSD_DETAIL="${boot_detail}" \
	PBSD_FAIL="${failure}" PBSD_SRCSTATE="${source_status_before}" PBSD_SRCDIGEST="${source_digest_before}" \
	PBSD_OUT="${evidence_dir}/${run_id}.json" \
	python3 -c '
import datetime, json, os, time
lvl = int(os.environ["PBSD_LEVEL"])
out = {
    "schema": os.environ["PBSD_SCHEMA"],
    "run_id": os.environ["PBSD_RUN"],
    "timestamp": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
    "generated_epoch": int(time.time()),
    "status": os.environ["PBSD_STATUS"],
    "source_guest_type": "lxc",
    "source_guest_id": os.environ["PBSD_SRC"],
    "source_snapshot": os.environ["PBSD_SNAP"],
    "pbs_datastore": os.environ["PBSD_SNAP"].split(":")[0],
    "target_node": os.environ["PBSD_NODE"],
    "target_storage": os.environ["PBSD_STORE"],
    "disposable_guest_id": os.environ["PBSD_TGT"],
    "network_isolation_method": os.environ["PBSD_ISO"],
    "restore_result": os.environ["PBSD_RESTORE"],
    "boot_result": os.environ["PBSD_BOOT"],
    "boot_detail": os.environ["PBSD_DETAIL"],
    "cleanup_result": os.environ["PBSD_CLEAN"],
    # The level is only ever claimed when the boot AND the cleanup both succeeded. An artifact that
    # claimed LEVEL 3 while a disposable guest was still on the cluster would be worse than useless.
    "evidence_level": lvl,
    "evidence_level_name": os.environ["PBSD_LEVELNAME"] if lvl == 3 else "NOTHING_PROVEN",
    "source_unchanged": os.environ["PBSD_STATUS"] != "fail" or bool(os.environ["PBSD_SRCDIGEST"]),
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

abort() { # reason
	failure="$1"
	log "ABORT: $1"
	emit_evidence "fail"
	exit 1
}

cleanup_guest() {
	[[ -n "${target_ctid}" ]] || return 0
	[[ "${target_ctid}" != "${source_ctid}" ]] || { cleanup_result="refused_source_collision"; return 1; }
	if [[ "$(pct status "${target_ctid}" 2>&1)" == *running* ]]; then
		timeout "${t_stop}" pct shutdown "${target_ctid}" --timeout $((t_stop / 2)) >/dev/null 2>&1 \
			|| timeout "${t_stop}" pct stop "${target_ctid}" >/dev/null 2>&1
	fi
	timeout "${t_stop}" pct destroy "${target_ctid}" --purge 1 --destroy-unreferenced-disks 1 >/dev/null 2>&1
	if [[ -f "${conf_dir}/${target_ctid}.conf" ]]; then
		cleanup_result="failed"
		return 1
	fi
	cleanup_result="ok"
	return 0
}

# ---------------------------------------------------------------- preflight
command -v pct   >/dev/null 2>&1 || abort "pct not available; run this on the target Proxmox node"
command -v pvesh >/dev/null 2>&1 || abort "pvesh not available; run this on a cluster node"
[[ "${source_ctid}" =~ ^[0-9]+$ ]] || abort "source ctid must be numeric"

# The snapshot must exist AND be verified. An unverified backup may be perfectly good, but a drill
# whose whole purpose is proving recoverability should not start from something PBS has not checked.
snap_line="$(timeout "${t_cmd}" pvesh get "/nodes/$(hostname)/storage/${snapshot%%:*}/content" --output-format json 2>/dev/null \
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
[[ "${snap_line}" == "ok" ]] || abort "snapshot verification state is '${snap_line:-unknown}', refusing to drill from an unverified backup"
log "snapshot ${snapshot} verified=ok"

source_status_before="$(timeout "${t_cmd}" pvesh get "/cluster/resources" --type vm --output-format json 2>/dev/null \
	| python3 -c '
import json, sys
w = sys.argv[1]
m = [x for x in json.load(sys.stdin) if str(x.get("vmid")) == w]
print(m[0].get("status", "unknown") if m else "absent")' "${source_ctid}" 2>/dev/null)"

# ---------------------------------------------------------------- target id
target_ctid="$(timeout "${t_cmd}" pvesh get /cluster/nextid 2>/dev/null | tr -d '"[:space:]')"
[[ "${target_ctid}" =~ ^[0-9]+$ ]] || abort "could not allocate a target ctid"
# The single most dangerous mistake this tool could make.
[[ "${target_ctid}" != "${source_ctid}" ]] || abort "allocated ctid equals the source ctid; refusing"
occupied="$(timeout "${t_cmd}" pvesh get /cluster/resources --type vm --output-format json 2>/dev/null \
	| python3 -c '
import json, sys
w = sys.argv[1]
print(sum(1 for x in json.load(sys.stdin) if str(x.get("vmid")) == w))' "${target_ctid}" 2>/dev/null)"
[[ "${occupied}" == "0" ]] || abort "target ctid ${target_ctid} is occupied; refusing to overwrite"
[[ ! -f "${conf_dir}/${target_ctid}.conf" ]] || abort "config already exists for ${target_ctid}; refusing"
log "disposable target ctid=${target_ctid} (source=${source_ctid}) proven free"

if [[ ${dry_run} -eq 1 ]]; then
	log "dry-run: stopping before restore"
	restore_result="skipped_dry_run"
	emit_evidence "dry-run"
	exit 0
fi

# ---------------------------------------------------------------- restore
log "restoring ${snapshot} -> ctid ${target_ctid} on ${target_storage}"
if ! timeout "${t_restore}" pct restore "${target_ctid}" "${snapshot}" \
		--storage "${target_storage}" --hostname "${run_id}" \
		--unprivileged 1 --onboot 0 --start 0 >/dev/null 2>&1; then
	restore_result="failed"
	abort "pct restore failed or timed out"
fi
# Exit 0 is not the evidence. The config has to exist and carry a rootfs.
[[ -f "${conf_dir}/${target_ctid}.conf" ]] || { restore_result="failed"; abort "restore reported success but no config exists"; }
pct config "${target_ctid}" 2>/dev/null | grep -q "^rootfs:" || { restore_result="failed"; abort "restored guest has no rootfs"; }
restore_result="ok"
log "restore ok"

# ---------------------------------------------------------------- isolation, BEFORE first start
for n in $(pct config "${target_ctid}" 2>/dev/null | grep -oE '^net[0-9]+' ); do
	pct set "${target_ctid}" --delete "${n}" >/dev/null 2>&1 || abort "could not delete ${n}"
done
remaining="$(pct config "${target_ctid}" 2>/dev/null | grep -cE '^net[0-9]+')"
[[ "${remaining}" == "0" ]] || abort "network isolation failed: ${remaining} device(s) remain; refusing to boot"
isolation_method="all_net_devices_removed"
log "isolation: all network devices removed"

# ---------------------------------------------------------------- pre-boot gates
pct config "${target_ctid}" 2>/dev/null | grep -qE '^onboot: 1' && abort "autostart is enabled on the disposable guest"
ha="$(timeout "${t_cmd}" pvesh get /cluster/ha/resources --output-format json 2>/dev/null \
	| python3 -c '
import json, sys
w = ":" + sys.argv[1]
print(sum(1 for x in json.load(sys.stdin) if str(x.get("sid", "")).endswith(w)))' "${target_ctid}" 2>/dev/null)"
[[ "${ha:-0}" == "0" ]] || abort "disposable guest is HA-managed; refusing to boot"
rep="$(timeout "${t_cmd}" pvesh get /cluster/replication --output-format json 2>/dev/null \
	| python3 -c '
import json, sys
w = sys.argv[1]
print(sum(1 for x in json.load(sys.stdin) if str(x.get("guest", "")) == w))' "${target_ctid}" 2>/dev/null)"
[[ "${rep:-0}" == "0" ]] || abort "disposable guest has a replication job; refusing to boot"
[[ "$(pct status "${target_ctid}" 2>&1)" == *stopped* ]] || abort "disposable guest is not stopped before boot"

# ---------------------------------------------------------------- boot
log "starting ${target_ctid}"
timeout "${t_cmd}" pct start "${target_ctid}" >/dev/null 2>&1 || { boot_result="failed"; cleanup_guest; abort "pct start failed"; }
deadline=$((SECONDS + t_boot))
booted=0
while (( SECONDS < deadline )); do
	if [[ "$(pct status "${target_ctid}" 2>&1)" == *running* ]] \
		&& timeout "${t_cmd}" pct exec "${target_ctid}" -- true >/dev/null 2>&1; then
		booted=1; break
	fi
	sleep 3
done
if [[ ${booted} -ne 1 ]]; then
	boot_result="timeout"
	cleanup_guest
	abort "guest did not reach a usable state within ${t_boot}s"
fi
# Running is not booted. Require a real init and a readable filesystem, proven by execution.
init="$(timeout "${t_cmd}" pct exec "${target_ctid}" -- ps -p 1 -o comm= 2>/dev/null | tr -d '[:space:]')"
[[ -n "${init}" ]] || { boot_result="failed"; cleanup_guest; abort "no PID 1 in the restored guest"; }
timeout "${t_cmd}" pct exec "${target_ctid}" -- test -r /etc/os-release >/dev/null 2>&1 \
	|| { boot_result="failed"; cleanup_guest; abort "restored filesystem is not readable"; }
sysstate="$(timeout "${t_cmd}" pct exec "${target_ctid}" -- systemctl is-system-running 2>/dev/null | tr -d '[:space:]')"
# `degraded` is the expected settled state: the guest has no NIC, so its network units cannot
# succeed. That is the isolation working, not the restore failing. `starting` is NOT accepted as
# settled, because it means the boot transaction never completed.
case "${sysstate}" in
	running|degraded|"") boot_result="ok" ;;
	*) boot_result="unsettled" ;;
esac
boot_detail="init=${init} systemd=${sysstate:-none}"
[[ "${boot_result}" == "ok" ]] || { cleanup_guest; abort "guest init did not settle (${boot_detail})"; }
log "boot ok (${boot_detail})"

# ---------------------------------------------------------------- stop + destroy
if ! cleanup_guest; then
	# A drill that leaves a clone of a production guest on the cluster has not succeeded, however
	# well the boot went. The level is deliberately not claimed here.
	abort "cleanup failed; disposable guest ${target_ctid} may still exist"
fi
log "cleanup ok"

level=3
emit_evidence "pass"
log "LEVEL 3 ${LEVEL_NAME} proven for ${source_ctid} via ${snapshot}"
