# 🖥️ Dell R730 — General Node (#2)
**Tags:** #compute #dell #r730  
**Related:** [[Compute/Dell R730 - ML Node]] · [[Infrastructure/Proxmox Cluster]] · [[Power Distribution]]

---

## Hardware Specs

| Component | Spec |
|---|---|
| Model | Dell PowerEdge R730 |
| Form Factor | 2U |
| Rack Position | U15–U16 |
| **CPU** | 2× Intel Xeon E5-2687W v4 |
| CPU Cores | 24c / 48t total |
| CPU Base Clock | 3.0 GHz |
| **RAM** | 64 GB ECC DDR4 |
| Storage | TBD (see [[Infrastructure/Storage]]) |
| NICs | 4× 1G onboard |
| Remote Mgmt | iDRAC 8 Enterprise |
| iDRAC IP | 10.0.10.11 (VLAN 10 MGMT) |
| Depth | ~28" — **rear panel removed** from NetFRAME CS9000 |

---

## Purpose

General-purpose compute node in the Proxmox cluster:
- Jellyfin media server VM
- Vaultwarden
- FreePBX (VoIP — see [[Projects/VoIP - FreePBX]])
- General VM hosting
- Overflow workloads

---

## Proxmox Role

- Node in Proxmox cluster alongside other hosts
- No GPU passthrough required (general workloads)
- Storage: local + NFS share from [[Infrastructure/Storage]]

---

## iDRAC Access

```bash
https://10.0.10.11
```

---

## Notes

- E5-2687W v4 is a high-clocked Xeon (3.0GHz base) — good for latency-sensitive VMs
- 64GB RAM is the current limit — upgrade path: additional LRDIMM sticks if needed
- Shares rear-panel-removed depth situation with ML node
