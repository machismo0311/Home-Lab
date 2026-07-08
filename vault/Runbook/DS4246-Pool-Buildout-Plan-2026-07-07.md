# 📄 Build-Out Plan — DS4246 Bulk/Media ZFS Pool (`bulk`)

**Tags:** #plan #storage #zfs #netapp #jbod #multipath #randy
**Related:** [[Infrastructure/Storage]] · [[Runbook/Cluster-Health-Fixes-2026-07-07]] · [[Infrastructure/Proxmox Cluster]] · [[00 - Homelab MOC]]

| | |
|---|---|
| **Target** | NetApp DS4246, 16× 4 TB SAS, on Randy (LSI SAS2308 HBA) |
| **Purpose** | **Bulk / media** storage (large sequential files, archives, media library) |
| **Topology** | **2× 8-wide RAIDZ2** (all 16 drives), pool name **`bulk`** |
| **Usable** | **~40 TiB** (~48 TB) · 75% efficiency · tolerates 2 failures per vdev |
| **Status** | PLAN — not executed. Gated on drive qualification + multipath. |

> ⚠️ These are **used, mixed-age enterprise drives**. Do not create the pool until Phase 1 (qualification) passes. Do not build on raw `sdX` — the shelf is **dual-pathed** and needs multipath (Phase 2) first, or ZFS may grab the same disk twice.

---

## Phase 1 — Qualify the drives (GATE)
Long SMART self-tests were started 2026-07-07 (~7–8 h). Before proceeding, confirm **every** drive:
```bash
ssh randy '
for wwn in 637228f7 637238eb 63724197 6372476b 63725497 637257b7 63725b7f \
           5cc9af48 5ccbb218 5ccbe1d8 5ccc5580 5ccc8894 5cccb198 5ccce820 5cccf754 5ccd78dc; do
  d=$(lsblk -dno NAME,WWN | awk -v w="0x5000c500$wwn 0x5000cca05$wwn" "\$2~substr(w,1,18){print \$1;exit}")
  [ -z "$d" ] && d=$(lsblk -dno NAME,WWN | grep -i "$wwn" | awk "{print \$1;exit}")
  echo "$d $wwn: $(smartctl -l selftest /dev/$d | awk "/# 1/{print \$3,\$4,\$5;exit}") \
        realloc/defects=$(smartctl -x /dev/$d | awk -F: "/grown defect list/{print \$2}")"
done'
```
**Pass criteria (all 16):** self-test `Completed` (no "read failure"), grown-defect list stable (≤ a few, not climbing), 0 new reallocations. **Reject any drive that fails** — pull it, use one of the 8 empty bays / a spare instead. Do not build a vdev short; keep vdevs at 8.

> ✅ **PHASE 1 PASSED — 2026-07-08 ~03:27.** All 16 long self-tests `Completed` clean (LBA `-`, sense `[- - -]`), **0 failures, 0 new reallocations**; grown defects all 0 except sdx/Z1Z861CF = 1 (stable, passed). Tests ran ~17 h (SAS background, slow). Power-on hours (replacement-priority reference): **sdap/Z1Z862D3 = 60,310 h (oldest)**; Seagates sdao 12,527 · sdaq/sdar/sdan/sdy 22,137 · sdx 22,170; HGSTs — sdac 25,124 · sdab 25,128 · sdad 25,057 · sdag 25,097 · sdal 6,737 · sdas 6,736 · sdam 6,734 · sdaj 6,745 · sdak 6,747. **Cleared to build.** → proceed to Phase 2.

## Phase 2 — Multipath (GATE)
The dual IOM6 shelf presents each disk on **2 paths** (32 `sdX` for 16 disks). Install + configure multipath so each disk is a single `/dev/mapper` device.
```bash
ssh randy '
apt-get update && apt-get install -y multipath-tools
cat > /etc/multipath.conf <<EOF
defaults {
    user_friendly_names yes
    find_multipaths     yes
    path_grouping_policy multibus
}
blacklist {
    # keep the MegaRAID datastore + boot disks OUT of multipath
    devnode "^sd[a-v]$"
}
EOF
systemctl enable --now multipathd
multipath -r
sleep 2
multipath -ll | grep -E "mpath|status" | head -40'
```
- The `blacklist` protects the internal `datastore`/boot disks (currently `sda`–`sdv`); **re-verify those device letters at run time** — a reboot can shuffle them. Safer alternative: blacklist by WWN-prefix and whitelist only the shelf WWNs (`0x5000c50063…`, `0x5000cca05cc…`).
- Result: 16× `/dev/mapper/mpathX`, each aggregating the 2 paths. Confirm `multipath -ll` shows **2 active paths per mpath**.

## Phase 3 — Create the pool
Balance models and spread the 4 highest-hour HGST drives across both vdevs (don't concentrate the most-worn disks in one vdev). Suggested split (by WWN suffix):

| vdev | Seagate `0x5000c50063…` | HGST `0x5000cca05cc…` |
|---|---|---|
| **raidz2-0** | 7228f7 · 7238eb · 724197 · 72476b | 9af48 · cbb218 · cbe1d8 · cc5580 |
| **raidz2-1** | 725497 · 7257b7 · 725b7f | c8894 · ccb198 · cce820 · ccf754 · cd78dc |

```bash
# Use the /dev/mapper/mpath* names that map to the WWNs above (from `multipath -ll`).
ssh randy '
zpool create -o ashift=12 \
  -O compression=lz4 -O atime=off -O relatime=off -O xattr=sa -O acltype=posixacl \
  -O recordsize=1M -O mountpoint=/mnt/bulk \
  bulk \
  raidz2 /dev/mapper/<8 mpaths for vdev0> \
  raidz2 /dev/mapper/<8 mpaths for vdev1>
zpool status bulk'
```
- **ashift=12** (safe/aligned even on 512 B drives).
- **recordsize=1M** + **lz4** — ideal for large media/archive files (media is largely incompressible; lz4 is near-free and skips uncompressible blocks). Consider `zstd` only for compressible archive datasets.

## Phase 4 — Datasets & tuning
```bash
ssh randy '
zfs create bulk/media       # recordsize=1M inherited
zfs create bulk/archive
zfs create -o recordsize=128k bulk/misc   # smaller files
zfs set compression=zstd bulk/archive     # better ratio on compressible archives
zfs list -r bulk'
```

## Phase 5 — Sharing (media/bulk to the cluster)
Export over NFS to the cluster / media server (Jellyfin was the historical intent). Keep it on the **VLAN 30 servers** network per the segmentation model.
```bash
ssh randy '
zfs set sharenfs="rw=@192.168.30.0/24,no_subtree_check" bulk/media
# or manage via /etc/exports; confirm nfs-kernel-server is enabled
exportfs -ra && exportfs -v | grep bulk'
```

## Phase 6 — Data protection
- **Scrub:** the distro `zfs-scrub.timer` already scrubs *all* pools monthly (covers `bulk` automatically). Given used drives, optionally add `bulk` to the weekly cron alongside `datastore` (`/etc/cron.d/zfs-scrub-datastore`).
- **ZED:** already `active` → pool fault emails/events covered. Confirm `/etc/zfs/zed.d/zed.rc` has a notify target.
- **smartd:** already `active` → **add the 16 shelf drives** to `/etc/smartd.conf` (or `DEVICESCAN`) so pending/reallocated sectors alert like the internal disks did.
- **Snapshots:** if any dataset holds non-repro data, add `sanoid` (or `zfs-auto-snapshot`) with a sane retention (e.g. media: light; archive: daily+weekly).

## Expansion path
- 8 empty bays remain. Grow by **adding another 8-wide RAIDZ2 vdev** (keep vdev geometry uniform) — never widen an existing vdev.
- Keep pool **< ~80% full** for performance/CoW headroom (~32 TiB practical on this layout).

## Validation checklist (post-build)
- [ ] `zpool status bulk` → ONLINE, 2× raidz2, 0 errors
- [ ] `multipath -ll` → 16 maps, 2 active paths each
- [ ] Reboot Randy → pool auto-imports, multipath re-forms, `datastore` unaffected
- [ ] Initial `zpool scrub bulk` → 0 errors
- [ ] NFS mount from a VLAN-30 client works; write/read a large file
- [ ] smartd/ZED alerting confirmed on the new drives

## Rollback
Nothing destructive until `zpool create`. To undo pre-data: `zpool destroy bulk` (only if empty), `systemctl disable --now multipathd` + remove `/etc/multipath.conf`, `apt-get remove multipath-tools`. The internal `datastore` pool is never touched by this plan.

## Risks & notes
- **Used drives:** expect a higher near-term failure rate than new disks; RAIDZ2 + prompt resilience + weekly scrub mitigate. Keep 1–2 qualified drives ready as replacements (use empty bays).
- **Multipath blacklist correctness is critical** — a wrong blacklist could pull `datastore` members into multipath. Verify device letters / prefer WWN-based whitelist at run time.
- **Not a backup of `datastore`** — same chassis/host. If `bulk` holds anything important, it still needs an off-box copy.
