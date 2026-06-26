# QuarkyLab — ZFS Workspace Pool

## Pool: `workspace`

**Host:** QuarkyLab (192.168.10.179)  
**Total Capacity:** 9.09TB  
**Health:** ONLINE  
**Purpose:** ML research scratch space and student workspaces

## Layout

| vdev | Type | Drives | Capacity |
|---|---|---|---|
| raidz1-0 | RAIDZ1 | 5× Hitachi HUA723020ALA640 1.8TB SATA | 9.09TB |

## Drive WWNs

| WWN | Serial | Power-On Hours |
|---|---|---|
| wwn-0x5000cca223d8859d | MK0171YFHRY8YA | ~11 yrs |
| wwn-0x5000cca223c3bb61 | MK0131YFG86HLA | ~13 yrs |
| wwn-0x5000cca224c305d0 | MK0231YGG6N46A | ~12 yrs |
| wwn-0x5000cca223c3c0b2 | MK0131YFG87XHA | ~11 yrs |
| wwn-0x5000cca223c3be9a | MK0131YFG87B6A | ~11 yrs |

## Datasets

| Dataset | Mountpoint | Quota | Compression |
|---|---|---|---|
| workspace/fernanda | /workspace/fernanda | 4TB | lz4 |
| workspace/students | /workspace/students | 3TB | lz4 |
| workspace/scratch | /workspace/scratch | none | lz4 |

## NFS Mounts

| Remote | Local Mountpoint | Options |
|---|---|---|
| 192.168.10.187:/datastore | /mnt/randy-datastore | rw,sync,hard,intr,timeo=30 |

## Notes
- `sda` (Hitachi MK0171YFHSG5PA) excluded — hosts Proxmox boot + Wazuh VM 104
- `sdc` (Hitachi HUA722010CLA330 931GB) excluded — capacity mismatch, kept as cold spare
- Drives are 10-13 years old — suitable for scratch only, not primary storage
- All important data should be backed up to Randy via PBS
