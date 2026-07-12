# 🔀 UniFi USW-24-250W
**Tags:** #networking #unifi #switching  
**Related:** [[Networking/Network Overview]] · [[Networking/Juniper EX3400-48P]]

---

## Hardware Overview

| Field | Value |
|---|---|
| Model | UniFi USW-24-250W |
| Ports | 24× 1G PoE+ (802.3at), 2× 10G SFP+ uplinks |
| PoE Budget | 250W |
| Management | UniFi Network Controller (self-hosted) |
| Rack Position | U39 |
| Role | Access switch / AP host, PoE+ for endpoints |

> [!NOTE] PoE+ Capable
> This is the **PRO** variant with PoE+. Suitable for UniFi APs, Cisco CP-8841 phones (with PoE), and other 802.3at devices.

---

## Uplink

| Link | Type | Speed |
|---|---|---|
| USW-24 SFP+ → EX3400 xe-0/0/0 | 10Gtek 0.25m passive SFP+ DAC | 10 Gbps |

---

## Port Assignments

| Port | Device | VLAN |
|---|---|---|
| 1–2 | EliteDesk G3 Mini A | COMPUTE (20) |
| 3–4 | EliteDesk G3 Mini B | COMPUTE (20) |
| 5–6 | Mac mini + RPi 4 | COMPUTE / IOT |
| 7–12 | UniFi APs | Trunk (MGMT tagged, SSID VLANs) |
| 13–18 | Available | - |
| 19–23 | Reserved (VoIP future) | VOIP (60) |
| SFP+1 | DAC to EX3400 | Trunk - all VLANs |

---

## Controller

- UniFi Network Controller runs as **Docker container** on Proxmox VM
- Access: `https://10.0.10.3:8443` (or via UniFi app)
- See [[Infrastructure/Services & VMs]] for container config
