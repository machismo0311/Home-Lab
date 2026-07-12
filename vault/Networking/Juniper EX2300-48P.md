# 🔀 Juniper EX2300-48P
**Tags:** #networking #juniper #switching  
**Related:** [[Networking/Network Overview]] · [[Networking/Juniper EX3400-48P]]

---

## Hardware Overview

| Field | Value |
|---|---|
| Model | EX2300-48P |
| Ports | 48× 1G PoE+, 4× 1G/10G SFP+ |
| Rack Position | U38 |
| Junos | ELS (same syntax as EX3400) |
| Role | Secondary / lab isolation switch |

---

## Use Cases

- **CCNA lab isolation:** Spin up isolated L2 topologies for Packet Tracer / GNS3 physical practice
- **VLAN 70 (LAB):** All lab ports native to LAB VLAN by default
- **Overflow capacity:** If EX3400 ports fill up

---

## Uplink

| Link | Type |
|---|---|
| EX2300 → EX3400 ge-0/0/45 | 1G copper trunk (upgrade to DAC when SFP+ available) |

---

## Config Notes

ELS Junos syntax identical to EX3400 - see [[Networking/Juniper EX3400-48P]] for full reference.

```junos
# All ports default to LAB VLAN
set interfaces ge-0/0/[0-47] unit 0 family ethernet-switching interface-mode access
set interfaces ge-0/0/[0-47] unit 0 family ethernet-switching vlan members LAB

# Uplink trunk to EX3400
set interfaces xe-0/0/0 unit 0 family ethernet-switching interface-mode trunk
set interfaces xe-0/0/0 unit 0 family ethernet-switching vlan members all
```
