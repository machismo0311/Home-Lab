#!/usr/bin/env bash
# Daily backup/storage-health verification, run from Ares (the control node).
# Installed as a user cron job — see the README (Scheduling). Mirrors the
# opnsense-config-backup pattern (user cron on Ares, append-only run log).
#
# The vault password file is added only when it exists, so this works both
# before and after the PBS token / vault.yml is set up.
set -uo pipefail

playbook_dir="/home/machismo/Home-Lab/playbooks"
ansible_bin="/home/machismo/.ansible-venv/bin/ansible-playbook"
vault_pass="${ANSIBLE_VAULT_PASSWORD_FILE:-${HOME}/.config/ansible/vault-pass}"

cd "${playbook_dir}" || {
	echo "ERROR: playbook dir not found: ${playbook_dir}" >&2
	exit 1
}

args=(backup-verify.yml)
[[ -f "${vault_pass}" ]] && args+=(--vault-password-file "${vault_pass}")

echo "=== $(date -Is) : backup-verify start ==="
"${ansible_bin}" "${args[@]}"
rc=$?
echo "=== $(date -Is) : backup-verify end (rc=${rc}) ==="
exit "${rc}"
