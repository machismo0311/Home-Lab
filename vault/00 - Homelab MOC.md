# 🖥️ Homelab — Master Map of Content
> **Operator:** Kyle Mason (`machismo`) · **Location:** Greater Cleveland, OH
> **Cabinet:** NetFRAME CS9000 42U · **Last Updated:** 2026-07-11

---

## 🗺️ Navigation

```mermaid
mindmap
  root((Homelab))
    Infrastructure
      [[Rack Layout]]
      [[Power Distribution]]
      [[Networking/Network Overview]]
    Compute
      [[Compute/Dell R730 - ML Node]]
      [[Compute/Dell R730 - General Node]]
      [[Compute/Small Node Cluster]]
    Storage
      [[Infrastructure/Storage]]
    Services
      [[Infrastructure/Proxmox Cluster]]
      [[Infrastructure/Services & VMs]]
    Kubernetes
      [[Runbook/RKE2-Phase1-HA-ControlPlane-2026-07-10]]
    Projects
      [[Projects/VoIP - FreePBX]]
      [[Projects/IMU Gesture Control]]
      [[Projects/Server Scraper]]
    Runbook
      [[Runbook/Daily Operations]]
      [[Runbook/Network Procedures]]
      [[Runbook/Recovery Procedures]]
      [[Runbook/Randy-PCIe-Slot-Recovery-2026-07-01]]
```

---

## 📦 Quick Reference — Rack Summary

| U Position | Device | Role |
|---|---|---|
| U42–U41 | Leviton Patch Panels (×2) | Cable management / patch |
| U40 | Juniper EX3400-48P | Core PoE+ switch |
| U39 | UniFi USW-24-250W | Access / PoE switch |
| U38 | Juniper EX2300-48P | Secondary switch |
| U36–U34 | HP EliteDesk G4 SFF ×2 (3U shelf) | pve2 (32GB) + pve3 (48GB) |
| U33–U31 | HP EliteDesk G3 Mini ×2 (3U shelf) | pve4 + pve5 (32GB each) |
| U30 | Mac mini (pve1) + RPi 4 (1U shelf) | Pi-hole / cluster mgmt |
| U29–U21 | *Open / cable mgmt* | — |
| U20–U18 | Dell R730 — Jarvis | LLM node (2× RTX 6000 48GB total, installed 2026-07-04) |
| U16–U15 | Dell R730 — QuarkyLab | ML node — RTX 8000 48GB, installed 2026-07-01 (the researcher / DUNE) |
| U14–U13 | SuperMicro CSE-219U — Randy | PBS, Jellyfin, ZFS storage |
| U12–U7 | NetApp DS4246 (4U) | JBOD storage shelf |
| U6 | Furman RP-8 | Power conditioning |
| U5–U4 | Tripp Lite SMART1500VA | UPS B — top half bus |
| U2–U1 | Middle Atlantic UPS-OL2200R | UPS A — bottom half / ML bus |

---

## 🌐 Network (live — OPNsense + VLANs)

> [!NOTE] OPNsense (VM 100 on pve2) is the **live LAN router/firewall/DHCP** for `192.168.10.0/24` (v25.7). The UniFi Dream Router is the **upstream WAN edge** (`192.168.1.x` WiFi/WAN). **VLANs are live** (2026-06-25). See [[Networking/Network Overview]].

| Device | IP | Notes |
|--------|-----|-------|
| OPNsense (LAN gateway) | 192.168.10.1 | VM 100 on pve2, v25.7 |
| pve1 (Mac Mini) | 192.168.10.193 | **Standalone** (not in km-cluster); Pi-hole host. TS: 100.x.x.x |
| pve2 (EliteDesk G4) | 192.168.10.204 | 32GB; OPNsense VM 100, step-ca |
| pve3 (EliteDesk G4) | 192.168.10.201 | 48GB; primary services node |
| pve4 (EliteDesk G3) | 192.168.10.202 | 32GB |
| pve5 (EliteDesk G3) | 192.168.10.203 | 32GB |
| QuarkyLab (R730) | 192.168.10.179 | ML node, RTX 8000 48GB; Wazuh VM 104 (.184) |
| Jarvis (R730) | 192.168.10.31 | LLM node (2× RTX 6000 48GB total, installed 2026-07-04, Ollama GPU-backed) |
| Randy (SuperMicro) | 192.168.10.187 | PBS, Jellyfin, ZFS storage |
| QuarkyLab iDRAC / Jarvis iDRAC / Randy IPMI | 192.168.20.20 / .20.21 / .20.22 (VLAN 20 since 2026-07-03) | |
| Juniper EX3400 | 192.168.10.50 | JunOS 23.4R2-S7.4, VLAN trunk |
| Nginx Proxy Manager | 192.168.10.181 | LXC 101 on pve3 |
| Vaultwarden | 192.168.10.182 | LXC 102 on pve3 |
| Grafana/Prometheus/Loki | 192.168.10.183 | LXC 103 on pve3 |
| Headscale | 192.168.10.186 | LXC 105 on pve3 |
| Homepage | 192.168.10.148 | LXC 106 on pve3 |
| Pi-hole (primary) | 192.168.10.177 | LXC on pve1 |
| Pi-hole (secondary) | 192.168.10.178 | CT 108 on pve5 (nebula-sync mirror, 2026-07-10) |
| RKE2 API VIP | 192.168.10.54 | kube-vip; CP = rke2-cp1/2/3 (.51/.52/.53 = VMs 201-203 on pve3/4/5); Randy = bare-metal worker |
| RKE2 MetalLB LBs | 192.168.10.71–.75 | .71 Uptime Kuma (status.netframe.local), .72 registry (registry.netframe.local, TLS) |
| Ares (laptop) | 192.168.10.100 wired | TS: 100.x.x.x |

---

## 🔗 Key Links

### Infrastructure
- [[Rack Layout]] — Physical layout, depth notes, thermal zones
- [[Power Distribution]] — Dual UPS bus diagram, load calculations
- [[Networking/Network Overview]] — Topology, VLANs, routing

### Compute
- [[Compute/Dell R730 - ML Node]] — QuarkyLab (iDRAC: 192.168.20.20, RTX 8000 48GB installed 2026-07-01)
- [[Compute/Dell R730 - General Node]] — Jarvis (iDRAC: 192.168.20.21, LLM, 2× RTX 6000 48GB installed 2026-07-04)
- [[Compute/Small Node Cluster]] — pve1 (standalone) + pve2–pve5

### Storage & Virtualization
- [[Infrastructure/Storage]] — NetApp DS4246, drive inventory
- [[Infrastructure/Proxmox Cluster]] — Cluster config, node table, OPNsense
- [[Infrastructure/Services & VMs]] — All deployed/planned services

### VPN
- [[Projects/Headscale]] — Self-hosted Tailscale control plane (pve3 CT 105)

### Kubernetes
- [[Runbook/RKE2-Phase1-HA-ControlPlane-2026-07-10]] — RKE2 cluster (3-node HA CP, Cilium, MetalLB, Randy storage worker, private registry w/ step-ca TLS + auto-renew); manifests in `scripts/rke2/`

### Switching
- [[Networking/Juniper EX3400-48P]] — Core switch config & Junos notes
- [[Networking/UniFi USW-24-250W]] — UniFi switch config
- [[Networking/Juniper EX2300-48P]] — Secondary switch

### Projects
- [[Projects/VoIP - FreePBX]] — CP-8841 phones + VoIP.ms
- [[Projects/IMU Gesture Control]] — Nordic nRF52 IMU → Home Assistant
- [[Projects/Server Scraper]] — eBay/TechMikeNY hardware alerter

### Runbook
- [[Runbook/Daily Operations]]
- [[Runbook/Network Procedures]]
- [[Runbook/Recovery Procedures]]
- [[Runbook/Randy-PCIe-Slot-Recovery-2026-07-01]] — Randy PCIe slot failure & recovery (incident report, 2026-07-01)

---

## 🎯 Active Goals

- [x] Finalize rack layout (v10)
- [x] Middle Atlantic UPS-2200R installed (bottom anchor)
- [x] Juniper EX3400 acquired & JunOS upgraded to 23.4R2-S7.4
- [x] EX3400 SSH issue resolved & switch on production network (2026-06-05)
- [x] Proxmox 5-node cluster live (pve1–pve5)
- [x] Core services deployed on pve3: NPM, Vaultwarden, Grafana+Prometheus+Loki, CrowdSec
- [x] Wildcard SSL cert issued (*.kylemason.org via Let's Encrypt + Cloudflare)
- [x] vault.kylemason.org and grafana.kylemason.org live
- [x] Headscale v0.29.1 deployed (pve3 CT 105) — Ares registered, self-hosted VPN control plane live
- [x] Add Ares SSH key to pve1 (added via pve2 cluster hop, 2026-06-20)
- [x] NetFRAME logo deployed to all five Proxmox nodes (pve1–pve5, 2026-06-20)
- [x] OPNsense cutover — VM 100 (pve2) is the live LAN router (Dream Router now WAN-only)
- [x] VLAN segmentation live (2026-06-25, EX3400 ge-0/0/46 trunk → UniFi Port 24)
- [x] Both Dell R730s installed and in km-cluster (QuarkyLab ML / Jarvis LLM)
- [x] Stand up QuarkyLab + Jarvis + Randy as Proxmox nodes (7-node km-cluster, PVE 9.2.3)
- [x] Deploy Wazuh SIEM on QuarkyLab (VM 104, .184)
- [x] All nodes in Grafana/Prometheus monitoring (node exporter, 8 targets)
- [x] PBS live on Randy (.187:8007); Jellyfin live on Randy (.187:8096)
- [x] Homepage dashboard live (homepage.kylemason.org); UPS monitoring (NUT→PeaNUT→Grafana→Discord)
- [x] Jarvis GPU software stack staged (2026-07-01) — kernel 6.14.11-9-pve pinned, NVIDIA 550.163.01 DKMS, Ollama → /opt/models
- [x] QuarkyLab RTX 6000 → RTX 8000 48GB swap — installed 2026-07-01
- [x] Jarvis 2× RTX 6000 install — installed & verified 2026-07-04 (48GB total, Ollama GPU-backed)
- [x] Security VLAN segmentation — all 3 phases (BMCs→VLAN 20 2026-07-03; services→VLAN 30; VLAN 30→VLAN 1 mgmt clamp 2026-07-10)
- [x] DNS HA — secondary Pi-hole (.178, pve5 CT 108, nebula-sync mirror of .177) + DHCP failover on all VLANs (2026-07-10)
- [x] RKE2 Kubernetes — Phases 1-7 (3-node HA CP, Cilium, MetalLB, Randy bare-metal storage worker, private registry w/ step-ca TLS + auto-renew); GPU Operator deferred (2026-07-10/11)
- [ ] DAC 10G uplink (xe-0/2/3 → UniFi SFP 2) — replace DAC with fiber optics
- [ ] Headscale Phase 2: fix Ares MagicDNS /etc/resolv.conf permission error
- [ ] Headscale Phase 3: migrate Kyle + the researcher devices off commercial Tailscale
- [ ] Headscale Phase 4: move CT 105 to VLAN 30, update login-server URLs
- [ ] VoIP project (deferred — post core infra)
- [ ] CCNA study cadence established
