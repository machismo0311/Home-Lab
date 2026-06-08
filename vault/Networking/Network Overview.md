# 🌐 Network Overview
**Tags:** #networking #topology #vlans  
**Related:** [[Networking/Juniper EX3400-48P]] · [[Networking/UniFi USW-24-250W]] · [[Networking/Juniper EX2300-48P]] · [[Rack Layout]] · [[00 - Homelab MOC]]

---

## Physical Topology

```mermaid
flowchart TB
    WAN[🌍 WAN / ISP] --> OPN[OPNsense VM\nRouter-on-a-Stick\nProxmox Hosted]

    OPN <-->|Trunk — all VLANs| EX3400

    subgraph CORE["Core Switching Layer"]
        EX3400[Juniper EX3400-48P\nCore PoE+ Switch\n48-port / Dual PSU\nU40]
        DAC[0.25m SFP+ DAC\n10Gtek passive]
        USW[UniFi USW-24-250W\nAccess / PoE\nU39]
        EX2300[Juniper EX2300-48P\nSecondary / Lab\nU38]
        EX3400 <-->|DAC 10G uplink| USW
        EX3400 <-->|1G trunk| EX2300
    end

    subgraph COMPUTE["Compute Nodes"]
        R730ML[Dell R730 ML\niDRAC + 4× 1G\nU18–19]
        R730GEN[Dell R730 General\niDRAC + 4× 1G\nU15–16]
        SM[SuperMicro CSE-219U\n4× 1G\nU13–14]
        G4A[EliteDesk G4 SFF A\n1G]
        G4B[EliteDesk G4 SFF B\n1G]
        G3A[EliteDesk G3 Mini A\n1G]
        G3B[EliteDesk G3 Mini B\n1G]
    end

    subgraph EDGE["Edge & IoT"]
        MAC[Mac mini 2011\nProxmox]
        RPI[Raspberry Pi 4\nPi-hole / HA]
        PHONES[Cisco CP-8841 ×5\nVoIP - planned]
        APS[UniFi APs\nWireless]
    end

    EX3400 --> R730ML
    EX3400 --> R730GEN
    EX3400 --> SM
    EX3400 --> G4A
    EX3400 --> G4B
    USW --> G3A
    USW --> G3B
    USW --> MAC
    USW --> RPI
    USW --> PHONES
    USW --> APS

    style EX3400 fill:#1a1a2e,color:#eee
    style OPN fill:#0f3460,color:#eee
    style R730ML fill:#16213e,color:#eee
```

---

## VLAN Plan

| VLAN ID | Name | Subnet | Purpose |
|---|---|---|---|
| 1 | Native/Default | — | Untagged (avoid in prod) |
| 10 | MGMT | 10.0.10.0/24 | iDRAC, switch OOB, UPS |
| 20 | COMPUTE | 10.0.20.0/24 | Proxmox hosts, VMs |
| 30 | STORAGE | 10.0.30.0/24 | NFS/iSCSI traffic isolation |
| 40 | SERVICES | 10.0.40.0/24 | Jellyfin, Vaultwarden, Uptime Kuma |
| 50 | IOT | 10.0.50.0/24 | Home Assistant, Frigate, IMUs |
| 60 | VOIP | 10.0.60.0/24 | CP-8841 phones, FreePBX |
| 70 | LAB | 10.0.70.0/24 | Experimental / CCNA lab |
| 99 | GUEST | 10.0.99.0/24 | Isolated guest WiFi |

> [!NOTE] Router-on-a-Stick
> OPNsense VM handles inter-VLAN routing via a single trunk link to EX3400. Each VLAN is a subinterface on the OPNsense uplink. See [[Networking/Juniper EX3400-48P]] for trunk config.

---

## Routing Architecture

```mermaid
flowchart LR
    subgraph PROXMOX["Proxmox Host"]
        OPN_VM[OPNsense VM]
        VMBR0[vmbr0\nTrunk bridge]
        OPN_VM <--> VMBR0
    end

    EX3400 <-->|802.1Q Trunk\nAll VLANs tagged| VMBR0

    OPN_VM -->|Routes between VLANs| FW{Firewall Rules}
    FW -->|Allow| INTER[Inter-VLAN traffic\nper policy]
    FW -->|Block| BLOCKED[IOT ↔ COMPUTE\nGUEST → all\netc.]

    OPN_VM --> WAN2[WAN uplink]
```

---

## DNS & DHCP

| Service | Host | VLAN |
|---|---|---|
| Pi-hole (primary DNS) | RPi 4 | 50 (IoT) / serves all |
| OPNsense DHCP | OPNsense VM | Per-VLAN |
| Local domain | `homelab.local` | All |

---

## Switching — Quick Reference

| Device | See Note | Role |
|---|---|---|
| Juniper EX3400-48P | [[Networking/Juniper EX3400-48P]] | Core, PoE+, dual PSU, 10G |
| UniFi USW-24-250W | [[Networking/UniFi USW-24-250W]] | Access, PoE+, UniFi managed |
| Juniper EX2300-48P | [[Networking/Juniper EX2300-48P]] | Secondary / lab isolation |

---

## DAC Interconnect

| Link | Cable | Speed |
|---|---|---|
| EX3400 ↔ USW-24 | 10Gtek 0.25m passive SFP+ DAC | 10 Gbps |
| EX3400 ↔ EX2300 | 1G copper (temp) → upgrade to DAC | 1 Gbps |

---

## Addresses — Static Assignments (MGMT VLAN 10)

| Device | IP | Notes |
|---|---|---|
| OPNsense | 10.0.10.1 | Gateway |
| EX3400-48P | 10.0.10.2 | |
| USW-24-250W | 10.0.10.3 | |
| EX2300-48P | 10.0.10.4 | |
| R730 ML iDRAC | 10.0.10.10 | |
| R730 Gen iDRAC | 10.0.10.11 | |
| SuperMicro IPMI | 10.0.10.12 | |
| RPi 4 | 10.0.10.20 | |
| Mac mini | 10.0.10.21 | |
