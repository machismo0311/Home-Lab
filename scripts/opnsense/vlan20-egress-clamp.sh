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
  0. PRECHECK the guest agent responds (else abort — apply+rollback both need it)
  1. back up /conf/config.xml -> ${BAK}
  2. PREPEND a FLOATING quick BLOCK for opt1 internet-bound (dest !Local_Nets) — this
     is REQUIRED: a quick multi-WAN-failover floating rule already passes VLAN20 ->
     internet, so removing the interface pass alone does NOT block it (found 2026-07-17)
  3. remove the 3 opt1 (VLAN20) interface PASS rules (->management, ->servers, ->internet)
  4. add an opt1 interface block+log for internal attempts
  5. configctl filter reload
Re-run with --apply to execute. Rollback: vlan20-egress-rollback.sh ${BAK}
EOF
	exit 0
fi

# GATE: the guest agent must be alive — both this apply AND the rollback drive it.
# It has proven flaky on this OPNsense (down 2026-07-17). Never apply a firewall
# change whose rollback channel is unavailable.
if ! ssh -o BatchMode=yes -o ConnectTimeout=10 "$PVE2" "qm agent $VMID ping" >/dev/null 2>&1; then
	echo "$(date -Is) ABORT: OPNsense guest agent not responding — rollback channel unavailable. Revive it (console/GUI) first." >&2
	exit 1
fi

read -r -d '' PHP <<'PHP' || true
<?php
require_once("config.inc");
require_once("util.inc");
global $config;
// (2) floating quick BLOCK for opt1 internet-bound, PREPENDED so it precedes the
// existing quick "Multi-WAN failover" floating pass rule (which would otherwise pass
// VLAN20 -> internet before any interface rule is evaluated).
$fblock = array(
    'type' => 'block', 'interface' => 'opt1', 'ipprotocol' => 'inet',
    'floating' => 'yes', 'quick' => '1', 'direction' => 'in', 'statetype' => 'keep state',
    'log' => '1', 'source' => array('any' => '1'),
    'destination' => array('address' => 'Local_Nets', 'not' => '1'),
    'descr' => 'VLAN20 BMC internet block+log (AAR 2026-07-17)'
);
$new = array($fblock); $removed = 0;
foreach ($config['filter']['rule'] as $r) {
    // (3) drop the opt1 interface pass rules (NOT the floating failover rule)
    if (($r['interface'] ?? '') === 'opt1' && ($r['type'] ?? '') === 'pass' && empty($r['floating'])) { $removed++; continue; }
    $new[] = $r;
}
// (4) interface block+log for VLAN20 -> internal attempts (visibility)
$new[] = array(
    'type' => 'block', 'interface' => 'opt1', 'ipprotocol' => 'inet',
    'log' => '1', 'source' => array('network' => 'opt1'),
    'destination' => array('any' => ''),
    'descr' => 'VLAN20 egress clamp: block+log internal (AAR 2026-07-17)'
);
$config['filter']['rule'] = $new;
write_config("VLAN20 BMC egress clamp v2: floating internet-block + interface clamp (AAR 2026-07-17)");
echo "removed=$removed opt1 interface pass rules; +1 floating internet-block; +1 interface block; total=" . count($config['filter']['rule']) . "\n";
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
