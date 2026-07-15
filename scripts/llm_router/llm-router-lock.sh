#!/bin/bash
# llm-router-lock: restrict tcp/8000 (llm_router) to its known clients only.
#
# llm_router binds 0.0.0.0 because it must serve Open WebUI (a different host) and
# NPM, and because binding a specific VLAN-30 address would fail at boot if vmbr1
# isn't up yet. It has NO authentication of its own, so the bind is paired with this
# allowlist instead. Same pattern as netframe-8808-lock / netframe-console-lock on
# this node. Scoped strictly to tcp/8000 - no other service is affected.
#
# Clients:
#   127.0.0.1        - local callers on Jarvis (netframe_*, CLI probes)
#   192.168.30.185   - Open WebUI (LXC 107, VLAN 30 only; sources from .30.185)
#   192.168.10.181   - NPM VLAN 1 leg (proxy host 5 llm.netframe.local -> .10.31:8000)
#   192.168.30.181   - NPM VLAN 30 leg (if the proxy host is ever repointed to .30.31)
#
# Managed by llm-router-lock.service (oneshot, idempotent, re-applies on boot).
port=8000
clients=(127.0.0.1 192.168.30.185 192.168.10.181 192.168.30.181)

# Remove any prior copies of our rules so re-runs don't stack duplicates.
for c in "${clients[@]}"; do
	while /usr/sbin/iptables -C INPUT -p tcp --dport "$port" -s "$c" -j ACCEPT 2>/dev/null; do
		/usr/sbin/iptables -D INPUT -p tcp --dport "$port" -s "$c" -j ACCEPT
	done
done
while /usr/sbin/iptables -C INPUT -p tcp --dport "$port" -j DROP 2>/dev/null; do
	/usr/sbin/iptables -D INPUT -p tcp --dport "$port" -j DROP
done

# Insert in priority order: DROP first, then ACCEPTs on top of it.
/usr/sbin/iptables -I INPUT 1 -p tcp --dport "$port" -j DROP
for c in "${clients[@]}"; do
	/usr/sbin/iptables -I INPUT 1 -p tcp --dport "$port" -s "$c" -j ACCEPT
done
