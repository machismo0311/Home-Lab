# 🖥️ Homelab — Master Map of Content
> **Operator:** Kyle Mason (`machismo`) · **Location:** Vermilion / Greater Cleveland, OH
> **Cabinet:** NetFRAME CS9000 42U · **Last Updated:** 2026-06-17

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
    Projects
      [[Projects/VoIP - FreePBX]]
      [[Projects/IMU Gesture Control]]
      [[Projects/Server Scraper]]
    Runbook
      [[Runbook/Daily Operations]]
      [[Runbook/Network Procedures]]
      [[Runbook/Recovery Procedures]]
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
| U20–U18 | Dell R730 — Jarvis (ML Node) | AI/ML workloads (pending) |
| U16–U15 | Dell R730 — quarkylab (General) | Heavy compute (pending) |
| U14–U13 | SuperMicro CSE-219U | TrueNAS target (pending) |
| U12–U7 | NetApp DS4246 (4U) | JBOD storage shelf |
| U6 | Furman RP-8 | Power conditioning |
| U5–U4 | Tripp Lite SMART1500VA | UPS A — top half bus |
| U2–U1 | Middle Atlantic UPS-2200R | UPS B — bottom half / ML bus |

---

## 🌐 Current Network (Flat — Pre-VLAN Cutover)

> [!NOTE] VLANs are planned but not yet live. All devices are on a flat 192.168.10.0/24 subnet. OPNsense (VM 100 on pve2) is installed but not in the network path — Dream Router is still routing. VLAN segmentation happens at OPNsense cutover.

| Device | IP | Notes |
|--------|-----|-------|
| pve1 (Mac Mini) | 192.168.10.193 | Tailscale: 100.116.237.31 |
| pve2 (EliteDesk G4) | 192.168.10.204 | Hosts OPNsense VM 100 |
| pve3 (EliteDesk G4) | 192.168.10.201 | Primary services node |
| pve4 (EliteDesk G3) | 192.168.10.202 | |
| pve5 (EliteDesk G3) | 192.168.10.203 | |
| Juniper EX3400 | 192.168.10.50 | JunOS 23.4R2-S7.4 |
| quarkylab iDRAC | 192.168.10.20 | R730 svc tag 1S8WR22 |
| Jarvis iDRAC | 192.168.10.21 | R730 384GB |
| Nginx Proxy Manager | 192.168.10.181 | CT 101 on pve3 |
| Vaultwarden | 192.168.10.182 | CT 102 on pve3 |
| Grafana | 192.168.10.183 | CT 103 on pve3 |
| Pi-hole (primary) | 192.168.1.47 | pve1 LXC |
| Pi-hole (backup) | 192.168.1.170 | Raspberry Pi 4 |
| Ares (laptop) | DHCP / 192.168.10.100 wired | Tailscale: 100.124.118.63 |

---

## 🔗 Key Links

### Infrastructure
- [[Rack Layout]] — Physical layout, depth notes, thermal zones
- [[Power Distribution]] — Dual UPS bus diagram, load calculations
- [[Networking/Network Overview]] — Topology, VLANs, routing

### Compute
- [[Compute/Dell R730 - ML Node]] — Jarvis (iDRAC: 192.168.10.21)
- [[Compute/Dell R730 - General Node]] — quarkylab (iDRAC: 192.168.10.20)
- [[Compute/Small Node Cluster]] — pve1–pve5

### Storage & Virtualization
- [[Infrastructure/Storage]] — NetApp DS4246, drive inventory
- [[Infrastructure/Proxmox Cluster]] — Cluster config, node table, OPNsense
- [[Infrastructure/Services & VMs]] — All deployed/planned services

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
- [ ] Add Ares SSH key to pve1 (currently publickey-only, key not authorized)
- [ ] Fix EX3400 uplink ge-0/0/32: access port → proper trunk (VLANs not passing)
- [ ] DAC 10G uplink (xe-0/2/3 → UniFi SFP 2) — replace DAC with fiber optics
- [ ] OPNsense VM cutover (VM 100 on pve2 → replace Dream Router)
- [ ] VLAN segmentation implemented post-cutover
- [ ] Install both Dell R730s (quarkylab BIOS update in progress — CPU stepping mismatch)
- [ ] Stand up quarkylab + Jarvis as Proxmox nodes
- [ ] Deploy Wazuh SIEM on quarkylab
- [ ] Add all nodes to Grafana monitoring (node exporter)
- [ ] VoIP project (deferred — post core infra)
- [ ] CCNA study cadence established (VetTec 2.0 pathway)
