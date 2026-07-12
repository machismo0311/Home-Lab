# Architecture Decision Records (ADR)

**Tags:** #adr #decision #reference

This folder records the significant architecture decisions behind NetFRAME: the context, the choice, and the consequences. Each record is immutable once accepted. If a decision changes, a new ADR supersedes the old one rather than editing history. Format follows the Michael Nygard ADR template.

## Status values
- **Proposed:** under consideration, not yet acted on.
- **Accepted:** in effect.
- **Superseded:** replaced by a later ADR (linked).

## Index
| ADR | Title | Status |
|---|---|---|
| [[0001-dedicated-opnsense-router]] | Dedicated OPNsense router on Proxmox, roadmap to CARP pair | Accepted |
| [[0002-lxc-first-over-docker]] | LXC-first over Docker for services | Accepted |
| [[0003-dual-pihole-dns-ha]] | DNS high availability via dual Pi-hole | Accepted |
| [[0004-self-hosted-headscale]] | Self-hosted Headscale over commercial Tailscale | Accepted |
| [[0005-compute-ha-storage-strategy]] | Compute HA storage: Ceph vs ZFS replication | Proposed |

## Backlog (not yet written)
RKE2 as the Kubernetes distribution, VLAN segmentation model, config-as-code with manual deploy, Randy as ZFS and PBS storage host, GPU node kernel pinning.

Related: [[Architecture Overview]] · [[High Availability/High Availability MOC]]
