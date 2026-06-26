# Randy — ZFS Datastore

## Pool: `datastore`

**Host:** randy.netframe.local (192.168.10.187)
**Total Capacity:** 36.7TB
**Health:** ONLINE

## Layout

| vdev | Type | Drives | Capacity |
|---|---|---|---|
| raidz2-0 | RAIDZ2 | 6× Toshiba AL15SEB18EQ 1.6TB SAS | 9.81TB |
| raidz2-1 | RAIDZ2 | 6× Toshiba AL15SEB18EQ 1.6TB SAS | 9.81TB |
| raidz2-2 | RAIDZ2 | 6× Toshiba AL15SEB18EQ 1.6TB SAS | 9.81TB |
| raidz2-3 | RAIDZ2 | 4× Seagate ST2000NX0423 1.8TB SATA | 7.27TB |

## raidz2-3 Drive WWNs (Seagate ST2000NX0423)

| WWN | Serial | Power-On Hours |
|---|---|---|
| wwn-0x5000c500ac21b85c | W460W2Y3 | ~6 yrs |
| wwn-0x5000c500ac21f630 | W460W25Y | ~6 yrs |
| wwn-0x5000c500ac222fb5 | W460W1FJ | ~2.4 yrs |
| wwn-0x5000c500ac212d63 | W460VVTP | ~6 yrs |

## ZFS Features
Upgraded to latest feature flags on 2026-06-25:
- `block_cloning_endian`
- `physical_rewrite`

## NFS Exports

| Export | Client | Options |
|---|---|---|
| `/datastore` | 192.168.10.179 (QuarkyLab) | rw,sync,no_subtree_check,no_root_squash |

## Notes
- raidz2-3 Seagates are SATA drives in AVAGO SMC3108 JBOD passthrough
- SATA drives will not light blue on SuperMicro backplane (SAS PHY limitation, cosmetic only)
- Boot SSDs (2× Seagate ST200FM0053 185GB SAS) are in PERC RAID-1, separate from ZFS
