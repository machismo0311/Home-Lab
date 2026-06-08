# 🖥️ Homelab — Master Map of Content
> **Operator:** Kyle Mason (`machismo`) · **Location:** Vermilion / Greater Cleveland, OH  
> **Cabinet:** NetFRAME CS9000 42U · **Last Updated:** 2026-06-08

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
      [[Compute/SuperMicro CSE-219U]]
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
| U36–U34 | HP EliteDesk G4 SFF ×2 (3U shelf) | Proxmox small nodes |
| U33–U31 | HP EliteDesk G3 Mini ×2 (3U shelf) | Proxmox small nodes |
| U30 | Mac mini + RPi 4 (1U shelf) | Pi-hole / Home Assistant |
| U22–U19 | *Open / cable mgmt* | — |
| U19–U18 | Dell R730 #1 — ML Node | Fernanda's CUDA workloads |
| U16–U15 | Dell R730 #2 — General | General compute |
| U14–U13 | SuperMicro CSE-219U | Mixed workloads |
| U12–U7 | NetApp DS4246 (4U) | JBOD storage shelf |
| U6 | Furman RP-8 | Power conditioning |
| U5–U4 | Tripp Lite SMART1500VA | UPS — top half bus |
| U2–U1 | Middle Atlantic UPS-2200R | UPS — bottom half / ML bus |

---

## 🔗 Key Links

### Infrastructure
- [[Rack Layout]] — Physical layout, depth notes, thermal zones
- [[Power Distribution]] — Dual UPS bus diagram, load calculations
- [[Networking/Network Overview]] — Topology, VLANs, routing

### Compute
- [[Compute/Dell R730 - ML Node]] — Fernanda's CUDA box
- [[Compute/Dell R730 - General Node]] — General workloads
- [[Compute/SuperMicro CSE-219U]] — Mixed workloads
- [[Compute/Small Node Cluster]] — EliteDesk + Mac mini + RPi

### Storage & Virtualization
- [[Infrastructure/Storage]] — NetApp DS4246, drive inventory
- [[Infrastructure/Proxmox Cluster]] — Cluster config, VM layout
- [[Infrastructure/Services & VMs]] — All planned/running services

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
- [x] Juniper EX3400 acquired & Junos fundamentals covered
- [x] EX3400 SSH issue resolved & switch on production network (2026-06-05)
- [ ] DAC 10G uplink (xe-0/2/3 → UniFi SFP 2) — replace DAC with fiber optics
- [ ] Install both Dell R730s (rear panel removed — depth issue resolved)
- [ ] Cable management pass after all hardware seated
- [ ] Stand up Proxmox cluster (full mesh)
- [ ] OPNsense VM router-on-a-stick live
- [ ] VLAN segmentation implemented
- [ ] Core services live: Vaultwarden, Jellyfin, Pi-hole, Uptime Kuma
- [ ] VoIP project (deferred — post core infra)
- [ ] CCNA study cadence established (VetTec 2.0 pathway)
