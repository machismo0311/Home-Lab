# ADR-0004: Self-hosted Headscale over commercial Tailscale

**Status:** Accepted · **Date:** 2026-07-12
**Tags:** #adr #decision #networking #vpn

## Context
Remote access to the lab needs a mesh VPN with NAT traversal. Tailscale is the obvious choice for the clients, but its coordination server (the control plane that holds the network map and device keys) is a hosted SaaS. For a lab whose whole point is owning the infrastructure, depending on an external control plane for remote access is a philosophical and availability concern.

## Decision
Self-host Headscale, the open coordination server that speaks the Tailscale protocol, as an LXC (CT 105 on pve3). Keep the standard Tailscale clients on each node and continue to use Tailscale's public DERP relays for NAT traversal. Use never-expire pre-auth keys so established nodes keep working through a control-plane restart. See [[Projects/Headscale]].

## Consequences
- The control plane is fully owned: device authorization, the network map, and ACLs are local, with no SaaS account in the path.
- Established peers keep relaying through a control-plane outage because keys do not expire and clients cache the network map.
- Two dependencies remain: the Headscale instance itself must be maintained, and NAT traversal still leans on Tailscale's public DERP. The WAN-failover work adds a self-hosted DERP as optional hardening. See [[Runbook/WAN-Failover-FirstNet-MR7400-Plan-2026-07-12]].

## Alternatives considered
- **Tailscale SaaS:** rejected. Simplest, but the control plane is external and out of our control.
- **Raw WireGuard:** rejected as the primary mesh. No coordination or NAT traversal, so key and peer management becomes manual at cluster scale.
- **OpenVPN:** rejected. Heavier, hub-and-spoke, and weaker peer-to-peer behavior.
