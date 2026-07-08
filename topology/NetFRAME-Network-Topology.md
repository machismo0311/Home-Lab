# NetFRAME Home Lab — Network Topology Reference

> **Public edition.** Physical MAC addresses, drive serial numbers, and out-of-band credential detail have been generalized. This is the shareable topology reference for the `machismo0311/Home-Lab` repository.

| Field | Value |
|---|---|
| **Document** | NetFRAME Network Topology & Systems Reference |
| **Owner** | Kyle Mason (`machismo0311`) — Vermilion / Greater Cleveland, OH |
| **Classification** | Public / Sanitized (MACs → vendor only; serials omitted) |
| **Version** | 1.0 |
| **Generated** | 2026-07-08 |
| **Method** | Live discovery (nmap, Proxmox API, SSH host facts, Headscale, ZFS/StorCLI) reconciled against the Home-Lab Obsidian vault |
| **Scope** | Every host, VLAN, subnet, link, service, storage pool, and overlay path on the `192.168.10.0/24` estate and its segmented VLANs |
| **Site** | Single site — residential lab, Vermilion OH |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Conventions & Legend](#2-conventions--legend)
3. [Layer 1 — Physical](#3-layer-1--physical)
4. [Layer 2 — Data Link (Switching & VLANs)](#4-layer-2--data-link-switching--vlans)
5. [Layer 3 — Network (Addressing, Routing, DNS, DHCP)](#5-layer-3--network-addressing-routing-dns-dhcp)
6. [Overlay — Headscale Mesh VPN](#6-overlay--headscale-mesh-vpn)
7. [Compute & Virtualization — km-cluster](#7-compute--virtualization--km-cluster)
8. [Storage Architecture](#8-storage-architecture)
9. [Services & Application Layer](#9-services--application-layer)
10. [AI / LLM Platform](#10-ai--llm-platform)
11. [Security Architecture](#11-security-architecture)
12. [Data-Flow Walkthroughs ("packet walks")](#12-data-flow-walkthroughs-packet-walks)
13. [End-to-End Connection Matrix](#13-end-to-end-connection-matrix)
14. [Observations, Drift & Recommendations](#14-observations-drift--recommendations)
15. [Failure-Domain / Blast-Radius Analysis](#15-failure-domain--blast-radius-analysis)
16. [Appendices](#16-appendices)

---

## 1. Executive Summary

**NetFRAME** is a single-site, 42U production-grade home lab built around a **7-node Proxmox VE 9.2.3 hyper-converged cluster** (`km-cluster`), a **Juniper-cored, VLAN-segmented switched fabric**, and a **24-bay ZFS storage node** providing NFS and Proxmox Backup Server services. It runs a full self-hosted platform: reverse-proxied web services with automated TLS, a Prometheus/Grafana/Loki observability stack, drive-health telemetry across ~50 disks, a Wazuh SIEM, an internal ACME PKI, a password vault, and a **GPU-accelerated private LLM platform** (RTX 8000 + dual RTX 6000, ~96 GB of VRAM) with a custom OpenAI-compatible router that transparently escalates to the Claude API.

At a glance:

| Domain | Count / Figure |
|---|---|
| Proxmox nodes (cluster) | 7 (voting, quorate 7/7) |
| Standalone hypervisor | 1 (pve1, Mac Mini — Pi-hole host) |
| VMs / LXC containers | 2 VMs + 6 LXCs |
| Managed switches | 3 (EX3400 core, USW-24 access, EX2300 lab) |
| VLANs defined | 7 (IDs 1/20/30/40/50/60/70) |
| Physical GPUs | 3 (1× RTX 8000 48 GB, 2× RTX 6000 24 GB) |
| Aggregate VRAM | ~96 GB |
| Aggregate RAM (cluster) | ~1.5 TB |
| ZFS raw capacity (Randy) | 36.7 TB (~23 TB usable, 4× RAIDZ2) |
| Backup capacity (PBS) | 24.6 TB datastore |
| Monitored drives | ~50 (Scrutiny/SMART) |
| Overlay VPN nodes | 9 (Headscale `100.64.0.0/10`) |
| UPS units | 2 (split-bus, ~2220 W combined) |

**Edge model:** a UniFi Dream Router is the WAN edge (upstream `192.168.1.0/24`); **OPNsense** (a VM on `pve2`) is the LAN router / firewall / DHCP for `192.168.10.0/24` and inter-VLAN gateway. This is a deliberate **double-NAT** design isolating the lab LAN behind its own firewall.

---

## 2. Conventions & Legend

### Naming
- **Nodes** carry personal names (QuarkyLab, Jarvis, Randy, Ares) or role-numbers (pve2–pve5, pve1).
- **Cable/port labels** follow `[DEVICE]-[PORT]` with TIA-606 color coding; structured runs land on Leviton patch panels.
- Internal DNS zone: **`*.netframe.local`** (step-ca issued TLS). Public/edge DNS: **`*.kylemason.org`** (Cloudflare, DNS-only "grey-cloud" A records → NPM).

### VLAN color key (used throughout diagrams)

| VLAN | ID | Subnet | Role | Color |
|---|---|---|---|---|
| Management | 1 | `192.168.10.0/24` | Proxmox, services, switch mgmt | ⬛ slate |
| Trusted / OOB | 20 | `192.168.20.0/24` | iDRAC / IPMI, jump host | 🟪 violet |
| Servers | 30 | `192.168.30.0/24` | NFS / PBS / GPU egress | 🟩 green |
| IoT | 40 | `192.168.40.0/24` | Smart-home, IMUs | 🟨 amber |
| VoIP | 50 | `192.168.50.0/24` | CP-8841 phones, FreePBX | 🟦 blue |
| Guest | 60 | `192.168.60.0/24` | Isolated guest WiFi | 🟧 orange |
| Lab | 70 | `192.168.70.0/24` | CCNA / experimental | 🟥 red |

### Status glyphs
🟢 verified live this session · 🟡 configured, partially verified · 🔴 planned / down · ⚠️ finding — see §14

---

## 3. Layer 1 — Physical

### 3.1 Cabinet

| Field | Value |
|---|---|
| Model | NetFRAME **CS9000**, 42U, 24″ usable internal depth |
| Rear panel | **Removed** — Dell R730s are ~28″ deep and overhang; maintain 6–8″ rear wall clearance for airflow |
| Location | Vermilion / Greater Cleveland, OH |
| Structured cabling | 2× Leviton CAT6 patch panels (U41–U42), vertical lacing both sides, horizontal managers at U37 & U7 |

### 3.2 Rack elevation (top → bottom)

```
U42  Leviton Patch Panel #1 ─────────────── CAT6 front patching
U41  Leviton Patch Panel #2
U40  Juniper EX3400-48P (PoE+)  ─────────── CORE switch · dual PSU · 4×10G SFP+ · 2×40G QSFP+
U39  UniFi USW-24-250W (PoE+)   ─────────── ACCESS switch / AP aggregation
U38  Juniper EX2300-48P         ─────────── Secondary / lab switch
U37  ── horizontal cable manager ──
U36–34  HP EliteDesk G4 SFF ×2 (3U shelf)   pve2 (i7-8700/32G) · pve3 (i7-8700/48G)
U33–31  HP EliteDesk G3 Mini ×2 (3U shelf)  pve4 · pve5 (i5-7500T/32G)
U30  Mac mini (2011) + RPi 4 (1U)           pve1 standalone · Pi-hole
U29–21  ── open / cable reserve ──
U20–18  Dell R730 #1 "QuarkyLab" (2U)        ML node · RTX 8000 48GB · rear panel removed
U17  ── spacer ──
U16–15  Dell R730 #2 "Jarvis" (2U)           LLM node · 2× RTX 6000 · rear panel removed
U14–13  SuperMicro CSE-219U "Randy" (2U)     PBS / ZFS / Jellyfin
U12–8   NetApp DS4246 (4U JBOD)              24-bay SAS expansion shelf
U7   ── horizontal cable manager ──
U6   Furman RP-8 power conditioner
U5–4  Tripp Lite SMART1500VA (UPS B)         top-half bus
U3   ── spacer ──
U2–1  Middle Atlantic UPS-2200R (UPS A)      bottom / ML bus · rack anchor
```

### 3.3 Structured cabling & key physical links

| From | Port | To | Port | Media | Speed | Notes |
|---|---|---|---|---|---|---|
| EX3400 | `ge-0/0/46` | UniFi USW-24 | Port 24 | Copper | 1 G | **802.1Q trunk** (native 1 + tagged 20/30/40/50/60/70) |
| EX3400 | `ge-0/0/45` | EX2300-48P | uplink | Copper | 1 G | Trunk, all VLANs |
| EX3400 | `ge-0/0/32` | UniFi USW-24 | — | Copper | 1 G | Legacy access uplink, VLAN 1 only |
| EX3400 | `ge-0/0/38` | APC AP7901 PDU | — | Copper | 1 G | Managed PDU, VLAN 1 |
| EX3400 | `xe-0/2/0` | Randy `nic3` (Mellanox ConnectX-3) | — | **10 G SFP+** | 10 G | Storage/NFS data path |
| EX3400 | `xe-0/2/2` | Jarvis `enp132s0` (ConnectX 10G) | vmbr1 | **10 G SFP+** | 10 G | Access VLAN 30 (dedicated storage/egress leg) |
| EX3400 | `xe-0/2/3` | UniFi SFP 2 (DAC) | — | 10 G DAC | — | ⚠️ **DOWN** — 10 G vs 1 G EEPROM speed mismatch |
| EX3400 | `ge-0/0/24` | QuarkyLab `nic2` | vmbr0 | Copper | 1 G | Trunk (native 1 + tagged 30) |
| EX3400 | `ge-0/0/22` | Jarvis `nic2` | vmbr0 | Copper | 1 G | Native VLAN 1 (mgmt/corosync); tagged-30 now vestigial |
| EX3400 | `ge-0/0/30·32·44` | (OOB) | — | Copper | 1 G | **Tagged VLAN 20 only** → iDRAC/IPMI |
| Ares | `enp0s31f6` | EX3400 | — | Copper | 1 G | Primary mgmt leg (⚠️ currently link-down) |
| Ares | `enp0s31f6.20` | — | — | 802.1Q | — | VLAN 20 OOB jump leg |

### 3.4 Power distribution — split-bus

Wall → **Furman RP-8** conditioner (U6) → two independent UPS buses:

| Bus | UPS | Capacity | Load zone | Monitoring |
|---|---|---|---|---|
| **A** (bottom / ML) | Middle Atlantic **UPS-OL2200R** | 2200 VA / ~1320 W | Both R730s, Randy, DS4246 | NUT `snmp-ups` via SNMP card `192.168.10.180` (CyberPower OL rebrand, enterprise OID 3808) |
| **B** (top) | Tripp Lite **SMART1500VA** | 1500 VA / ~900 W | EX3400, USW-24, EX2300, EliteDesks, Mac mini | NUT `usbhid-ups` via USB → pve3 (`09ae:2012`) |

Both are exposed by **NUT 2.8.1** on `pve3` (`MODE=netserver`, TCP `3493`) and surfaced as live widgets on Homepage via a PeaNUT bridge.

> ⚠️ **Capacity watch:** UPS A carries both GPU R730s. RTX 8000 alone can pull ~260 W under CUDA; with Jarvis's 2× RTX 6000 online, full ML load can push UPS A toward/over its 1320 W continuous rating. Meter and stagger heavy jobs.

### 3.5 Thermal zones

`Zone 1` Networking (U38–U42) · `Zone 2` Small compute (U30–U37) · `Zone 3` **Heavy compute / high heat** (U13–U20, both R730s + Randy) · `Zone 4` Storage & power (U1–U12). Front-to-back airflow; R730 GPU fans are actively managed (see §7.5).

---

## 4. Layer 2 — Data Link (Switching & VLANs)

### 4.1 Switch fabric

| Device | Mgmt IP | Model | OS / Ver | U | Role |
|---|---|---|---|---|---|
| **EX3400-48P** | `192.168.10.50` | Juniper EX3400 | JunOS **23.4R2-S7.4** | U40 | **Core** — 48× 1G PoE+, 4× 10G SFP+, 2× 40G QSFP+, dual PSU, STP root |
| UniFi USW-24-250W | (UniFi-managed) | Ubiquiti | UniFi | U39 | Access / AP aggregation; Port 24 trunk |
| EX2300-48P | (via trunk) | Juniper EX2300 | JunOS | U38 | Secondary / lab isolation |
| UniFi Dream Router | `192.168.1.1` | Ubiquiti UDR | UniFi | — | **WAN edge** (upstream of OPNsense) |

**Core switch details (EX3400):**
- Management via `irb.10` → `192.168.10.50/24`, static default `0.0.0.0/0 → 192.168.10.1` (OPNsense).
- **STP:** RSTP, bridge-priority `4096` (deliberate root).
- **ELS gotcha (documented, live):** `native-vlan-id` must be set at the **physical-interface** level, *not* under `unit 0 family ethernet-switching`. Misplacement previously caused a trunk outage.
- Renumbered `.2 → .50` (2026-06-05) after an IP conflict.
- ⚠️ SSH to the switch is **password-only for `mason`** (key-auth broken — see `EX3400-SSH-Auth-Failure-RCA.md`); switch config here is reconciled from the vault, not pulled live this session.

### 4.2 VLAN matrix (EX3400 ELS, live since 2026-06-25)

| VLAN name | ID | Subnet | Gateway | L3 SVI | Populated? |
|---|---|---|---|---|---|
| `default` | 1 | `192.168.10.0/24` | `192.168.10.1` (OPNsense) | irb.10 on switch | ✅ dense |
| `trusted` | 20 | `192.168.20.0/24` | `192.168.20.1` | OPNsense | ✅ 3 BMCs + Ares leg |
| `servers` | 30 | `192.168.30.0/24` | `192.168.30.1` | OPNsense | ✅ 3 GPU/storage nodes |
| `iot` | 40 | `192.168.40.0/24` | `192.168.40.1` | OPNsense | 🟡 sparse |
| `voip` | 50 | `192.168.50.0/24` | `192.168.50.1` | OPNsense | 🔴 planned (FreePBX deferred) |
| `guest` | 60 | `192.168.60.0/24` | `192.168.60.1` | OPNsense | 🟡 guest WiFi |
| `lab` | 70 | `192.168.70.0/24` | `192.168.70.1` | OPNsense | 🟡 sandbox node |

### 4.3 Trunk / access port map (EX3400)

| Port | Attachment | Mode | VLANs |
|---|---|---|---|
| `ge-0/0/22` | Jarvis `nic2` (onboard 1G) | Trunk | native 1 (+ tagged 30, vestigial) |
| `ge-0/0/24` | QuarkyLab `nic2` | Trunk | native 1 + tagged 30 |
| `ge-0/0/30, /32, /44` | iDRAC / IPMI OOB | Access (tagged) | **20 only** |
| `ge-0/0/38` | APC AP7901 PDU | Access | 1 |
| `ge-0/0/45` | EX2300 uplink | Trunk | all |
| `ge-0/0/46` | UniFi USW-24 Port 24 | Trunk | native 1 + tagged 20/30/40/50/60/70 |
| `xe-0/2/0` | Randy `nic3` (10G) | (trunk/data) | 1 + 30 |
| `xe-0/2/2` | Jarvis `enp132s0` (10G) | Access | **30** |
| `xe-0/2/3` | UniFi SFP2 DAC | — | ⚠️ down (EEPROM mismatch) |

### 4.4 MAC / OUI inventory (VLAN 1, live ARP)

> Full addresses retained in this master; the public edition shows vendor OUI only. `bc:24:11:*` is the **Proxmox VE** locally-assigned prefix (auto-generated VM/CT vNICs).

| IP | MAC | Vendor (OUI) | Identity |
|---|---|---|---|
| .1 | `(OUI only)` | Proxmox vNIC | OPNsense VM 100 (LAN gw) |
| .2 | `(OUI only)` | Ubiquiti | UniFi USW-24 mgmt |
| .31 | `(OUI only)` | Dell | Jarvis (R730) |
| .50 | `(OUI only)` | Juniper | EX3400 core |
| .148 | `(OUI only)` | Proxmox vNIC | Homepage CT 106 |
| .176 | `(OUI only)` | Ubiquiti | UniFi AP |
| .177 | `(OUI only)` | Proxmox vNIC | Pi-hole (on pve1) |
| .179 | `(OUI only)` | Dell | QuarkyLab (R730) |
| .180 | `(OUI only)` | CyberPower | UPS A SNMP card |
| .181–.186 | `bc:24:11:*` | Proxmox vNIC | NPM/Vault/Grafana/Wazuh/OpenWebUI/Headscale |
| .187 | `(OUI only)` | Mellanox | Randy `nic3` (10G) |
| .193 | `(OUI only)` | Apple | pve1 Mac Mini |
| .201 | `(OUI only)` | HP | pve3 |
| .202 | `(OUI only)` | HP | pve4 |
| .203 | `(OUI only)` | HP | pve5 |
| .204 | `(OUI only)` | Intel/HP | pve2 |

Client/IoT devices also seen: Samsung (`.111`), Amazon (`.112`), Intel (`.191`), plus assorted DHCP clients. Full table in [Appendix D](#appendix-d--full-mac--oui-registry).

---

## 5. Layer 3 — Network (Addressing, Routing, DNS, DHCP)

### 5.1 Edge / WAN

```
Internet ─▶ ISP ─▶ UniFi Dream Router (WAN edge, 192.168.1.0/24) ─▶ OPNsense VM100 (192.168.10.1) ─▶ LAN 192.168.10.0/24 + VLANs
                              │                                            │
                              └── provides WiFi + upstream NAT             └── LAN firewall / DHCP / inter-VLAN routing (double-NAT)
```

- **OPNsense v25.7** (VM 100 on pve2) is the authoritative LAN router/firewall/DHCP and inter-VLAN gateway. `onboot=1`.
- The **UDR** remains the WAN edge and WiFi provider on `192.168.1.x`; the lab sits behind a second NAT/firewall boundary.

### 5.2 Static IP registry — VLAN 1 (`192.168.10.0/24`)

| IP | Host | Role |
|---|---|---|
| .1 | OPNsense | LAN gateway / FW / DHCP (VM 100, pve2) |
| .2 | UniFi USW-24 | Access switch mgmt |
| .31 | **Jarvis** | R730 LLM node |
| .50 | EX3400 | Core switch |
| .100 | Ares (wired) | Admin workstation `enp0s31f6` |
| .148 | Homepage | LXC 106 (pve3) |
| .177 | Pi-hole | LXC 103 on **pve1** (Mac Mini) |
| .179 | **QuarkyLab** | R730 ML node |
| .180 | UPS A SNMP | Middle Atlantic OL2200R card |
| .181 | Nginx Proxy Manager | LXC 101 (pve3) |
| .182 | Vaultwarden | LXC 102 (pve3) |
| .183 | Grafana/Prometheus/Loki/InfluxDB/Scrutiny | LXC 103 (pve3) |
| .184 | Wazuh SIEM | VM 104 (QuarkyLab) |
| .185 | Open WebUI | LXC 107 (pve3) |
| .186 | Headscale | LXC 105 (pve3) |
| .187 | **Randy** | SuperMicro PBS / ZFS / Jellyfin |
| .193 | **pve1** | Mac Mini standalone (Pi-hole host) |
| .199 | Ares (WiFi) | Admin workstation `wlp2s0` |
| .201–.204 | pve3 / pve4 / pve5 / pve2 | Cluster nodes |

### 5.3 VLAN 20 (Trusted / OOB) & VLAN 30 (Servers)

| IP | Host | VLAN | Note |
|---|---|---|---|
| `192.168.20.20` | QuarkyLab iDRAC | 20 | Moved to OOB 2026-07-03; credentials rotated to vault |
| `192.168.20.21` | Jarvis iDRAC | 20 | " |
| `192.168.20.22` | Randy IPMI (ch 1) | 20 | Enabling VLAN zeroes the IP — re-apply `ipmitool lan set 1 ipaddr` |
| `192.168.20.199` | Ares OOB leg | 20 | `enp0s31f6.20` jump host |
| `192.168.30.179` | QuarkyLab | 30 | NFS/PBS/egress (dual-homed) |
| `192.168.30.187` | Randy | 30 | NFS export + PBS + egress |
| `192.168.30.31` | Jarvis | 30 | On dedicated 10G ConnectX (`vmbr1`) |
| `192.168.30.1` | OPNsense | 30 | Servers gateway |

### 5.4 Routing — per-node default gateways (live)

| Node | Default gateway | Egress iface | Note |
|---|---|---|---|
| pve2 | `192.168.10.1` | vmbr1 | ✅ correct (OPNsense) |
| pve3 | `192.168.1.1` | vmbr0 | ⚠️ **onlink to UDR** — off-subnet, see §14-F1 |
| pve4 | `192.168.1.1` | vmbr0 | ⚠️ same |
| pve5 | `192.168.1.1` | vmbr0 | ⚠️ same |
| QuarkyLab | `192.168.30.1` | vmbr0.30 | ✅ VLAN 30 egress |
| Jarvis | `192.168.30.1` | vmbr1 | ✅ VLAN 30 egress (10G) |
| Randy | `192.168.30.1` | vmbr0.30 | ✅ VLAN 30 egress |
| Ares | `192.168.10.1` | wlp2s0 (WiFi) | wired leg down → WiFi is active default |

> **Split-personality routing is by design at the storage tier** (GPU/storage nodes egress via VLAN 30) but **inconsistent at the small-node tier** (pve3/4/5 point at the UDR `192.168.1.1` directly rather than OPNsense `192.168.10.1`). See finding **F-1**.

### 5.5 DNS architecture

```
Clients ─▶ Pi-hole (192.168.10.177, FTL v6, LXC on pve1) ─▶ upstream resolvers
   │
   ├── Local zone: *.netframe.local  (llm./chat. → NPM 192.168.10.181)
   └── Ad/tracker blocking + LAN name resolution

Public: *.kylemason.org ─▶ Cloudflare (DNS-only, grey cloud) A → 192.168.10.181 (NPM) ─▶ internal services
Overlay: Tailscale/Headscale MagicDNS (100.100.100.100) — disabled on nodes (--accept-dns=false) to avoid resolv.conf clobber
```

- **Pi-hole** is the LAN DNS server and sink for ad/tracker blocking; it also serves internal `*.netframe.local` records (e.g. `llm.netframe.local`, `chat.netframe.local` → NPM `.181`, which resolve **only** for Pi-hole clients).
- ⚠️ Tailscale/Headscale overwrites `/etc/resolv.conf` on nodes; policy is `tailscale set --accept-dns=false` + `nameserver 192.168.10.177` before any `apt` operation.

### 5.6 DHCP

OPNsense (`192.168.10.1`) serves DHCP per VLAN. Most infrastructure uses static/reservation; several LXCs use DHCP with effectively fixed leases (NPM `.181`, Vaultwarden `.182`, Grafana `.183`, Homepage `.148`), while Headscale (`.186`) and Open WebUI (`.185`) are configured static in the CT config.

---

## 6. Overlay — Headscale Mesh VPN

Self-hosted **Headscale v0.29.1** (LXC 105 on pve3, `192.168.10.186:8080`) replaces the Tailscale SaaS control plane. Tailnet CGNAT range `100.64.0.0/10`.

| Tailnet IP | Node | User | Tags | State |
|---|---|---|---|---|
| `100.64.0.1` | Ares | tagged-devices | tag:ssh | offline (laptop) |
| `100.64.0.2` | Randy | tagged-devices | tag:ssh | 🟢 online |
| `100.64.0.3` | pve5 | tagged-devices | tag:ssh | 🟢 online |
| `100.64.0.4` | pve4 | tagged-devices | tag:ssh | 🟢 online |
| `100.64.0.5` | pve3 | tagged-devices | tag:ssh | 🟢 online |
| `100.64.0.6` | Jarvis | tagged-devices | tag:ssh | 🟢 online |
| `100.64.0.7` | QuarkyLab | tagged-devices | tag:ssh | 🟢 online |
| `100.64.0.8` | pve1 | tagged-devices | tag:ssh | 🟢 online |
| `100.64.0.9` | FUS22-009897 (Fernanda's Mac) | fernanda | — | offline |

> **Migration note:** QuarkyLab + Fernanda's Mac must migrate together in Headscale Phase 2 — do not migrate one without the other.

---

## 7. Compute & Virtualization — km-cluster

### 7.1 Cluster & quorum

**km-cluster** — Proxmox VE **9.2.3**, Corosync ring over VLAN 1 (kept on stable L2 deliberately; **not** moved to VLAN 30). Quorate **7/7**.

| Corosync ID | Node | Ring address |
|---|---|---|
| 0x1 | pve2 | 192.168.10.204 |
| 0x2 | pve5 | 192.168.10.203 |
| 0x3 | pve4 | 192.168.10.202 |
| 0x4 | pve3 | 192.168.10.201 (local) |
| 0x5 | QuarkyLab | 192.168.10.179 |
| 0x6 | Jarvis | 192.168.10.31 |
| 0x7 | Randy | 192.168.10.187 |

### 7.2 Node hardware inventory

| Node | Chassis | CPU | RAM (usable) | GPU | Kernel | Notes |
|---|---|---|---|---|---|---|
| pve2 | HP EliteDesk 800 G4 SFF | i7-8700 | 31 GB | — | 7.0.12-1-pve | Hosts OPNsense VM 100, step-ca |
| pve3 | HP EliteDesk 800 G4 SFF | i7-8700 | 46 GB | — | 7.0.12-1-pve | Service host (6 LXCs) |
| pve4 | HP EliteDesk 800 G3 Mini | i5-7500T | 31 GB | — | 7.0.12-1-pve | |
| pve5 | HP EliteDesk 800 G3 Mini | i5-7500T | 31 GB | — | 7.0.12-1-pve | |
| **QuarkyLab** | Dell R730 | 2× E5-2699 v4 | 503 GB LRDIMM | **RTX 8000 48 GB** | **6.14.11-9-pve** (pinned) | ML / DUNE agent; Wazuh VM 104 |
| **Jarvis** | Dell R730 | 2× E5-2687W v4 | 377 GB LRDIMM | **2× RTX 6000 (48 GB)** | **6.14.11-9-pve** (pinned) | LLM inference; 10G ConnectX |
| **Randy** | SuperMicro CSE-219U / X10DRU-i+ | 2× E5-2690 v4 | 125 GB ECC | RX 580 8 GB (transcode) | 7.0.12-1-pve | PBS / ZFS / Jellyfin; Mellanox 10G |
| pve1 | Mac Mini (2011) | — | — | — | — | **Standalone** (not in cluster); Pi-hole host |

> **Kernel pinning:** QuarkyLab and Jarvis are pinned to **6.14.11-9-pve** via `GRUB_DEFAULT` — 6.17+ breaks the NVIDIA 550.163.01 stack. **Never** run kernel upgrades or change GRUB default on either GPU node.

### 7.3 Virtual machines

| VMID | Name | Host | vCPU/RAM | IP | onboot | Notes |
|---|---|---|---|---|---|---|
| 100 | OPNsense | pve2 | —/4 GB | 192.168.10.1 | ✅ | LAN router/FW/DHCP v25.7 |
| 104 | Wazuh | QuarkyLab | —/16 GB | 192.168.10.184 | ✅ | SIEM; ⚠️ **no qemu-guest-agent** → host reboot corrupts indexer (recovery in §11) |

### 7.4 LXC containers (all on pve3 unless noted)

| CTID | Name | vCPU / RAM / disk | IP | onboot | Payload |
|---|---|---|---|---|---|
| 101 | nginx-proxy | 2 / 512M / 8G | 192.168.10.181 | ✅ | Nginx Proxy Manager (Docker-in-LXC) |
| 102 | vaultwarden | 2 / 512M / 10G | 192.168.10.182 | ✅ | Vaultwarden (Docker) |
| 103 | grafana | 2 / 2G / 20G | 192.168.10.183 | ✅ | Grafana + Prometheus + Loki + InfluxDB + Scrutiny |
| 105 | headscale | 1 / 512M / 4G | 192.168.10.186 | ✅ | Headscale control plane (static, gw .10.1) |
| 106 | homepage | 1 / 512M / 8G | 192.168.10.148 | ✅ | Homepage dashboard + PeaNUT |
| 107 | openwebui | 4 / 4G / 16G | 192.168.10.185 | ✅ | Open WebUI (native pip, static, gw .10.1) |

> CTs 101/102/103/106 run **Docker inside the LXC** (note the `172.17.0.0/16`+`172.18.0.0/16` bridges on those containers). NPM's admin `:81` is firewalled to Ares only (`DOCKER-USER`, remediation F-05).

### 7.5 GPU inventory & thermal control

| Node | GPU(s) | VRAM | Driver | Fan control |
|---|---|---|---|---|
| QuarkyLab | 1× Quadro RTX 8000 | 46080 MiB | 550.163.01 | Third-party PCIe fan response **Disabled** (quiet baseline) |
| Jarvis | 2× Quadro RTX 6000 | 24576 MiB ea. | 550.163.01 | **`gpu-fan-control` daemon** — closed-loop nvidia-smi → ipmitool curve (15 %→100 %), failsafe-to-auto on crash |

> R730 iDRAC has **no GPU-temp visibility**, so the stock options are "loud fixed ramp" or "quiet but won't ramp." Jarvis's daemon closes that loop in-band. This is the "quiet 48 GB inference box in a bedroom-adjacent rack" trick.

---

## 8. Storage Architecture

### 8.1 Randy — primary ZFS (`datastore`)

**36.7 TB raw / ~23 TB usable**, 4× RAIDZ2 vdevs, `ONLINE`, 0 errors, last resilver 2026-07-07.

```
datastore (pool)
├─ raidz2-0  6× Toshiba AL15SEB18EQ 1.636TB 10K SAS   (sdi sdh sde sdf sdg sdj)
├─ raidz2-1  6× Toshiba AL15SEB18EQ 1.636TB 10K SAS   (sdk sdm sdn sdo sdp sdq)
├─ raidz2-2  6× Toshiba AL15SEB18EQ 1.636TB 10K SAS   (sdr sds sdt sdu sdv sdl)
└─ raidz2-3  4× Seagate ST2000NX0423 1.819TB SATA      (sdb sdc sdd sda)
```

- **Datasets:** `datastore` (46.4 G used, /datastore) · `datastore/quarkylab` (13.6 G, workspace, 2 TB quota).
- **Boot:** RAID-1 mirror, 2× Seagate ST200FM0053 185.8 GB SAS via **AVAGO 3108 MegaRAID** (`sdw` = SMC3108 virtual disk). *Do not reconfigure.*
- **HBA split:** boot mirror on AVAGO 3108; data drives on a **separate LSI 9207-8e in IT mode** (two different cards). JBOD mode may reset after reboot — re-run `storcli64 /c0 set jbod=on`.
- **Media:** Jellyfin serves `/datastore/media/{movies,tv,music}`.
- ⚠️ The AVAGO 3108 was relocated to a known-good PCIe slot (2026-07-01) after its original slot died — **original slot is DEAD, do not reuse**.

### 8.2 NetApp DS4246 (JBOD expansion)

24-bay 4U SAS shelf attached via the LSI 9207-8e (IT mode). **Live observation:** the shelf's drives currently enumerate as **duplicate serial pairs** (each physical serial appears twice) — this is **dual-path SAS multipath** through the shelf's two I/O modules presenting each physical disk on two SAS paths. Present population is **4 TB** class (Seagate `ST4000NM0063` + HGST `HUS724040ALS641`), a build-out in progress toward a bulk/media pool.

> ⚠️ **Drift vs. docs:** the CLAUDE.md/Rack notes describe the DS4246 as 2 TB-class; the live shelf is 4 TB-class and mid-buildout (`DS4246-Pool-Buildout-Plan-2026-07-07`). Configure `multipath`/dm before pooling to avoid using both paths as separate vdev members. See finding **F-3**.

### 8.3 Proxmox storage backends

| Storage | Type | Where | Size | Use |
|---|---|---|---|---|
| `local` | dir | each node | 71 G (pve3) | ISOs, templates, dumps |
| `local-lvm` | lvmthin | each node | 148 G | VM/CT root volumes |
| `randy-pbs` | pbs | Randy | 24.6 TB | Cluster backups |

### 8.4 Backup — Proxmox Backup Server

PBS **v4.2.2** on Randy (`https://192.168.10.187:8007`), ZFS-backed (36.7 T). LXCs 02:00 daily, VMs 03:00 daily, 7d + 4w retention. Nightly LXC job covers 101/102/103/105/106/107.

> ⚠️ **History:** the VLAN 30 migration silently repointed PBS storage to `.30.187` (only reachable from VLAN-30 nodes), stalling all VLAN-1 node backups at 0 B from 2026-07-02. **Fixed 2026-07-06** — `randy-pbs` repointed to Randy's dual-homed VLAN-1 IP `192.168.10.187`. **Keep PBS storage on `.10.187`.** (finding **F-4**)

---

## 9. Services & Application Layer

### 9.1 Reverse proxy & published services

**Nginx Proxy Manager** (CT 101, `192.168.10.181`, admin `:81` Ares-only) fronts all HTTP(S) services. TLS via **Cloudflare DNS-01** (Let's Encrypt), grey-cloud A records → `.181`.

| Hostname | Backend | Port | TLS | Auth |
|---|---|---|---|---|
| `vault.kylemason.org` | 192.168.10.182 | 80 | CF DNS-01 | Vaultwarden login |
| `grafana.kylemason.org` | 192.168.10.183 | 3000 | CF DNS-01 | Grafana |
| `homepage.kylemason.org` | 192.168.10.148 | 3000 | CF DNS-01 | Basic auth (kyle) |
| `wazuh.kylemason.org` | 192.168.10.184 | 443 | CF DNS-01 | Wazuh |
| `chat.netframe.local` | Open WebUI .185 | — | internal | admin acct |
| `llm.netframe.local` | Jarvis .31 | 8000 | HTTP | — (Pi-hole-scoped DNS) |

### 9.2 Observability stack (CT 103)

| Component | Port | Exposure | Function |
|---|---|---|---|
| Prometheus | 9090 | localhost-only (F-03) | 8 node exporters + peanut-ups |
| Grafana | 3000 | via NPM | Dashboards (v13.0.2) |
| Loki | 3100 | internal | Log aggregation |
| InfluxDB | 8086 | internal | Scrutiny backend |
| Scrutiny | 8080 | LAN | ~50 drives; collectors on Randy (43), QuarkyLab (7), Jarvis (1) via 6-h systemd timers |
| NUT (on pve3 host) | 3493 | 127.0.0.1 + .201 | 2 UPS units |
| PeaNUT (CT 106) | 8081 | Homepage bridge | UPS widgets |
| CrowdSec (pve3 host) | — | cloud console | Behavioral IPS |

### 9.3 Platform services

| Service | Host | Endpoint | Notes |
|---|---|---|---|
| Vaultwarden | CT 102 | vault.kylemason.org | Secrets of record (BMC creds, step-ca pw) |
| step-ca | pve2 | `:443` | Internal ACME PKI, `*.netframe.local` |
| Wazuh SIEM | VM 104 (QuarkyLab) | `192.168.10.184` | Migrated from pve2 |
| Homepage | CT 106 | homepage.kylemason.org | Live widgets: Proxmox/Pi-hole/Jellyfin/Scrutiny/UPS |
| Jellyfin | Randy (host) | `:8096` | v10.11.11; RX 580 transcode pending power cable |
| PBS | Randy | `:8007` | v4.2.2 |
| Headscale | CT 105 | `:8080` | Mesh VPN control plane |

### 9.4 Service dependency chain (abridged)

```
Cloudflare DNS ─▶ NPM (.181) ─▶ { Vaultwarden, Grafana, Homepage, Wazuh, Open WebUI }
Pi-hole (.177) ─▶ LAN name resolution + *.netframe.local
step-ca (pve2) ─▶ *.netframe.local TLS
NUT (pve3) ─▶ PeaNUT ─▶ Homepage
Prometheus (.183) ─▶ node-exporters ×8 + peanut ─▶ Grafana
Scrutiny (.183) ◀─ SMART collectors on Randy / QuarkyLab / Jarvis
PBS (Randy) ◀─ nightly vzdump of CTs/VMs
```

---

## 10. AI / LLM Platform

A genuinely differentiated subsystem: a **private, GPU-accelerated LLM stack with transparent cloud escalation.**

```
Open WebUI (CT107 .185, chat.netframe.local)
        │  OpenAI-compatible
        ▼
llm_router.service  (Jarvis :8000, FastAPI)         models: "local" | "rag" | "claude-*"
        ├─▶ Ollama (127.0.0.1:11434, 2× RTX 6000)  ── qwen2.5:72b (47 GB, tensor-split), qwen2.5:7b, nomic-embed-text
        ├─▶ RAG: nomic-embed-text + numpy cosine index over the Home-Lab vault (418 chunks) → [source] citations
        └─▶ Claude API fallback (claude-opus-4-8, adaptive thinking) on escalate:true / model=claude-* / local failure
                 (gated on ANTHROPIC_API_KEY in /etc/llm_router.env; unset ⇒ local-only)
```

| Item | Detail |
|---|---|
| Inference engine | Ollama v0.31.1, GPU-backed (2× RTX 6000, 48 GB total) |
| Flagship model | `qwen2.5:72b` (Q4 ~47 GB, tensor-split across both cards) |
| Context | `OLLAMA_NUM_CTX=8192` (72B Q4 barely fits 48 GB → minor CPU spill; 4096 = fully-GPU) |
| Router | `llm_router.service` (systemd, `Home-Lab/scripts/llm_router/`) |
| RAG rebuild | `rag_ingest.py` |
| Front door | NPM `llm.netframe.local` (proxy id 5) + Pi-hole local DNS |
| ML node | QuarkyLab RTX 8000 48 GB → Fernanda / DUNE RAG agent (ChromaDB/Qdrant TBD) |

> **Wow factor:** ask `chat.netframe.local` a question about the homelab and the `"rag"` model answers *grounded on your own Obsidian vault with citations* — served entirely on-prem, with a one-flag escalation to Claude Opus for hard queries.

---

## 11. Security Architecture

### 11.1 Segmentation posture

- **OOB isolation (Phase 1, 2026-07-03):** all three BMCs (iDRAC ×2 + IPMI) moved off flat VLAN 1 onto **VLAN 20** (tagged), credentials rotated into the password vault. Reachable only from Ares' `enp0s31f6.20` leg.
- **Servers VLAN 30 (2026-07-02):** GPU/storage nodes dual-homed; NFS/PBS/egress on VLAN 30, corosync/mgmt on VLAN 1.
- **Reverse-proxy chokepoint:** all web ingress via NPM; admin planes bound to localhost or Ares only (F-03/F-05).
- **Defense-in-depth:** Wazuh SIEM + CrowdSec IPS + step-ca internal PKI + Vaultwarden secrets.

### 11.2 Pentest remediation (tracked)

Findings F-03 (Prometheus/Loki localhost-only), F-05 (NPM `:81` Ares-only), OOB VLAN 20 + credential rotation — **complete & verified**. Pending: OPNsense rule to deny non-Ares → VLAN 20 and block BMC egress (Phase 1.5).

### 11.3 Operational safety notes (carried from runbooks)

- Wazuh VM 104 has **no qemu-guest-agent** → after any QuarkyLab reboot: `qm stop 104 && qm start 104`, wait ~4 min (healthy = dashboard 302→/login).
- Never touch pve2 network config without checking the June-15 outage history.
- Randy corosync singleton recovery after reboot; JBOD re-assert; PBS storage must stay on `.10.187`.

---

## 12. Data-Flow Walkthroughs ("packet walks")

**A) User opens `chat.netframe.local` and asks a grounded question**
1. Browser → Pi-hole (`.177`) resolves `chat.netframe.local` → NPM `.181` (Pi-hole-scoped record).
2. NPM (CT 101) reverse-proxies to Open WebUI (CT 107, `.185:8080`).
3. Open WebUI calls its OpenAI endpoint → `llm_router` on Jarvis `.31:8000` (`model:"rag"`).
4. Router embeds the query (nomic-embed-text on Ollama), cosine-searches the 418-chunk vault index, injects `[source]` context.
5. Ollama runs `qwen2.5:72b` tensor-split across both RTX 6000s → grounded answer with citations. (If `escalate:true`, router calls Claude Opus instead.)

**B) Nightly backup**
1. `pvescheduler` on each node triggers `vzdump` (02:00 CT / 03:00 VM).
2. Stream → PBS datastore on Randy `192.168.10.187:8007` (VLAN 1, dedup/ZFS).
3. Retention prune 7d + 4w.

**C) Storage/NFS traffic**
1. GPU nodes mount `/data` from Randy over **VLAN 30** (`192.168.30.187`) — 10 G path via `xe-0/2/0`.
2. Corosync + management deliberately stay on VLAN 1 (stable L2 ring).

**D) Admin reaches an iDRAC**
1. Ares tags VLAN 20 on `enp0s31f6.20` → EX3400 `ge-0/0/30/32/44` (tagged 20) → iDRAC `192.168.20.20-22`.
2. ⚠️ If the wired leg is down, VLAN 20 silently reroutes via WiFi→OPNsense; verify `ip route get 192.168.20.x` egresses `enp0s31f6.20` first.

---

## 13. End-to-End Connection Matrix

| Source | Destination | Path | Protocol/Port |
|---|---|---|---|
| Any LAN client | Internet | client → OPNsense `.10.1` → UDR `.1.1` → ISP | NAT (double) |
| LAN client | DNS | client → Pi-hole `.177` → upstream | 53 |
| Admin (Ares) | Cluster nodes | SSH (key) direct on VLAN 1 or via Headscale `100.64.0.x` | 22 |
| Admin (Ares) | BMCs | `enp0s31f6.20` → VLAN 20 → iDRAC/IPMI | 443/623 |
| GPU nodes | Randy NFS | VLAN 30 10G → `.30.187` | NFS |
| Cluster nodes | PBS | VLAN 1 → Randy `.10.187:8007` | HTTPS |
| Corosync | Cluster ring | VLAN 1 L2 (all 7 nodes) | 5405/udp |
| Internet user | Public services | Cloudflare → NPM `.181` → backend | 443 |
| Open WebUI | LLM | CT107 → Jarvis `.31:8000` → Ollama `:11434` | HTTP |
| Prometheus | Exporters | `.183` → 8 nodes `:9100` | HTTP |
| Scrutiny | SMART collectors | Randy/QuarkyLab/Jarvis → `.183:8080` | HTTP |
| NUT | UPS A / B | pve3 `:3493` ← SNMP `.180` / USB | 3493 |
| Nodes | Overlay | Headscale `.186:8080` control; WireGuard data | 8080/UDP |

---

## 14. Observations, Drift & Recommendations

| # | Severity | Finding | Recommendation |
|---|---|---|---|
| **F-1** | ⚠️ Medium | **Inconsistent default gateways:** pve3/4/5 default via `192.168.1.1` (UDR, off-subnet onlink) while pve2 uses OPNsense `.10.1`. Node egress bypasses the OPNsense firewall/logging. | Repoint pve3/4/5 default to `192.168.10.1` for consistent policy/logging, or document the intent explicitly. |
| **F-2** | 🟡 Low | **Ares wired mgmt leg (`enp0s31f6`) is link-down**; VLAN 20 OOB is currently unreachable and silently reroutes via WiFi→OPNsense. | Restore the wired leg before OOB/BMC work; verify `ip route get 192.168.20.x`. |
| **F-3** | ⚠️ Medium | **DS4246 drift + multipath:** shelf is 4 TB-class (docs say 2 TB) and drives enumerate as dual-path duplicates. | Configure `multipath`/dm before pooling; update Rack/CLAUDE docs to match live inventory. |
| **F-4** | ✅ Resolved | PBS storage was repointed to `.30.187` and broke VLAN-1 backups; fixed 2026-07-06 back to `.10.187`. | Keep PBS storage pinned to `.10.187`; add a monitor for backup age. |
| **F-5** | 🟡 Low | Wazuh VM 104 lacks qemu-guest-agent → unclean stop on host reboot corrupts the indexer. | Install `qemu-guest-agent`, set `--agent enabled=1`, one cold start. |
| **F-6** | 🟡 Low | `xe-0/2/3` DAC to UniFi down (10G/1G EEPROM mismatch). | Replace with a speed-matched SFP or accept as decommissioned. |
| **F-7** | 🟢 Info | VLANs 40/50/60/70 defined but lightly/not populated (VoIP/FreePBX deferred). | Populate or prune to keep the VLAN map honest. |
| **F-8** | ⚠️ Medium | **Open no-auth SOCKS5 proxy** on an Amazon IoT device (`192.168.10.112:1080`) — an unauthenticated open proxy on the flat LAN. | Identify the device, disable the proxy, or move it to the IoT VLAN 40 with egress-only firewalling. |

---

## 15. Failure-Domain / Blast-Radius Analysis

| Component | If it fails… | Blast radius | Mitigation present |
|---|---|---|---|
| pve2 | OPNsense down → **no LAN routing/DHCP/inter-VLAN** | Whole LAN loses gateway & internet | `onboot=1`; serial-console runbook; keep Ares wired leg |
| pve3 | 6 LXCs down → NPM/Vault/Grafana/Homepage/Headscale/OpenWebUI | All web ingress, secrets UI, dashboards, VPN control | PBS backups; onboot; migratable CTs |
| Randy | ZFS/PBS/NFS down | Backups + GPU-node NFS + Jellyfin | ZFS RAIDZ2 (2-disk fault/vdev); split HBAs |
| EX3400 | Core switch down | Entire wired fabric | Dual PSU; UPS B; EX2300/USW survive locally |
| UPS A | Power loss on ML bus | Both R730s + Randy + DS4246 | 2200 VA headroom; graceful shutdown target |
| pve1 (Mac Mini) | Pi-hole down | LAN DNS/ad-block; `*.netframe.local` | Secondary resolver `1.1.1.1` in resolv.conf |
| Corosync ring | Partition | Cluster loses quorum | 7 votes on stable VLAN-1 L2; ring not moved to VLAN 30 |

---

## 16. Appendices

### Appendix A — Live discovery method
- Host discovery: `nmap -sn 192.168.10.0/24`
- Service/version: `nmap -sT -sV -p- --open` (results in Appendix C)
- Cluster: `pvesh get /cluster/resources`, `pvecm status`, `pct config`, `qm list`
- Facts: SSH host `ip/route/bridge`, `zpool status`, `lsblk`, `nvidia-smi`, `ollama list`
- Overlay: `headscale nodes list`; MAC OUI from `nmap-mac-prefixes`

### Appendix B — Runbook cross-reference (Home-Lab vault)
`VLAN-Activation-2026-06-25` · `VLAN30-Migration-Report-2026-07-02` · `Node-VLAN-Migration-Template` · `Security-VLAN-Segmentation-Phased-2026-07-03` · `Jarvis-LLM-Platform-2026-07-05` · `DS4246-Pool-Buildout-Plan-2026-07-07` · `Randy-PCIe-Slot-Recovery-2026-07-01` · `EX3400-Network-Buildout-2026-06-14` · `EX3400-SSH-Auth-Failure-RCA` · `Homepage-Setup-2026-06-26` · `netframe-pentest-remediation-2026-06-24`

### Appendix C — Port / service scan (live, `nmap -sT -sV`, top-200)

> Verified attack-surface snapshot 2026-07-08. **Note:** Proxmox web `:8006`, PBS `:8007`, and Jellyfin `:8096` fall outside the top-200 port set and are therefore not listed below but are known-live (see §7/§8); `:9100` = Prometheus node-exporter (all nodes); `:3128` = Proxmox `pveproxy`.

| Host | Open ports | Identity |
|---|---|---|
| .1 OPNsense | 53, 80, 443 | Unbound DNS 1.23.1 + web GUI |
| .2 UniFi USW-24 | 53, 80, 443, 8080, 8443 | dnsmasq + UniFi/nginx |
| .31 Jarvis | 22, 111, 3128, **8000**, 9100 | SSH · Proxmox · **llm_router** · node-exporter |
| .50 EX3400 | 22, 830 | SSH + NETCONF |
| .100/.199 Ares | 21, 22, 111, 139, 445, 2049, 9090 | FTP · Samba · NFS · Cockpit (workstation) |
| .112 (Amazon IoT) | **1080**, 8888 | ⚠️ **open no-auth SOCKS5** (F-8) |
| .148 Homepage | 22, 8081 | SSH · PeaNUT |
| .172 (printer) | 80, 443, 515, 631, 9100 | Network printer (LPD/IPP/JetDirect) |
| .177 Pi-hole | 22, 53, 80, 443 | dnsmasq pi-hole v2.92.2 + admin |
| .179 QuarkyLab | 22, 111, 3128, 9100 | SSH · Proxmox · node-exporter |
| .180 UPS A card | 22, 80, 443 | CyberPower SSH + web |
| .181 NPM | 22, 80, 81, 443 | OpenResty (reverse proxy + admin) |
| .182 Vaultwarden | 22, 80 | SSH · Vaultwarden |
| .183 Observability | 22, 3000, 8080, 9100 | Grafana · Scrutiny · node-exporter |
| .184 Wazuh | 22, 443 | SIEM dashboard |
| .185 Open WebUI | 22, 8080 | Chat UI |
| .186 Headscale | 22, 8080 | Mesh VPN control |
| .187 Randy | 22, 111, 2049, 3128, 9100 | SSH · NFS · Proxmox · node-exporter (+8007 PBS, +8096 Jellyfin) |
| .193 pve1 | 22, 111, 3128, 9100 | Mac Mini standalone (Pi-hole host) |
| .201–.204 pve3/4/5/2 | 22, 111, 3128, 9100 | Cluster nodes (.204 also **443 = step-ca**) |

_Six IoT/client hosts did not respond to the top-200 sweep (filtered/asleep)._

### Appendix D — Full MAC / OUI registry
_Vendor/OUI only in the public edition (full addresses omitted)._

### Appendix E — Randy disk serial inventory
_Serial numbers omitted in the public edition. Pool geometry: 22 pool drives (3× 6-wide Toshiba 1.6TB + 1× 4-wide Seagate 1.8TB) + RAID-1 boot mirror + DS4246 multipath shelf._

### Appendix F — Glossary
ELS (Enhanced Layer 2 Software, JunOS) · IT-mode HBA (raw passthrough) · RAIDZ2 (dual-parity ZFS) · CGNAT (`100.64.0.0/10`) · DNS-01 (ACME DNS challenge) · SVI/irb (switch L3 interface) · BMC (iDRAC/IPMI OOB controller).

---

*Generated 2026-07-08 from live discovery reconciled against the NetFRAME Home-Lab vault. Sanitized public edition.*
