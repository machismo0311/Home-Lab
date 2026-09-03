#!/usr/bin/env bash
# Publish the Ares restore-verify evidence to Randy, where netframe_monitor reads it.
#
# WHY THIS IS SEPARATE FROM THE DRILL. Three facts must not be collapsed into one boolean:
#
#   RESTORE TEST RESULT      what ares-restore-verify actually proved
#   MONITORING DELIVERY      whether Randy received that evidence
#   MONITORING FRESHNESS     whether what Randy holds is recent enough
#
# A failed publication does not make a successful restore drill unsuccessful, and a successful
# publication does not make a failed drill acceptable. Keeping publication in its own script keeps
# that separation structural rather than a matter of discipline, and it means the CURRENT valid
# evidence can be published without re-running a real repository restore just to move a file.
#
# WHY THIS TRANSPORT. The same ansible copy already used by run-hardening-drift-check.sh for the
# same directory on the same host. The copy module stages to a temporary file and renames it into
# place, so a reader on Randy sees either the old complete document or the new complete document
# and never a half-written one. A plain `scp` or a redirect over ssh would write the destination in
# place, which is exactly the partial-read window this must not have.
#
# The source evidence file is NEVER rewritten, normalized or reformatted here. It is copied
# verbatim, and delivery is confirmed by comparing digests afterwards.
set -uo pipefail

evidence="${ARES_RESTORE_VERIFY_EVIDENCE:-${HOME}/.local/state/ares-restore-verify.json}"
log_file="${ARES_RESTORE_VERIFY_LOG:-${HOME}/.local/state/ares-restore-verify.log}"
dest="${ARES_RESTORE_PUBLISH_DEST:-/var/log/netframe-monitor/restore-verify.json}"
target="${ARES_RESTORE_PUBLISH_TARGET:-randy}"
# Absolute by default so systemd's PATH cannot change which ansible runs. Overridable only so the
# hermetic tests can supply a stub transport; the unit never sets it.
ansible_adhoc="${ARES_PUBLISH_ANSIBLE:-/home/machismo/.ansible-venv/bin/ansible}"
vault_pass="${ANSIBLE_VAULT_PASSWORD_FILE:-${HOME}/.config/ansible/vault-pass}"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
say() { echo "$(ts) PUBLISH: $1" >> "${log_file}"; echo "$1"; }

mkdir -p "$(dirname "${log_file}")"

[[ -f "${evidence}" ]] || { say "FAILED: no evidence file at ${evidence}"; exit 1; }

# Refuse to publish a document that is not complete and parseable. Publishing garbage would turn a
# local producer bug into a monitoring result that looks like an estate problem.
if ! python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "${evidence}" 2>/dev/null; then
	say "FAILED: local evidence is not valid JSON; refusing to publish"
	exit 1
fi

src_sha="$(sha256sum "${evidence}" | cut -d' ' -f1)"

args=(-b -m ansible.builtin.copy -a "src=${evidence} dest=${dest} mode=0644 owner=root group=root")
[[ -f "${vault_pass}" ]] && args+=(--vault-password-file "${vault_pass}")
if ! "${ansible_adhoc}" "${target}" "${args[@]}" >/dev/null 2>&1; then
	say "FAILED: could not copy evidence to ${target}:${dest}"
	exit 1
fi

# Confirm what actually landed. An exit code from the transport says the command ran; comparing the
# digest says the bytes arrived, complete and unaltered.
vargs=(-m ansible.builtin.command -a "sha256sum ${dest}")
[[ -f "${vault_pass}" ]] && vargs+=(--vault-password-file "${vault_pass}")
remote_out="$("${ansible_adhoc}" "${target}" "${vargs[@]}" 2>/dev/null)"
remote_sha="$(grep -oE '\b[0-9a-f]{64}\b' <<<"${remote_out}" | head -1)"

if [[ -z "${remote_sha}" ]]; then
	say "FAILED: could not read back ${target}:${dest} to confirm delivery"
	exit 1
fi
if [[ "${remote_sha}" != "${src_sha}" ]]; then
	say "FAILED: delivered copy does not match the source evidence (${remote_sha:0:12} != ${src_sha:0:12})"
	exit 1
fi

say "OK: evidence delivered to ${target}:${dest} (sha256 ${src_sha:0:12})"
