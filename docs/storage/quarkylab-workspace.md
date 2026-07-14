# QuarkyLab — ZFS Workspace Pool

> Canonical reference (slot map, procedures, backup tiers) lives in the Obsidian vault:
> `vault/Infrastructure/QuarkyLab Storage.md`. This file mirrors the hardware facts for the docs tree.

## Pool: `workspace`

**Host:** QuarkyLab (192.168.10.179)
**Raw capacity:** 10.9 TB (`zpool list`) · usable ~9.1 TB
**Health:** ONLINE, 0 errors
**Purpose:** ML research scratch space, student/researcher workspaces, system containerd store

## RAID controller / backplane

| Field | Value |
|---|---|
| Controller | Dell **PERC H330 Mini** (LSI SAS-3 3008 "Fury" ASIC) |
| Controller SN / FW | `4AM00EM` / `25.2.1.0037` |
| Personality | RAID-Mode with **JBOD ON** — drives pass through as raw `/dev/sd*`; **ZFS owns redundancy, no hardware RAID VD** |
| Tooling | `storcli64` at `/usr/local/bin/storcli64`, controller `/c0` |
| Backplane | Dell **BP13G+**, 8-bay, enclosure `EID 32`, slots 0-7 |

## Layout

| vdev | Type | Drives | Raw |
|---|---|---|---|
| raidz1-0 | RAIDZ1 (6-wide) | 5× Hitachi HUA723020ALA640 2TB SATA + 1× HGST HUS724020ALS640 2TB SAS | 10.9 TB |
| spare | hot spare | 1× HGST HUS724020ALS640 2TB SAS (`sdh`) | — |

`feature@raidz_expansion` = **active** (vdev was widened 5→6 on 2026-07-13).

## Drive map (slot → device → serial → WWN)

| Slot | Device | Model | Intf | Serial | WWN (by-id) | Role |
|---|---|---|---|---|---|---|
| 32:0 | sda | Hitachi HUA723020ALA640 2TB | SATA | MK0171YFHSG5PA | wwn-0x5000cca223d8c148 | OS / boot (LVM: pve-root + Wazuh VM 104) |
| 32:1 | sdb | Hitachi HUA723020ALA640 2TB | SATA | MK0171YFHRY8YA | wwn-0x5000cca223d8859d | pool member |
| 32:2 | sdc | HGST HUS724020ALS640 2TB | SAS | P6JRLE5V | wwn-0x5000cca02899d158 | pool member (added 2026-07-13) |
| 32:3 | sdd | Hitachi HUA723020ALA640 2TB | SATA | MK0131YFG86HLA | wwn-0x5000cca223c3bb61 | pool member |
| 32:4 | sde | Hitachi HUA723020ALA640 2TB | SATA | MK0231YGG6N46A | wwn-0x5000cca224c305d0 | pool member |
| 32:5 | sdf | Hitachi HUA723020ALA640 2TB | SATA | MK0131YFG87XHA | wwn-0x5000cca223c3c0b2 | pool member |
| 32:6 | sdg | Hitachi HUA723020ALA640 2TB | SATA | MK0131YFG87B6A | wwn-0x5000cca223c3be9a | pool member |
| 32:7 | sdh | HGST HUS724020ALS640 2TB | SAS | P6HK5U6V | wwn-0x5000cca028579e88 | hot spare (AVAIL, added 2026-07-13) |

## Datasets

| Dataset | Mountpoint | Notes |
|---|---|---|
| workspace/students | /workspace/students | 3 TB quota, 100 GB/user |
| workspace/researchers | /workspace/researchers | 1 TB quota, 150 GB/user |
| workspace/fernanda | /workspace/fernanda | 4 TB, researcher home + data |
| workspace/scratch | /workspace/scratch | 2 TB, disposable, NOT backed up |
| workspace/containerd | /var/lib/containerd | system containerd store (relocated off OS disk 2026-07-10) |
| workspace/backup | /workspace/backup | + read-only child `backup/randy-fernanda` |

All datasets lz4. Compression + mountpoint inherited from the pool (`/workspace`).

## NFS

| Remote | Local | Options |
|---|---|---|
| 192.168.30.187:/datastore/quarkylab | /data | nfs4.2, `_netdev`, **VLAN 30** (storage traffic moved off VLAN 1 on 2026-07-02) |

## Notes

- `sda` (Hitachi MK0171YFHSG5PA) is the OS disk — Proxmox boot + Wazuh VM 104 on its LVM thin pool. Not in the pool.
- The old 931 GB Hitachi HUA722010CLA330 (SN JPW9K0N13BHTVL) that used to occupy slot 2 was **removed 2026-07-13** (undersized for a 2TB vdev, never pooled) and replaced by the 2TB SAS pool member.
- SATA members are 10-13 year old enterprise drives — fine for working sets/scratch, not sole-copy primary storage. Everything important is backed up nightly to Randy PBS (`host/quarkylab-workspace`).
- **Adding a drive:** clear foreign config + set the slot JBOD on the PERC before ZFS can see it, then `zpool attach workspace raidz1-0 <by-id>` to widen or `zpool add workspace spare <by-id>`. Never `zpool add workspace <disk>` bare (destroys redundancy). Full procedure + the slot-7 "paper in the bay" story: `vault/Runbook/QuarkyLab-Storage-Expansion-2026-07-13.md`.

## History

- **2026-07-13** — +2× 2TB HGST SAS; raidz1 widened 5→6 (9.09→10.9 TB raw) + hot spare; 931 GB drive pulled.
- **2026-07-10** — `workspace/containerd` dataset; system containerd store relocated off the OS disk.
- **2026-07-02** — pool + tiers built; homes moved onto ZFS; NFS/PBS to VLAN 30.
