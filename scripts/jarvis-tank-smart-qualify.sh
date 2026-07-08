#!/bin/bash
# jarvis-tank-smart-qualify — launch / poll / summarize SAS long self-tests on
# Jarvis's `tank` pool drives (the 5× 2 TB ST2000NX046x behind the HBA330).
#
# These are used enterprise drives that were pooled (raidz1) without a prior
# qualification pass, so this runs the SAS extended self-test on each member and
# reports the result the same way we did for Randy's DS4246 drives.
#
# Runs ON JARVIS as root (smartctl needs the local disks). It resolves pool
# members from `zpool status` rather than trusting sdX letters, which are not
# stable across reboots.
#
#   ./jarvis-tank-smart-qualify.sh start     # kick long self-test on every tank member
#   ./jarvis-tank-smart-qualify.sh status    # % remaining / in-progress (default)
#   ./jarvis-tank-smart-qualify.sh result    # pass/fail + defect/error summary
#
# The extended test runs on the drive itself (background), non-disruptive to I/O;
# expect ~7-8 h per drive. `start` fires all five in parallel, then poll `status`.
set -u

POOL=tank

log(){ echo "$(date '+%F %T') $*"; }
die(){ echo "ERROR: $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "must run as root (smartctl needs raw disk access)"
command -v smartctl >/dev/null || die "smartctl not found (apt install smartmontools)"
command -v zpool    >/dev/null || die "zpool not found"

# Resolve the leaf block devices of POOL to /dev/sdX. zpool may print by-id
# names, sdX, or partition suffixes; map each back to its parent /dev node.
tank_disks(){
	zpool status -LP "$POOL" 2>/dev/null \
		| awk 'f && /^\s+\/dev\//{print $1} /config:/{f=1} /errors:/{f=0}' \
		| sed -E 's#(/dev/sd[a-z]+)[0-9]*#\1#' \
		| sort -u
}

DISKS=$(tank_disks)
[ -n "$DISKS" ] || die "no disks resolved for pool '$POOL' — is it imported? (zpool status $POOL)"

cmd=${1:-status}
case "$cmd" in
	start)
		log "starting SAS long self-test on $POOL members:"
		for d in $DISKS; do
			printf '  %s -> ' "$d"
			smartctl -t long "$d" 2>&1 | grep -iE 'test has begun|please wait|error' || echo "started"
		done
		echo
		log "poll progress with:  $0 status"
		;;
	status)
		for d in $DISKS; do
			echo "=== $d ==="
			smartctl -c "$d" 2>/dev/null | grep -iE 'self-test execution|% of test remaining|polling' \
				|| smartctl -l selftest "$d" 2>/dev/null | head -4
			echo
		done
		;;
	result)
		fail=0
		for d in $DISKS; do
			echo "=== $d ==="
			# SAS self-test log: newest entry first; "Completed" = pass, anything
			# else (read failure / servo / etc.) is a fault we must surface.
			smartctl -l selftest "$d" 2>/dev/null | grep -iE 'Description|Completed|failure|self-test' | head -3
			smartctl -a "$d" 2>/dev/null \
				| grep -iE 'SMART Health|grown defect list|uncorrected|Non-medium error' \
				| sed 's/^/    /'
			if smartctl -l selftest "$d" 2>/dev/null | grep -qi 'failure'; then
				echo "    >>> FAIL: self-test read/servo failure — replace this disk"
				fail=1
			fi
			echo
		done
		if [ "$fail" -eq 0 ]; then
			log "all $POOL drives: last self-test Completed without error"
		else
			log "one or more drives FAILED — see >>> lines above"
		fi
		echo
		log "when tests finish, refresh the hub:  systemctl start scrutiny-collector.service"
		exit "$fail"
		;;
	*)
		die "usage: $0 {start|status|result}"
		;;
esac
