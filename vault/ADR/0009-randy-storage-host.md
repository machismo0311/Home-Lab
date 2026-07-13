# ADR-0009: Randy as the single ZFS and PBS storage host

**Status:** Accepted · **Date:** 2026-07-12
**Tags:** #adr #decision #storage

## Context
The cluster needed bulk capacity, data integrity, and centralized backups. The options were distributed storage across nodes (Ceph), a single dedicated storage node, or local disks per node with no shared layer. The lab had a SuperMicro 24-bay chassis available and a limited hardware and time budget.

## Decision
Run a dedicated storage node (Randy, a SuperMicro CSE-219U) with ZFS: a `datastore` pool for primary data and a `bulk` pool on an attached NetApp DS4246 shelf, plus Proxmox Backup Server. It serves NFS to the cluster and to Kubernetes, and holds the nightly backups. See [[Infrastructure/Storage]].

## Consequences
- Large usable capacity with ZFS data integrity, snapshots, and a single place for backups.
- Simple to operate compared with a distributed store.
- Randy is a single point of failure for both storage and backups. This is explicitly acknowledged and tracked in [[ADR/0005-compute-ha-storage-strategy]] and [[High Availability/High Availability MOC]]; the mitigations are an offsite backup (planned) and the Ceph evaluation that would remove this SPOF.

## Alternatives considered
- **Ceph now:** rejected for the moment. It removes the SPOF but needs OSD disks on three or more nodes, a dedicated network, and significant operational learning. Kept as the evaluated future path in ADR-0005.
- **Local per-node storage:** rejected. No shared storage for Kubernetes or migration, and no central backup target.
