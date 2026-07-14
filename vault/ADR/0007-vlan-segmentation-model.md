# ADR-0007: Seven-VLAN segmentation model with dual-homed servers

**Status:** Accepted · **Date:** 2026-07-12
**Tags:** #adr #decision #networking #security

## Context
The network began flat: management interfaces, servers, and edge devices all shared one broadcast domain. A single compromised device could reach the out-of-band controllers and every host. The lab needed segmentation that gave least-privilege reachability without a disruptive rebuild.

## Decision
Define seven VLANs on the Juniper EX3400 with OPNsense doing inter-VLAN routing and firewalling: management (1), out-of-band and BMC (20), servers (30), IoT (40), VoIP (50), guest (60), and lab (70). The GPU and storage nodes are dual-homed: management, corosync, and monitoring stay on VLAN 1, while NFS, PBS, and internet egress ride VLAN 30. Corosync is deliberately kept on VLAN 1's stable Layer 2 and not moved. See [[Runbook/Security-VLAN-Segmentation-Phased-2026-07-03]].

## Consequences
- Defense in depth: BMCs are isolated on VLAN 20, and cross-segment reachability is default-deny with explicit allows.
- Storage traffic is separated onto VLAN 30, off the management plane.
- More firewall policy to maintain, and dual-homing adds a NIC and per-node configuration to manage. The migration was executed in tracked phases so production never dropped.

## Alternatives considered
- **Flat network:** rejected. The original state, and the security problem being solved.
- **Per-host microsegmentation:** rejected. Overkill for a single-operator lab.
- **Fewer VLANs:** rejected. Would blur the OOB, server, and edge trust boundaries that matter most.
