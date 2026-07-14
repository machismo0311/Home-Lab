# ADR-0006: RKE2 as the Kubernetes distribution

**Status:** Accepted · **Date:** 2026-07-12
**Tags:** #adr #decision #kubernetes

## Context
The lab needed a Kubernetes platform on the existing Proxmox cluster: highly available, secure by default, and comfortable on bare metal and on-prem rather than assuming a cloud. It also had to fit the house style of systemd-managed services on LXC and VMs. The field includes k3s, RKE2, upstream kubeadm, k0s, and Talos.

## Decision
Use RKE2 (Rancher's government-grade Kubernetes). It ships CIS-hardened defaults, embedded etcd with built-in HA, a choice of CNI including Cilium, and installs as a single supervisor plus agent managed by systemd. The control plane runs as three VMs with a kube-vip API virtual IP, and the storage host joins as a tainted bare-metal agent. See [[Runbook/RKE2-Phase1-HA-ControlPlane-2026-07-10]].

## Consequences
- A hardened, HA control plane that tolerates losing a node, with etcd quorum across three members.
- Systemd-based install matches how everything else in the lab is operated.
- Heavier than k3s, and the tooling leans toward the SUSE and Rancher ecosystem.

## Alternatives considered
- **k3s:** rejected as the primary. Excellent and lightweight, but RKE2 was chosen for production-grade hardening and first-class HA.
- **kubeadm (upstream):** rejected. More manual assembly and hardening for no gain here.
- **Talos:** rejected. Immutable-OS model does not fit running Kubernetes as guests on Proxmox with systemd.
- **k0s:** viable, rejected for smaller ecosystem and less operational familiarity.
