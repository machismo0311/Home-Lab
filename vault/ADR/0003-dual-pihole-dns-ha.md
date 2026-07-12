# ADR-0003: DNS high availability via dual Pi-hole

**Status:** Accepted · **Date:** 2026-07-12
**Tags:** #adr #decision #dns #ha

## Context
DNS is a hard dependency for nearly everything on the network, including internal service discovery and ad and tracker filtering. A single Pi-hole instance is a single point of failure: if its host reboots or fails, name resolution stops network-wide, which looks like a total outage to clients.

## Decision
Run two Pi-hole instances: primary `.177` on the standalone Mac mini (pve1) and secondary `.178` on pve5 (CT 108). The secondary is a full mirror kept in sync by nebula-sync on a short timer (gravity, adlists, local DNS, allow and deny lists). OPNsense DHCP hands out both resolvers on all seven VLAN scopes, so clients fail over automatically. See [[Runbook/DNS-HA-OPNsense-Resilience-2026-07-10]].

## Consequences
- Loss of either Pi-hole host leaves resolution intact with no manual action.
- Blackbox probes plus a `PiholePrimaryDown` alert remove silent failover, so a degraded primary is still visible.
- Two instances must be kept in sync, which nebula-sync automates, and both admin passwords are unified in Vaultwarden.

## Alternatives considered
- **Single Pi-hole:** rejected. Simple, but a network-wide single point of failure.
- **Keepalived or CARP virtual IP fronting one active Pi-hole:** rejected for now. More moving parts than DHCP-advertised dual resolvers, which clients already handle natively.
- **Public upstream DNS only:** rejected. Loses filtering and internal name resolution.
