# NetFRAME Canonical Facts

> **This file wins in a conflict.** When another doc disagrees with a value here, this file is
> authoritative and the other doc is stale — fix the other doc. Generated from the 2026-07-22
> reconciliation audit (`audit/findings/`), live-verified where noted. Keep it short; it is the
> tiebreaker, not the encyclopedia.

_Last reconciled: 2026-07-22 · basis commit 65f3681 · live-scanned all 8 nodes._

## Compute / nodes
| Entity | Canonical value | Note |
|---|---|---|
| Cluster | km-cluster, 7 nodes, PVE 9.2.3, **7/7 quorate** | pve1 is standalone (not a member) |
| pve1 | standalone Mac Mini, PVE 9.1.9, `192.168.10.193` | hosts Pi-hole CT103 + old homepage CT104 |
| Randy CPU | **2× E5-2690 v3 (24c / 48t, nproc=48)** | corrected 2026-07-11; NOT v4/28c |
| Randy RAM | 128 GB (+64 on hand → 192 planned) | |
| QuarkyLab GPU | **1× RTX 8000 48 GB** (installed & verified 2026-07-01) | post-swap; kernel pin 6.14.11-9-pve (held) |
| Jarvis GPU | **2× RTX 6000 (24 GB ea / 48 GB total)** (verified 2026-07-04) | post-swap; kernel pin 6.14.11-9-pve (held) |

## Storage
| Pool | Canonical value | Health (2026-07-22) |
|---|---|---|
| `datastore` (Randy internal) | 4× RAIDZ2 (3×6-wide Toshiba + 1×4-wide Seagate), 36.7T / ~23T usable | ONLINE |
| `bulk` (DS4246) | **3× RAIDZ2 (8+8+6-wide), 80.0T raw / ~55 TiB usable**, 22× 4TB, 2 bays free | **DEGRADED — slot-15 `mpathv` faulted (replace)** |
| DS4246 attach | LSI 9207-8e (IT-mode) + dm-multipath | 22 drives (not 32) |

## Services (location authoritative)
| Service | Canonical location | IP |
|---|---|---|
| Grafana / Prometheus / Loki | **LXC 103 on pve4** (moved 2026-07-16) | 192.168.10.183 |
| Headscale | **LXC 105 on pve5** (moved 2026-07-16) | 192.168.10.186 |
| Homepage | **LXC 106 on pve3** (migrated from pve1 LXC104, 2026-06-24) | 192.168.10.148 |
| OPNsense | VM 100 on pve2, **v25.1.12** (25.7 = future upgrade target only) | 192.168.10.1 |
| PBS | Randy, datastore `datastore` | 192.168.10.187:8007 |

## Network
| Fact | Canonical value |
|---|---|
| EX3400 mgmt | 192.168.10.50, JunOS 23.4R2-S7.4 (192.168.10.2 = UniFi UDR, not the switch) |
| `native-vlan-id` on EX3400 | **Supported; set at the physical-interface level (ELS).** "Not supported" is stale/wrong. |
| VLANs | 1 mgmt · 20 iDRAC · 30 servers · 40 IoT · 50 VoIP · 60 guest · 70 lab |

See `audit/findings/11-contradictions.md` for the file:line evidence behind each correction.
