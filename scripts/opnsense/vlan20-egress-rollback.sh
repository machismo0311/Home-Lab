#!/usr/bin/env bash
# Rollback the VLAN 20 egress clamp: restore a pre-change /conf/config.xml backup
# and reload. Pass the backup path printed by vlan20-egress-clamp.sh, e.g.:
#   ./vlan20-egress-rollback.sh /conf/config.xml.bak-vlan20clamp-20260717-HHMMSS
#
# Restores the file, reloads the in-memory config cache, and reloads pf. Contained
# to what the clamp changed (opt1 rules); other interfaces are unaffected.
set -euo pipefail

PVE2="root@192.168.10.204"
VMID=100
BAK="${1:-}"

[ -n "$BAK" ] || { echo "usage: $0 /conf/config.xml.bak-vlan20clamp-<stamp>" >&2; exit 1; }
case "$BAK" in /conf/config.xml.bak-vlan20clamp-*) ;; *) echo "refusing: not a vlan20clamp backup path" >&2; exit 1 ;; esac

# The rollback drives the guest agent too. If it is down, use the serial console
# (qm terminal 100 from pve2, menu opt 8) to `cp $BAK /conf/config.xml` and reload.
if ! ssh -o BatchMode=yes -o ConnectTimeout=10 "$PVE2" "qm agent $VMID ping" >/dev/null 2>&1; then
	echo "$(date -Is) WARN: guest agent down — cannot roll back via agent. Fall back to serial console (qm terminal $VMID)." >&2
	exit 1
fi

echo "$(date -Is) restoring ${BAK} on VM ${VMID}..."
ssh -o BatchMode=yes -o ConnectTimeout=15 "$PVE2" \
	"qm guest exec $VMID -- /bin/sh -c 'test -f ${BAK} && cp ${BAK} /conf/config.xml && /usr/local/sbin/configctl config reload >/dev/null 2>&1; /usr/local/sbin/configctl filter reload >/dev/null 2>&1 && echo RESTORED+RELOADED || echo \"BACKUP NOT FOUND: ${BAK}\"'" \
	2>/dev/null | python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("out-data",""))
except Exception: print(sys.stdin.read())'
echo "$(date -Is) rollback done. Confirm opt1 shows the original 4 rules restored."
