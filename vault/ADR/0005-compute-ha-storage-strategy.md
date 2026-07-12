# ADR-0005: Compute HA storage: Ceph vs ZFS replication

**Status:** Proposed · **Date:** 2026-07-12
**Tags:** #adr #decision #storage #ha

## Context
Proxmox `ha-manager` can restart a failed guest on another node only if that guest's disk is reachable from the other node. Today the cluster has no HA resources configured and all guest storage is local (`local`, `local-lvm`) with no replication, so nothing auto-recovers on node failure. Separately, Randy is a single storage node serving PBS, the RKE2 NFS class, the registry, and bare-metal storage, which is itself a single point of failure. Closing the compute-HA gap and the storage-SPOF gap are related, because the storage choice drives both. See [[High Availability/High Availability MOC]].

## Decision
Proposed, not yet accepted. Two candidate paths:
1. **ZFS replication plus ha-manager** for a small set of critical single-instance guests (monitoring, Headscale, Wazuh, Vaultwarden, primary Pi-hole). Lighter, works on the current local ZFS, asynchronous with a small data-loss window.
2. **Ceph** across nodes as shared storage, which enables ha-manager relocation for any guest and removes the Randy storage SPOF at the same time. Heavier: it needs OSD disks on at least three nodes, a dedicated storage network, and operational learning.

Current lean is to prove the concept with ZFS replication on a few guests first, then evaluate Ceph as the larger investment once the disk and network budget is in place.

## Consequences
To be recorded when this is accepted. ZFS replication delivers partial, per-guest HA quickly. Ceph delivers broad HA and removes the storage SPOF but is a significant build.

## Alternatives considered
- **Shared NFS or iSCSI from Randy:** rejected as the HA foundation. It would enable relocation but keeps Randy as the single point of failure, which is one of the problems being solved.
- **Do nothing:** rejected. Leaves every single-instance guest exposed to node failure.
