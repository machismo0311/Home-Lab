#!/usr/bin/env bash
# breakglass-refresh.sh - snapshot critical infrastructure credentials from
# Vaultwarden into an age-encrypted file that does NOT depend on Vaultwarden,
# NPM, Pi-hole, or pve3 to read back (AAR 2026-07-16 recommendation 11: during
# the outage, switch/firewall creds were locked inside the very failure domain
# they were needed to diagnose).
#
# Usage:
#   bw login / bw unlock            # get a session first (owner action)
#   export BW_SESSION="..."
#   ./breakglass-refresh.sh
#
# Output: ~/.config/breakglass/breakglass.age on Ares (0600) plus an off-host
# copy on Randy (/root/breakglass.age). Plaintext never touches disk.
# Read back anytime with breakglass-read.sh (needs only age + the local key).
#
# Item list: ~/.config/breakglass/items.txt (one Vaultwarden item name per
# line, '#' comments allowed). A missing item is reported, not fatal, so the
# list can name things before they exist in the vault.

set -u

conf_dir="${HOME}/.config/breakglass"
items_file="${conf_dir}/items.txt"
out_file="${conf_dir}/breakglass.age"
# Reuse the DR age identity that already lives outside Vaultwarden (same
# pattern as the OPNsense config backups; also printed/filed per its runbook).
key_file="${HOME}/.config/opnsense-backup/age-key.txt"
offhost="root@192.168.10.187:/root/breakglass.age"

mkdir -p "${conf_dir}"
chmod 700 "${conf_dir}"

if [[ ! -f "${items_file}" ]]; then
	cat > "${items_file}" <<'EOF'
# Vaultwarden item names to snapshot into the break-glass file.
# One per line. Keep this list to what you need when Vaultwarden is DOWN:
# network gear, consoles, and out-of-band access.
EX3400
OPNsense
QuarkyLab iDRAC
Jarvis iDRAC
Randy IPMI
nginx-proxy-manager (NPM) admin
Pi-hole
EOF
	echo "Wrote a starter item list to ${items_file} - review it, then re-run."
	exit 0
fi

if ! command -v age > /dev/null || ! command -v bw > /dev/null; then
	echo "ERROR: needs 'age' and 'bw' on PATH." >&2
	exit 1
fi
if [[ ! -f "${key_file}" ]]; then
	echo "ERROR: age identity ${key_file} not found." >&2
	exit 1
fi
if [[ -z "${BW_SESSION:-}" ]]; then
	echo "ERROR: BW_SESSION not set. Run: export BW_SESSION=\"\$(bw unlock --raw)\"" >&2
	exit 1
fi

recipient="$(age-keygen -y "${key_file}")"

bw sync > /dev/null 2>&1 || true

plain="# NetFRAME break-glass credentials - generated $(date -u +%FT%TZ)
# Read with breakglass-read.sh. Refresh after ANY rotation of these secrets.
"
missing=0
found=0
while IFS= read -r name; do
	[[ -z "${name}" || "${name}" == \#* ]] && continue
	item_json="$(bw list items --search "${name}" 2> /dev/null | python3 -c '
import json, sys
wanted = sys.argv[1].lower()
items = json.load(sys.stdin)
best = next((i for i in items if i["name"].lower() == wanted), None) or \
       next((i for i in items if wanted in i["name"].lower()), None)
print(json.dumps(best) if best else "")' "${name}")"
	if [[ -z "${item_json}" ]]; then
		echo "  MISSING in vault: ${name}"
		missing=$((missing + 1))
		continue
	fi
	entry="$(python3 - "${item_json}" <<'PYEOF'
import json
import sys
i = json.loads(sys.argv[1])
login = i.get("login") or {}
lines = ["## " + i["name"]]
if login.get("username"):
    lines.append("username: " + login["username"])
if login.get("password"):
    lines.append("password: " + login["password"])
for u in (login.get("uris") or []):
    lines.append("uri: " + (u.get("uri") or ""))
if i.get("notes"):
    lines.append("notes: " + i["notes"])
print("\n".join(lines))
PYEOF
)"
	plain="${plain}
${entry}
"
	found=$((found + 1))
	echo "  captured: ${name}"
done < "${items_file}"

if [[ "${found}" -eq 0 ]]; then
	echo "ERROR: nothing captured; not overwriting ${out_file}." >&2
	exit 1
fi

printf '%s\n' "${plain}" | age -r "${recipient}" -o "${out_file}.tmp" \
	&& mv "${out_file}.tmp" "${out_file}" \
	&& chmod 600 "${out_file}"
echo "Encrypted ${found} item(s) -> ${out_file} (${missing} missing)"

if scp -q "${out_file}" "${offhost}" 2> /dev/null; then
	echo "Off-host copy -> ${offhost}"
else
	echo "WARN: off-host copy to Randy failed (retry when reachable)." >&2
fi
