#!/usr/bin/env bash
# Data-plane + control-plane tests for the NETFRAME containerlab topology.
# Run AFTER `containerlab deploy`. Exits non-zero if any assertion fails.
set -euo pipefail

lab="netframe"
fail=0

# Poll a ping until it succeeds (handles OSPF convergence / FIB programming),
# rather than assuming the data plane is ready the instant the adjacency is up.
wait_ping() { # wait_ping "<description>" <source-node> <target-ip>
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
}

check() { # check "<description>" <command...>
	local desc="$1"
	shift
	if "$@" >/dev/null 2>&1; then
		echo "  ok   ${desc}"
	else
		echo "  FAIL ${desc}"
		fail=1
	fi
}

echo "== wait for OSPF to converge =="
for i in $(seq 1 45); do
	if docker exec "clab-${lab}-r1" vtysh -c 'show ip ospf neighbor' 2>/dev/null | grep -q Full; then
		echo "  OSPF adjacency reached Full after ${i}s"
		break
	fi
	sleep 1
done

echo "== data-plane reachability (host-to-host, across r1 <-> r2) =="
wait_ping "h1 -> h2 (10.10.2.10)" h1 10.10.2.10
wait_ping "h2 -> h1 (10.10.1.10)" h2 10.10.1.10

echo "== control-plane =="
check "r1 OSPF neighbor is Full" \
	bash -c "docker exec clab-${lab}-r1 vtysh -c 'show ip ospf neighbor' | grep -q Full"
check "r1 learned 10.10.2.0/24 via OSPF" \
	bash -c "docker exec clab-${lab}-r1 vtysh -c 'show ip route ospf' | grep -q '10.10.2.0/24'"

if [ "${fail}" -ne 0 ]; then
	echo "NETWORK TESTS FAILED"
	exit 1
fi
echo "ALL NETWORK TESTS PASSED"
