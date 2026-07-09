# NetFRAME Infrastructure Update — June 22, 2026

**Session:** Randy commissioned, PBS live, ZFS pool online, full cluster update

---

## Cluster Nodes

| Hostname | Role | IP | CPU | RAM | GPU |
|---|---|---|---|---|---|
| Randy | Storage / PBS | 192.168.10.187 | 2× E5-2690 v4 | 128GB | RX 580 8GB |
| QuarkyLab | ML / the researcher | 192.168.10.30 | 2× E5-2699 v4 | 512GB | RTX 6000 24GB |
| Jarvis | LLM Inference | 192.168.10.31 | 2× E5-2687W v4 | 384GB | RTX 8000 48GB |
| pve2 | OPNsense host | 192.168.10.204 | i7-8700 | 32GB | — |
| pve3 | Cluster node | 192.168.10.201 | i7-8700 | 48GB | — |
| pve4 | Cluster node | 192.168.10.202 | i5-7500T | 32GB | — |
| pve5 | Cluster node | 192.168.10.203 | i5-7500T | 32GB | — |

Cluster: **km-cluster**, Proxmox VE 9.1. pve1 (Mac Mini 2011) removed.

**GPU final assignment** (reversed from original plan):
- Jarvis → RTX 8000 48GB (Ollama/LLM inference)
- QuarkyLab → RTX 6000 24GB (the researcher/DUNE agent)

---

## Randy — Commissioned

### Storage

- **Boot:** RAID-1 mirror on 2× Seagate SAS SSDs via AVAGO 3108 MegaRAID
- **ZFS pool:** `datastore` — 3× RAIDZ2 vdevs of 6× Toshiba AL15SEB18EQ 1.6TB 10K SAS (expanded 2026-06-25 with a 4th RAIDZ2 of 4× Seagate ST2000NX0423 → 4× RAIDZ2 total)
- **Usable:** ~19.5TB (as of 2026-06-22; ~23TB / 36.7TB raw after the 2026-06-25 expansion)

### Proxmox Backup Server

- **UI:** `https://192.168.10.187:8007`
- **Version:** v4.2.2
- **Fingerprint:** `(stored in Vaultwarden — not published)`

### DS4246 JBOD

- 13× Toshiba 1.8TB 10K SAS + 19× Dell/Seagate 2TB 7.2K SAS
- Connected via LSI 9207-8e HBA (IT mode), SFF-8644 → SFF-8088 cables
- DS4246 passthrough still in progress

---

## Network Updates

- **OPNsense** now at `192.168.10.1` — handles routing/firewall/DHCP for all VLANs
- **Pi-hole** moved to `192.168.10.177` on pve3 (was 192.168.1.47)
- **PDU** identified: APC AP7901 on EX3400 ge-0/0/38
- **10G fabric**: Mellanox ConnectX-3 DAC links from Randy/QuarkyLab/Jarvis to EX3400 xe- ports

### Power

| UPS | Feeds | Capacity |
|---|---|---|
| Middle Atlantic UPS-OL2200R | R730s, Randy, DS4246 | 6× 12V 9Ah AGM (76.4V) |
| Tripp Lite SMART1500VA | EX3400, UniFi, small compute | 1500VA |

---

## In Progress / Planned

- [ ] NVIDIA 550 driver on QuarkyLab (pin kernel to 6.14.11-9-pve first)
- [ ] VLAN activation (pve2 trunk to EX3400)
- [ ] DS4246 → Randy via LSI 9207-8e passthrough
- [ ] Jellyfin on Randy (RX 580 ROCm transcoding)
- [ ] FreePBX + 5× Cisco CP-8841 VoIP phones
- [ ] RKE2 Kubernetes (Cilium, MetalLB, NVIDIA GPU Operator)
- [ ] Cyberpunk monitoring dashboard — live API integration
- [ ] IMU gesture control (nRF52 trackers → Home Assistant)
- [ ] Headscale migration (remaining devices off commercial Tailscale)
