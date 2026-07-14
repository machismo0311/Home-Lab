#!/usr/bin/env bash
# Link-failover test for the NETFRAME containerlab topology.
#
# Proves the network is resilient, not just reachable: there are two paths
# between the host subnets (direct r1<->r2, and backup r1<->r3<->r2). This test
# fails the PRIMARY link and asserts OSPF reroutes h1<->h2 traffic through r3
# with no loss of end-to-end connectivity, then restores it and asserts the
# route reverts to the preferred direct path.
#
# Run AFTER `containerlab deploy`. Exits non-zero if any assertion fails.
set -euo pipefail

lab="netframe"
DEST="10.10.2.0/24"        # h2's subnet, as seen from r1
NH_DIRECT="10.0.0.2"       # r2 across the primary link  (preferred, cost 10)
NH_BACKUP="10.0.1.2"       # r3 across the backup link   (cost 20)
fail=0

r1() { docker exec "clab-${lab}-r1" "$@"; }

# route_nexthop <dest-prefix> -> prints the next-hop IP r1 uses for <dest>.
# Uses the brief routing-table format ("O>* <prefix> [ad/metric] via <NH>,
# <iface>"), where the token after "via" is the next-hop IP — unlike the
# single-prefix detailed view, where "via" is followed by the interface name.
route_nexthop() {
	# NB: during reconvergence the prefix is briefly absent, so grep finds no
	# match and exits non-zero. The trailing `|| true` keeps that from tripping
	# `set -e`/`pipefail` and aborting the poll loop; `awk NR==1` (not `head`)
	# avoids SIGPIPE-ing the upstream grep.
	r1 vtysh -c "show ip route ospf" 2>/dev/null \
		| grep -F "${1}" | grep -oE 'via [0-9.]+' | awk 'NR==1{print $2}' || true
}

# wait_nexthop <dest> <expected-nh> <timeout-s> -> polls until r1 routes <dest>
# via <expected-nh>, allowing time for OSPF to reconverge and reprogram the FIB.
wait_nexthop() {
	local dest="$1" want="$2" timeout="$3" i got
	for i in $(seq 1 "${timeout}"); do
		got="$(route_nexthop "${dest}")"
		if [ "${got}" = "${want}" ]; then
			echo "  ok   r1 routes ${dest} via ${want} (converged after ${i}s)"
			return 0
		fi
		sleep 1
	done
	echo "  FAIL r1 routes ${dest} via '${got}', expected ${want} (after ${timeout}s)"
	fail=1
	return 1
}

# wait_ping <desc> <src-node> <target> -> polls a ping until it succeeds.
wait_ping() {
	local desc="$1" node="$2" target="$3" i
	for i in $(seq 1 30); do
		if docker exec "clab-${lab}-${node}" ping -c1 -W1 "${target}" >/dev/null 2>&1; then
			echo "  ok   ${desc} (reachable after ${i}s)"
			return 0
		fi
		sleep 1
	done
	echo "  FAIL ${desc} (still unreachable after 30s)"
	fail=1
	return 1
}

echo "== wait for full convergence (both r1 adjacencies Full) =="
for i in $(seq 1 60); do
	fulls="$(r1 vtysh -c 'show ip ospf neighbor' 2>/dev/null | grep -c Full || true)"
	if [ "${fulls}" -ge 2 ]; then
		echo "  r1 has ${fulls} Full adjacencies after ${i}s"
		break
	fi
	sleep 1
done

echo "== baseline: primary (direct r1->r2) path is in use =="
wait_nexthop "${DEST}" "${NH_DIRECT}" 30
wait_ping "h1 -> h2 over primary path" h1 10.10.2.10

echo "== FAIL the primary link (down r1 eth2 -> r2) =="
r1 ip link set eth2 down
echo "  primary transit link r1<->r2 is now DOWN"

echo "== failover: OSPF should reroute h1<->h2 through r3 =="
wait_nexthop "${DEST}" "${NH_BACKUP}" 30
wait_ping "h1 -> h2 over BACKUP path (via r3)" h1 10.10.2.10
wait_ping "h2 -> h1 over BACKUP path (via r3)" h2 10.10.1.10

# The direct neighbor (2.2.2.2) must be gone now; only r3 (3.3.3.3) remains.
if r1 vtysh -c 'show ip ospf neighbor' 2>/dev/null | grep -q '2.2.2.2'; then
	echo "  FAIL r1 still lists neighbor 2.2.2.2 after primary link down"
	fail=1
else
	echo "  ok   r1 dropped the direct neighbor (2.2.2.2)"
fi

echo "== restore the primary link (up r1 eth2) =="
r1 ip link set eth2 up
echo "  primary transit link r1<->r2 is back UP"

echo "== revert: OSPF should prefer the direct path again =="
wait_nexthop "${DEST}" "${NH_DIRECT}" 30
wait_ping "h1 -> h2 back over primary path" h1 10.10.2.10

if [ "${fail}" -ne 0 ]; then
	echo "FAILOVER TESTS FAILED"
	exit 1
fi
echo "ALL FAILOVER TESTS PASSED"
