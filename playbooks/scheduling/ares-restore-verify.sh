#!/usr/bin/env bash
# Monthly restore-verify drill: proves the Ares -> Randy restic backup actually restores.
#
# WHY THIS WAS REWRITTEN. The previous version ran untracked from ~/.local/bin, sent every restic
# stderr to /dev/null, and logged one of five fixed strings. On 2026-09-01 it recorded
# "FAIL: restic check (repo integrity)" and stopped there for a month. The real cause was a stale
# lock left by a restic process that the 2026-08-19 reboot killed: `restic check` needs an exclusive
# lock, backups only need a shared one, so nightly backups kept succeeding while the drill was dead.
# The repository was never damaged. But the log said "repo integrity", which reads like corruption,
# and there was no captured error, no snapshot id, and no evidence file to check. A drill whose
# failure output cannot distinguish "a lock file is in the way" from "your backups are corrupt" is
# worse than no drill, because it will eventually be believed.
#
# WHAT IT PROVES, precisely, and no more:
#   LEVEL 1  the repository passes restic's own integrity check (metadata, indexes, blob structure)
#   LEVEL 2  a named file extracts from an identified snapshot to a disposable directory, non-empty
# It does NOT boot anything, does NOT restore a VM or CT, and does NOT touch any production path.
# The evidence file records the level actually reached, so nobody has to infer it from an exit code.
#
# NON-DESTRUCTIVE. Reads the repository; restores only into a fresh mktemp directory that it then
# removes. It never prunes, never forgets, never writes into $HOME, and the only repository mutation
# it can make is removing a STALE lock, which is restic's own documented recovery and deletes no data.
set -uo pipefail

RESTIC_REPOSITORY="${RESTIC_REPOSITORY:-sftp:randy:/mnt/bulk/backups/ares}"
RESTIC_PASSWORD_FILE="${RESTIC_PASSWORD_FILE:-${HOME}/.config/restic/ares-randy.pass}"
export RESTIC_REPOSITORY RESTIC_PASSWORD_FILE

log_file="${ARES_RESTORE_VERIFY_LOG:-${HOME}/.local/state/ares-restore-verify.log}"
evidence="${ARES_RESTORE_VERIFY_EVIDENCE:-${HOME}/.local/state/ares-restore-verify.json}"
probe="${ARES_RESTORE_VERIFY_PROBE:-${HOME}/.bashrc}"
# Bounded. The previous version had no timeout anywhere, so a hung sftp session would have held the
# drill open indefinitely and reported nothing at all.
t_check="${ARES_RESTORE_VERIFY_CHECK_TIMEOUT:-3600}"
t_short="${ARES_RESTORE_VERIFY_SHORT_TIMEOUT:-300}"

mkdir -p "$(dirname "${log_file}")" "$(dirname "${evidence}")"
dest="$(mktemp -d "${TMPDIR:-/tmp}/restic-verify.XXXXXX")" || exit 1

level=0
snapshot=""
unlocked="false"
restored_bytes=0
restored_sha=""
probe_match="unknown"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
iso() { date -Is; }

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Publication is deliberately NON-FATAL to the restore verdict. Whether Randy received the evidence
# is a different fact from whether the restore worked, and collapsing them would let a network
# problem be reported as a backup problem. A publication failure is logged; monitoring sees the
# consequence as a missing or stale report, which is exactly what it is.
publish_evidence() {
	[[ "${ARES_RESTORE_VERIFY_PUBLISH:-1}" == "1" ]] || return 0
	"${here}/publish-restore-evidence.sh" >/dev/null 2>&1 \
		|| echo "$(ts) PUBLISH: FAILED (restore verdict unaffected)" >> "${log_file}"
	return 0
}

write_evidence() { # status class detail
	# Built by python3 rather than printf. `detail` carries captured restic stderr, which can contain
	# quotes, backslashes and newlines; hand-assembled JSON would emit a broken document exactly when
	# something has gone wrong and the evidence matters most.
	ARV_STATUS="$1" ARV_CLASS="$2" ARV_DETAIL="$3" ARV_LEVEL="${level}" \
	ARV_LEVEL_NAME="$(level_name)" ARV_SNAPSHOT="${snapshot}" ARV_UNLOCKED="${unlocked}" \
	ARV_PROBE="${probe}" ARV_BYTES="${restored_bytes}" ARV_SHA="${restored_sha}" \
	ARV_MATCH="${probe_match}" ARV_REPO="${RESTIC_REPOSITORY}" ARV_OUT="${evidence}" \
	python3 -c '
import datetime, json, os, time
out = {
    "schema": "netframe.ares-restore-verify/1",
    "generated": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
    "generated_epoch": int(time.time()),
    "status": os.environ["ARV_STATUS"],
    "failure_class": os.environ["ARV_CLASS"],
    "detail": os.environ["ARV_DETAIL"],
    "level": int(os.environ["ARV_LEVEL"]),
    "level_name": os.environ["ARV_LEVEL_NAME"],
    "snapshot": os.environ["ARV_SNAPSHOT"],
    "stale_lock_recovered": os.environ["ARV_UNLOCKED"] == "true",
    "probe_path": os.environ["ARV_PROBE"],
    "restored_bytes": int(os.environ["ARV_BYTES"] or 0),
    "restored_sha256": os.environ["ARV_SHA"],
    "matches_live_probe": os.environ["ARV_MATCH"],
    "repository": os.environ["ARV_REPO"],
}
with open(os.environ["ARV_OUT"], "w", encoding="utf-8") as fh:
    json.dump(out, fh, sort_keys=True)
    fh.write("\n")
'
}

level_name() {
	case "${level}" in
		0) echo "NOTHING_PROVEN" ;;
		1) echo "BACKUP_VERIFIED" ;;
		2) echo "RESTORE_EXTRACTED" ;;
		*) echo "UNKNOWN" ;;
	esac
}

cleanup_dest() {
	rm -rf "${dest}" 2>/dev/null
	[[ ! -e "${dest}" ]]
}

fail() { # class detail
	# Cleanup is part of the claim: a drill that leaves restored data behind is a drill that fills a
	# disk. If cleanup itself fails, say so rather than reporting only the original problem.
	if ! cleanup_dest; then
		write_evidence "fail" "CLEANUP_FAILED" "$2 (and the restore directory could not be removed)"
		echo "$(ts) FAIL[CLEANUP_FAILED]: $2 (and ${dest} could not be removed)" >> "${log_file}"
		publish_evidence
		exit 1
	fi
	write_evidence "fail" "$1" "$2"
	echo "$(ts) FAIL[$1]: $2" >> "${log_file}"
	# A failed drill must reach the monitor as a fresh explicit FAIL. Left unpublished it would
	# instead age into "stale", which reads as "nobody ran it" rather than "it ran and it failed".
	publish_evidence
	exit 1
}

# ---------------------------------------------------------------- preflight
command -v restic >/dev/null 2>&1 || fail "MISSING_DEPENDENCY" "restic is not on PATH"
[[ -r "${RESTIC_PASSWORD_FILE}" ]] || fail "MISSING_DEPENDENCY" "no readable restic password file"

# ---------------------------------------------------------------- LEVEL 1: repository integrity
# Stderr is CAPTURED, not discarded. This is the whole reason the previous failure was unreadable.
check_err="$(timeout "${t_check}" restic check 2>&1 >/dev/null)"
rc=$?
if [[ ${rc} -ne 0 ]]; then
	if [[ ${rc} -eq 124 ]]; then
		fail "TIMEOUT" "restic check exceeded ${t_check}s"
	fi
	# A stale lock is a normal, self-inflicted, documented condition: restic's own advice is to run
	# `unlock`. It is NOT evidence about the data, so it must never be reported as an integrity
	# failure. `restic unlock` without --remove-all removes only locks whose owner is gone.
	if grep -qi "already locked\|unable to create lock" <<<"${check_err}"; then
		if ! timeout "${t_short}" restic unlock >/dev/null 2>&1; then
			fail "REPOSITORY_LOCKED" "repository is locked and stale locks could not be removed"
		fi
		unlocked="true"
		check_err="$(timeout "${t_check}" restic check 2>&1 >/dev/null)"
		rc=$?
		if [[ ${rc} -ne 0 ]]; then
			fail "INTEGRITY_FAILED" "restic check still failed after clearing stale locks: $(head -c 300 <<<"${check_err}" | tr -d '\n')"
		fi
	else
		fail "INTEGRITY_FAILED" "restic check failed: $(head -c 300 <<<"${check_err}" | tr -d '\n')"
	fi
fi
level=1

# ---------------------------------------------------------------- identify the snapshot
# The old drill restored "latest" and recorded nothing, so its evidence named no snapshot and could
# not be audited afterwards. Resolve the id first, then restore THAT id.
snap_json="$(timeout "${t_short}" restic snapshots --latest 1 --json 2>/dev/null)"
[[ -n "${snap_json}" ]] || fail "BACKUP_UNAVAILABLE" "restic snapshots returned nothing"
snapshot="$(python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except ValueError:
    sys.exit(3)
if not isinstance(d, list) or not d:
    sys.exit(4)
sid = d[0].get("short_id") or d[0].get("id") or ""
if not sid:
    sys.exit(5)
print(sid)' <<<"${snap_json}" 2>/dev/null)"
case $? in
	3) fail "MALFORMED_OUTPUT" "restic snapshots did not return valid JSON" ;;
	4) fail "BACKUP_UNAVAILABLE" "no snapshots exist in the repository" ;;
	5) fail "MALFORMED_OUTPUT" "snapshot record carries no id" ;;
esac
[[ -n "${snapshot}" ]] || fail "MALFORMED_OUTPUT" "could not resolve a snapshot id"

# ---------------------------------------------------------------- LEVEL 2: extract from that snapshot
if ! timeout "${t_short}" restic restore "${snapshot}" --target "${dest}" \
		--include "${probe}" >/dev/null 2>&1; then
	fail "RESTORE_FAILED" "restore of ${probe} from snapshot ${snapshot} failed"
fi
restored="${dest}${probe}"
[[ -s "${restored}" ]] || fail "RESTORE_FAILED" "restored file ${probe} is missing or empty"
restored_bytes="$(wc -c <"${restored}" | tr -d ' ')"
restored_sha="$(sha256sum "${restored}" | cut -d' ' -f1)"
level=2

# Informational only. The live file is allowed to have changed since the snapshot was taken, so a
# difference is not a failure; recording it lets an operator see whether the restore is current.
if [[ -r "${probe}" ]]; then
	if [[ "$(sha256sum "${probe}" | cut -d' ' -f1)" == "${restored_sha}" ]]; then
		probe_match="identical"
	else
		probe_match="differs_from_live"
	fi
else
	probe_match="live_absent"
fi

cleanup_dest || fail "CLEANUP_FAILED" "restore directory ${dest} could not be removed"

write_evidence "pass" "" ""
echo "$(ts) OK: LEVEL 2 RESTORE_EXTRACTED snapshot=${snapshot} bytes=${restored_bytes} probe=${probe_match} stale_lock_recovered=${unlocked}" >> "${log_file}"
publish_evidence
