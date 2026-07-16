#!/usr/bin/env bash
# Daily hardening DRIFT CHECK, run from Ares (the control node).
#
# READ-ONLY by design: runs the hardening desired-state in --check mode and reports
# whether any node has drifted from the hardened baseline. It NEVER enforces or changes
# anything - detection only, so a surprising drift is surfaced for a human, not silently
# "corrected". (Enforcement stays a deliberate manual `ansible-playbook desired-state.yml`
# without --check.)
#
# Writes a world-readable JSON report to Randy at the same path the backup-verify report
# uses, so netframe_monitor ingests it the same way (a hardening_drift check) and drift
# shows on the dashboard instead of only in a log nobody reads.
#
# Installed as a user cron job on Ares (see README, Scheduling). Mirrors
# run-backup-verify.sh.
set -uo pipefail

playbook_dir="/home/machismo/Home-Lab/playbooks"
ansible_bin="/home/machismo/.ansible-venv/bin/ansible-playbook"
ansible_adhoc="/home/machismo/.ansible-venv/bin/ansible"
vault_pass="${ANSIBLE_VAULT_PASSWORD_FILE:-${HOME}/.config/ansible/vault-pass}"
report_local="$(mktemp)"
report_remote="/var/log/netframe-monitor/hardening-drift.json"

cd "${playbook_dir}" || { echo "ERROR: playbook dir not found" >&2; exit 1; }

export ANSIBLE_CONFIG="./ansible.cfg"
args=(desired-state.yml --check --diff)
[[ -f "${vault_pass}" ]] && args+=(--vault-password-file "${vault_pass}")

echo "=== $(date -Is) : hardening drift-check start ==="
out="$("${ansible_bin}" "${args[@]}" 2>&1)"
echo "${out}"

# Parse the PLAY RECAP: a node with changed>0 (after the apt-cache task was made
# changed_when:false) or unreachable/failed>0 has drifted or could not be verified.
epoch="$(date +%s)"
now="$(date -Is)"
nodes_json=""
any_drift="false"
drifted=""
while IFS= read -r line; do
	node="$(printf '%s' "${line}" | awk '{print $1}')"
	changed="$(printf '%s' "${line}" | sed -n 's/.*changed=\([0-9]*\).*/\1/p')"
	unreach="$(printf '%s' "${line}" | sed -n 's/.*unreachable=\([0-9]*\).*/\1/p')"
	failed="$(printf '%s' "${line}" | sed -n 's/.*failed=\([0-9]*\).*/\1/p')"
	[[ -z "${changed}" ]] && continue
	drift="false"
	if [[ "${changed}" != "0" || "${unreach}" != "0" || "${failed}" != "0" ]]; then
		drift="true"; any_drift="true"; drifted="${drifted}${node} "
	fi
	nodes_json="${nodes_json}\"${node}\":{\"changed\":${changed},\"unreachable\":${unreach},\"failed\":${failed},\"drift\":${drift}},"
done < <(printf '%s\n' "${out}" | sed -n '/PLAY RECAP/,$p' | grep -E 'changed=')

nodes_json="${nodes_json%,}"
printf '{"generated_epoch":%s,"generated":"%s","any_drift":%s,"drifted_nodes":"%s","nodes":{%s}}\n' \
	"${epoch}" "${now}" "${any_drift}" "${drifted% }" "${nodes_json}" > "${report_local}"

# Push the report to Randy (world-readable), where the monitor reads it. Never fatal.
"${ansible_adhoc}" randy -b -m ansible.builtin.copy \
	-a "src=${report_local} dest=${report_remote} mode=0644 owner=root group=root" \
	${vault_pass:+--vault-password-file "${vault_pass}"} >/dev/null 2>&1 \
	&& echo "report -> randy:${report_remote} (any_drift=${any_drift})" \
	|| echo "WARN: could not push report to randy" >&2

rm -f "${report_local}"
echo "=== $(date -Is) : hardening drift-check end (any_drift=${any_drift}) ==="
