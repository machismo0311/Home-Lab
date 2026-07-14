# 🏗️ NetFRAME Architecture Overview

> **Operator:** Kyle Mason (`machismo`) · **Cluster:** km-cluster · 7-node Proxmox VE 9.2.3
> **Location:** Greater Cleveland, OH · **Last Updated:** 2026-07-12

**Tags:** #architecture #overview #reference

> [!NOTE] **Audience:** written top-down for a first-time reader (a new operator or a technical reviewer). It states what the system is and why it is built this way. Detailed procedures live in the linked docs and runbooks.

---

## 🧭 At a glance
NetFRAME is a 7-node Proxmox cluster (**km-cluster**) in a 42U rack, running production-style services behind an OPNsense firewall with full VLAN segmentation. It serves three workloads: DUNE physics research compute, multi-tenant CS-student AI/ML (SLURM and GPU sharing), and a self-hosted LLM platform. It also runs standard self-hosted services for DNS, monitoring, VPN, backup, and media. Operating practices follow production norms: config-as-code where it counts, monitoring with alerting, DR-tested backups, and versioned runbooks.

## 🗺️ Topology

```mermaid
flowchart TB
  NET[Internet] --> EDGE[WAN edge]
  EDGE --> OPN[OPNsense router firewall VM100 on pve2]
  OPN --> SW[EX3400 core switch VLAN trunk]
  SW --> V1[VLAN1 Management 192.168.10.0/24]
  SW --> V20[VLAN20 OOB and BMC]
  SW --> V30[VLAN30 Servers]
  SW --> VX[VLAN40-70 IoT VoIP Guest Lab]
  V1 --> CL[km-cluster 7 node Proxmox PVE 9.2.3]
  CL --> GPU[GPU nodes QuarkyLab and Jarvis]
  CL --> STO[Randy storage PBS and ZFS]
  CL --> SVC[Service LXCs Pi-hole NPM Grafana Headscale Vaultwarden]
  CL --> K8S[RKE2 Kubernetes 3 node HA]
```

## 🎯 Design principles
- **LXC-first, not Docker.** Lightweight, Proxmox-native containers for services. Docker only when explicitly required.
- **Config-as-code where it counts.** The monitoring stack, OPNsense config backup, and CI/CD live in git. Deployment stays deliberate (SSH, systemd, API), not blind auto-deploy.
- **Secrets in Vaultwarden, never hardcoded.** Enforced with pre-commit secret scanning.
- **Defense in depth.** VLAN segmentation, out-of-band and BMC isolation on VLAN 20, an internal CA (step-ca), and a SIEM (Wazuh).
- **Observability first.** Every node is scraped. Alerting goes to Discord, including dead-man's-switch watchdogs.
- **Resilience by layer.** DNS HA, Kubernetes control-plane HA, and DR-tested backups. Single points of failure are tracked and retired deliberately. See [[High Availability/High Availability MOC]].
- **Honest about state.** Docs are grounded in verified reality, and open gaps are named rather than hidden.

## 🧱 The layers

### Physical
42U rack, dual-UPS A/B power buses, Juniper core switching. See [[Rack Layout]] and [[Power Distribution]].

### Network
OPNsense (VM 100 on pve2) is the router, firewall, and DHCP for the LAN. A Juniper EX3400 is the core switch carrying seven VLANs. Remote access uses a self-hosted Headscale tailnet. See [[Networking/Network Overview]] and [[Projects/Headscale]].

| VLAN | ID | Purpose |
|---|---|---|
| Management | 1 | Cluster, corosync, management (192.168.10.0/24) |
| Trusted / iDRAC | 20 | Out-of-band and BMC (isolated) |
| Servers | 30 | NFS, PBS, egress |
| IoT / VoIP / Guest / Lab | 40 / 50 / 60 / 70 | Segmented edge networks |

### Compute
Seven Proxmox nodes: four HP EliteDesk small-form-factor nodes (pve2 dedicated to OPNsense, pve3 to pve5 general), two Dell R730 GPU nodes (QuarkyLab with an RTX 8000 48GB for ML and research, Jarvis with 2x RTX 6000 for LLM inference), and Randy (SuperMicro storage and PBS). See [[Compute/Small Node Cluster]], [[Compute/Dell R730 - ML Node]], [[Compute/Dell R730 - General Node]].

### Storage
Randy runs ZFS: `datastore` (RAIDZ2, about 23 TiB usable) and `bulk` (2x 8-wide RAIDZ2 on a DS4246 shelf, about 41 TiB usable), plus Proxmox Backup Server. The GPU nodes carry their own ZFS pools for model libraries and scratch. See [[Infrastructure/Storage]].

### Platform services
RKE2 Kubernetes (3-node HA control plane, Cilium, MetalLB, private registry with internal TLS), dual Pi-hole DNS, Nginx Proxy Manager, the Grafana/Prometheus/Loki stack, Vaultwarden, step-ca, Ollama with an OpenAI-compatible `llm_router`, and Jellyfin. See [[Infrastructure/Proxmox Cluster]] and [[Infrastructure/Services & VMs]].

### Security
Phased VLAN segmentation (BMCs moved off the flat network to VLAN 20, services to VLAN 30, management-plane clamp), Wazuh SIEM, internal CA, rotated and scoped credentials, and pentest remediation. See [[Runbook/Security-VLAN-Segmentation-Phased-2026-07-03]].

### Observability
Prometheus scrapes all nodes. Grafana alerts to Discord across infra and UPS channels, including stale-report and backup-verify dead-man's switches. Scrutiny watches about 50 drives. NUT feeds UPS telemetry. See [[Runbook/Monitoring-Alerting-2026-07-10]].

### Resilience and HA
DNS and the Kubernetes control plane are already HA. WAN failover and an OPNsense CARP pair are in progress. Compute, storage, and switch redundancy are the planned next milestones. Full posture and roadmap: [[High Availability/High Availability MOC]].

---

## 🔗 Go deeper
- [[00 - Homelab MOC]]: master index of the whole vault
- [[Operations and Onboarding]]: how the cluster is run day to day
- [[High Availability/High Availability MOC]]: resilience map and roadmap
- [[ADR/README]]: architecture decision records (the why behind key choices)
- [[Runbook/Production-Readiness-Checklist-2026-07-10]]: prioritized operational punch list
- [[Runbook/RKE2-Phase1-HA-ControlPlane-2026-07-10]]: Kubernetes build
