# NetFRAME Infrastructure Update - June 22, 2026 (Cluster Upgrades)

**Session:** Full cluster upgrade to PVE 9.2.3, Jarvis disk expansion, corosync issue resolution, QuarkyLab GPU verified

---

## Cluster Upgrade - All Nodes to PVE 9.2.3 / Kernel 7.0.12-1

### Results

| Node | Before | After | Kernel | Notes |
|---|---|---|---|---|
| pve2 | 9.1.9 | 9.2.3 | 7.0.12-1 | OPNsense autostarted ✅ |
| pve3 | 9.1.9 | 9.2.3 | 7.0.12-1 | All 4 LXCs autostarted ✅ |
| pve4 | 9.1.9 | 9.2.3 | 7.0.12-1 | |
| pve5 | 9.1.1 | 9.2.3 | 7.0.12-1 | Fixed Tailscale DNS |
| Randy | 9.1.1 | 9.1.1* | 7.0.12-1 | Kernel/ZFS only; corosync rejoin required |
| Jarvis | 9.1.1 | 9.2.3 | 7.0.12-1 | Disk expanded 6GB → 56GB |
| QuarkyLab | 9.1.1 | 9.2.3 | 6.14.11-9-pve (pinned) | NVIDIA 550 verified ✅ |

*Randy's pve-manager package had no upgrade available in its repo.

---

## Issues Encountered & Resolutions

### 1 - Tailscale DNS Bug (pve5, pve4, Jarvis)
**Root cause:** Tailscale rewrites `/etc/resolv.conf` with MagicDNS (100.100.100.100) on join. Headscale doesn't have MagicDNS configured - all DNS resolution fails, breaking apt.

**Fix on each affected node:**
```bash
tailscale set --accept-dns=false
echo 'nameserver 192.168.10.177' > /etc/resolv.conf
echo 'nameserver 192.168.10.1' >> /etc/resolv.conf
```

**⚠️ Apply this before any apt operations on any node joined to Headscale.**

---

### 2 - pve3 LXCs Missing onboot Flag
**Root cause:** All 4 LXCs on pve3 (101/102/103/105) had no `onboot` setting - would not auto-start after reboot.

**Fix (applied before rebooting pve3):**
```bash
pct set 101 --onboot 1
pct set 102 --onboot 1
pct set 103 --onboot 1
pct set 105 --onboot 1
```

**⚠️ Verify onboot flags before any future pve3 reboots.**

---

### 3 - Randy Corosync Singleton After Reboot
**Root cause:** After Randy's first post-upgrade reboot, its corosync formed a singleton ring (1 vote) and could not merge into the main cluster. The isolated knet traffic disrupted the main ring's TOTEM token, causing token loss every ~9 seconds. This prevented the merge.

**Diagnosis:**
- knet links: all connected ✅
- Authkeys: matched ✅
- UDP packets: flowing both ways ✅
- But TOTEM ring wouldn't merge

**Root fix:** Remove and re-add Randy to the cluster.

```bash
# From pve2 - remove Randy
pvecm delnode Randy

# On Randy - clean up stale cluster state and rejoin
pkill pmxcfs
systemctl start pve-cluster
# pmxcfs will get new config from pve2 and rejoin
```

**⚠️ If Randy forms a singleton ring after reboot: run `pvecm delnode Randy` from pve2, then `pkill pmxcfs; systemctl start pve-cluster` on Randy.**

---

### 4 - Jarvis Root Disk Full During Upgrade
**Root cause:** Jarvis root LVM was only 6GB total. The dist-upgrade tried to install two kernel packages (~125MB each), filling the disk and leaving dpkg in `D` (disk sleep) state.

**Fix:** Add the unused 186GB SAS SSD (`/dev/sda`) to the LVM VG and extend root online.

```bash
pvcreate /dev/sda
vgextend pve /dev/sda
lvextend -r -L +50G /dev/pve/root
# resize2fs runs automatically (-r flag)
# dpkg resumed writing once space was available
```

Root is now 56GB (47GB free). `/dev/sda` (Seagate ST200FM0053 186GB) is now part of the pve VG.

---

### 5 - QuarkyLab Kernel Pin
**QuarkyLab GRUB was already pinned to 6.14.11-9-pve** before the upgrade. The `GRUB_DEFAULT` in `/etc/default/grub` was pre-set. Upgraded to PVE 9.2.3 without changing the kernel. Post-reboot:
- Kernel: 6.14.11-9-pve ✅
- NVIDIA 550.163.01 driver: working ✅
- RTX 6000 24GB: 35°C, idle ✅

**⚠️ Never run kernel upgrades or change GRUB_DEFAULT on QuarkyLab.**

---

### 6 - Wazuh VM Location
Wazuh VM 104 was found running on **QuarkyLab** (not pve2 as previously documented). IP: 192.168.10.184 (DHCP). Dashboard responding at `https://192.168.10.184`. Was migrated from pve2 at some unknown point - not deleted.

---

## Upgrade Procedure Used (All Nodes)

```bash
# 1. Fix DNS if needed
tailscale set --accept-dns=false
echo 'nameserver 192.168.10.177' > /etc/resolv.conf
echo 'nameserver 192.168.10.1' >> /etc/resolv.conf

# 2. Update and upgrade (via systemd-run to survive SSH disconnect)
apt-get update -qq
systemd-run --unit=pve-upgrade bash -c '
  DEBIAN_FRONTEND=noninteractive apt-get dist-upgrade -y \
    -o Dpkg::Options::="--force-confdef" \
    -o Dpkg::Options::="--force-confold" \
    > /tmp/apt-upgrade.log 2>&1
  echo SUCCESS >> /tmp/apt-upgrade.log'

# 3. Monitor
until tail -1 /tmp/apt-upgrade.log | grep -qE 'SUCCESS|FAILED'; do sleep 20; done

# 4. Reboot
reboot
```

---

## Post-Upgrade State

| Service | Status |
|---|---|
| km-cluster (7 nodes) | Quorate 7/7 ✅ |
| Randy PBS | Active, ZFS ONLINE ✅ |
| OPNsense VM 100 | Running ✅ |
| Headscale LXC 105 | Running ✅ |
| pve3 LXCs (101/102/103/105) | All running ✅ |
| QuarkyLab GPU (RTX 6000) | NVIDIA 550 active ✅ |
| Wazuh VM 104 | Running on QuarkyLab, dashboard up ✅ |
