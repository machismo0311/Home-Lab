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
| [[0006-rke2-kubernetes-distribution]] | RKE2 as the Kubernetes distribution | Accepted |
| [[0007-vlan-segmentation-model]] | Seven-VLAN segmentation model with dual-homed servers | Accepted |
| [[0008-config-as-code-manual-deploy]] | Config-as-code with manual deployment | Accepted |
| [[0009-randy-storage-host]] | Randy as the single ZFS and PBS storage host | Accepted |
| [[0010-gpu-node-kernel-pinning]] | Kernel pinning on GPU nodes for the NVIDIA driver stack | Accepted |

## Backlog (not yet written)
Offsite backup strategy (restic to B2), alerting without Alertmanager (Grafana-native to Discord), secrets management with Vaultwarden, WAN failover and OPNsense CARP (drafted in the runbook and [[High Availability/High Availability MOC]]).

Related: [[Architecture Overview]] · [[High Availability/High Availability MOC]]
