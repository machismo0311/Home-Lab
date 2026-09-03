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

# MANAGED-RUNTIME PROVENANCE, carried by this same daily check rather than a second timer.
#
# It belongs here and not on Jarvis: verification needs the tracked trust root, the signed
# manifests and the declared intended versions, all of which live in the NetFRAME repository on
# this control node. Jarvis holds only the artifact being audited, and a host that verifies its own
# deployment can attest to nothing an attacker with write access could not also forge.
#
# Detection only, exactly like the hardening check above: no repair, no redeploy, no symlink switch,
# no restart. Drift is surfaced for a human.
echo "--- managed-runtime provenance ---"
prov_json="$("${playbook_dir}/scheduling/provenance-drift.sh" 2>/dev/null)"
if ! printf '%s' "${prov_json}" | python3 -c 'import json,sys; json.load(sys.stdin)' 2>/dev/null; then
	prov_json='{"schema":"netframe.provenance-drift-report/1","status":"unknown","exit_code":null,"runtimes":[],"reason":"provenance check produced no usable report"}'
fi
prov_status="$(printf '%s' "${prov_json}" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("status","unknown"))' 2>/dev/null)"
prov_status="${prov_status:-unknown}"
printf '%s' "${prov_json}" | python3 -c '
import json, sys
d = json.load(sys.stdin)
print("provenance: %s%s" % (d.get("status"), (" - " + d["reason"]) if d.get("reason") else ""))
for r in d.get("runtimes") or []:
    print("  %-26s %-19s sig=%-8s artifact=%-8s version=%-8s active=%-7s intended=%s deployed=%s%s" % (
        r.get("runtime"), r.get("composite_state"), r.get("signature_status"),
        r.get("artifact_integrity"), r.get("version_status"), r.get("active_target_status"),
        (r.get("intended_sha") or "-")[:12], r.get("deployed_sha") or "-",
        ("  CLASSES: " + ", ".join(r["classes"])) if r.get("classes") else ""))
' 2>/dev/null

# Anything other than a proven-intact result is operator-visible drift. "Could not verify" and
# "verified corruption" stay distinguishable inside the provenance object; both raise the flag the
# dashboard actually reads, because a provenance check nobody can see is not a check.
if [[ "${prov_status}" != "intact" ]]; then
	any_drift="true"
	drifted="${drifted}provenance "
fi

write_report() {
	printf '{"generated_epoch":%s,"generated":"%s","any_drift":%s,"drifted_nodes":"%s","nodes":{%s}%s}\n' \
		"${epoch}" "${now}" "${any_drift}" "${drifted% }" "${nodes_json}" "${1:-}" > "${report_local}"
}

write_report ",\"provenance\":${prov_json}"
# The pre-existing hardening report must not regress because provenance was added to it. If the
# combined document is not valid JSON, the provenance section is dropped and the original report is
# written instead - a lost addition beats a broken consumer.
if ! python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "${report_local}" 2>/dev/null; then
	echo "WARN: provenance section produced invalid JSON; report written without it" >&2
	write_report ""
fi

# Push the report to Randy (world-readable), where the monitor reads it. Never fatal.
"${ansible_adhoc}" randy -b -m ansible.builtin.copy \
	-a "src=${report_local} dest=${report_remote} mode=0644 owner=root group=root" \
	${vault_pass:+--vault-password-file "${vault_pass}"} >/dev/null 2>&1 \
	&& echo "report -> randy:${report_remote} (any_drift=${any_drift})" \
	|| echo "WARN: could not push report to randy" >&2

rm -f "${report_local}"
echo "=== $(date -Is) : hardening drift-check end (any_drift=${any_drift}) ==="
