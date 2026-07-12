#!/usr/bin/env bash
# Data-plane + control-plane tests for the NETFRAME containerlab topology.
# Run AFTER `containerlab deploy`. Exits non-zero if any assertion fails.
set -euo pipefail

lab="netframe"
fail=0

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
for i in $(seq 1 30); do
	if docker exec "clab-${lab}-r1" vtysh -c 'show ip ospf neighbor' 2>/dev/null | grep -q Full; then
		echo "  OSPF adjacency reached Full after ${i}s"
		break
	fi
	sleep 1
done

echo "== data-plane reachability (across r1 <-> r2) =="
check "h1 -> h2 (10.10.2.10)" \
	docker exec "clab-${lab}-h1" ping -c2 -W2 10.10.2.10
check "h2 -> h1 (10.10.1.10)" \
	docker exec "clab-${lab}-h2" ping -c2 -W2 10.10.1.10

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
