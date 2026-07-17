#!/usr/bin/env bash
# VLAN 20 (BMC / "TRUSTED") egress clamp — AAR 2026-07-17, segmentation Phase 1.5.
#
# WHAT: on the OPNsense opt1 interface (VLAN 20, 192.168.20.0/24) remove the three
# broad "Allow trusted -> {management, servers, internet}" pass rules and add a
# block+log catch-all. A compromised BMC (iDRAC/IPMI on .20/.21/.22) can currently
# reach VLAN 1, VLAN 30 and the internet through those passes; this stops it.
#
# SAFE BECAUSE: Ares manages the BMCs over L2 on the SAME subnet (.20.100 -> .20.x),
# which never traverses the firewall — so this L3 rule change cannot break BMC
# management. Blast radius is contained to VLAN 20; no other interface's rules change.
#
# MECHANISM: Ares -> ssh pve2 -> qm guest exec 100 -> php write_config + filter reload.
# Backs up /conf/config.xml on the box first. Guarded: does nothing without --apply.
#
# ROLLBACK: scripts/opnsense/vlan20-egress-rollback.sh (restores the dated backup).
set -euo pipefail

PVE2="root@192.168.10.204"
VMID=100
STAMP="$(date +%Y%m%d-%H%M%S)"
BAK="/conf/config.xml.bak-vlan20clamp-${STAMP}"

if [ "${1:-}" != "--apply" ]; then
	cat <<EOF
DRY: this would, on OPNsense VM ${VMID} (via pve2 guest agent):
  1. back up /conf/config.xml -> ${BAK}
  2. remove the 3 opt1 (VLAN20) PASS rules (->management, ->servers, ->internet)
  3. add a block+log catch-all on opt1
  4. configctl filter reload
Re-run with --apply to execute. Rollback: vlan20-egress-rollback.sh ${BAK}
EOF
	exit 0
fi

read -r -d '' PHP <<'PHP' || true
<?php
require_once("config.inc");
require_once("util.inc");
global $config;
$new = array(); $removed = 0;
foreach ($config['filter']['rule'] as $r) {
    if (($r['interface'] ?? '') === 'opt1' && ($r['type'] ?? '') === 'pass') { $removed++; continue; }
    $new[] = $r;
}
$new[] = array(
    'type' => 'block',
    'interface' => 'opt1',
    'ipprotocol' => 'inet',
    'source' => array('network' => 'opt1'),
    'destination' => array('any' => ''),
    'log' => '1',
    'descr' => 'VLAN20 BMC egress clamp: block+log all (AAR 2026-07-17)'
);
$config['filter']['rule'] = $new;
write_config("VLAN20 BMC egress clamp: remove trusted-pass rules + block/log (AAR 2026-07-17)");
echo "removed=$removed opt1 pass rules; block+log appended; total rules=" . count($config['filter']['rule']) . "\n";
PHP

b64="$(printf '%s' "$PHP" | base64 -w0)"
echo "$(date -Is) backing up config + applying clamp on VM ${VMID}..."
ssh -o BatchMode=yes -o ConnectTimeout=15 "$PVE2" \
	"qm guest exec $VMID -- /bin/sh -c 'cp /conf/config.xml ${BAK} && printf %s \"$b64\" | openssl base64 -d -A > /tmp/vl20apply.php && php /tmp/vl20apply.php && rm -f /tmp/vl20apply.php && /usr/local/sbin/configctl filter reload >/dev/null 2>&1 && echo APPLIED+RELOADED'" \
	2>/dev/null | python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("out-data",""))
except Exception: print(sys.stdin.read())'
echo "$(date -Is) done. Backup on box: ${BAK}"
echo "VERIFY next: watch the opt1 block log, confirm BMC still reachable from Ares (L2), confirm BMC cannot reach VLAN1/internet."
echo "ROLLBACK:  scripts/opnsense/vlan20-egress-rollback.sh ${BAK}"
