# Randy — SuperMicro CSE-219U Commissioning Runbook

**Date:** June 22, 2026  
**Node:** Randy (SuperMicro CSE-219U)  
**Cluster:** km-cluster  
**Author:** Kyle Mason

---

## Hardware Specs

| Component | Detail |
|---|---|
| Chassis | SuperMicro CSE-219U 2U 24-bay |
| CPU | Dual Intel Xeon E5-2690 v4 (2× 14c/28t = 28 cores / 56 threads) |
| RAM | 128 GB ECC DDR4 |
| RAID Controller | AVAGO 3108 MegaRAID (SAS-12G) |
| NIC | Mellanox ConnectX-3 MCX312A dual-port 10GbE |
| IPMI | 192.168.10.22 |
| iDRAC | N/A (SuperMicro IPMI) |

### Storage

| Device | Model | Count | Size | Interface | Purpose |
|---|---|---|---|---|---|
| Boot SSDs | Seagate ST200FM0053 | 2 | 185.8 GB | SAS | RAID-1 boot mirror |
| Data drives | Toshiba AL15SEB18EQ | 18 | 1.636 TB | SAS 10K | ZFS datastore pool |
| Spare drives | Seagate ST2000NX0423 | 2 | 1.818 TB | SATA | Unallocated |

---

## Issues Encountered & Root Causes

### Issue 1 — No disks visible in Proxmox installer
**Root cause:** Internal SFF-8643 SAS cables were unplugged from the backplane.  
**Fix:** Physically reconnect both SAS cables between the AVAGO 3108 card and the backplane. Blue LEDs on caddies indicate power only — drives can have power but no data path if cables are disconnected.

### Issue 2 — MegaRAID WebBIOS showed "No PD Present"
**Root cause:** Same as above — no data path to drives.  
**Fix:** Cable reconnection resolved this. All drives then showed as "Unconfigured Good."

### Issue 3 — Proxmox USB booted into old BIOS flash utility
**Root cause:** The USB stick still contained the BIOS flash STARTUP.NSH from a previous session. The EFI shell auto-executed it.  
**Fix:** Rewrote USB with `dd` from Ares: `sudo dd if=~/Downloads/proxmox-ve_9.1-1.iso of=/dev/sda bs=4M status=progress conv=fsync`

### Issue 4 — Enterprise repos blocking apt
**Root cause:** Proxmox 9.1 + PBS ship with multiple enterprise repo files in both `.list` and `.sources` formats — all need to be disabled.  
**Files to disable:**
- `/etc/apt/sources.list.d/pve-enterprise.list`
- `/etc/apt/sources.list.d/pve-enterprise.sources`
- `/etc/apt/sources.list.d/ceph.list`
- `/etc/apt/sources.list.d/ceph.sources`
- `/etc/apt/sources.list.d/pbs-enterprise.list`
- `/etc/apt/sources.list.d/pbs-enterprise.sources`

### Issue 5 — Cluster join hostname verification failed
**Root cause:** Randy couldn't resolve pve2's hostname for TLS certificate validation.  
**Fix:**
```bash
echo "192.168.10.204 pve2.netframe.local pve2" >> /etc/hosts
pvecm add 192.168.10.204 --use_ssh
```

### Issue 6 — Tailscale overwrote /etc/resolv.conf with dead DNS
**Root cause:** Tailscale rewrites resolv.conf to use MagicDNS (100.100.100.100) on join. Headscale doesn't have MagicDNS configured, so all DNS resolution failed.  
**Fix:**
```bash
tailscale set --accept-dns=false
```

### Issue 7 — StorCLI unavailable in apt
**Root cause:** Broadcom doesn't distribute StorCLI via standard Debian repos. Their download portal also requires authentication, blocking `curl` downloads.  
**Fix:** Download `SAS35_StorCLI_7_23-007.2310.0000.0000.zip` manually from Broadcom portal on Ares, SCP to Randy, extract the Ubuntu `.deb`:
```bash
scp ~/Downloads/SAS35_StorCLI_7_23-007.2310.0000.0000.zip root@192.168.10.187:/tmp/storcli.zip
unzip /tmp/storcli.zip -d /tmp/storcli
unzip /tmp/storcli/storcli_rel/Unified_storcli_all_os.zip -d /tmp/storcli2
dpkg -i /tmp/storcli2/Unified_storcli_all_os/Ubuntu/storcli_007.2310.0000.0000_all.deb
ln -s /opt/MegaRAID/storcli/storcli64 /usr/sbin/storcli64
```

---

## Full Commissioning Procedure

### Step 1 — MegaRAID WebBIOS (Ctrl+H during POST)

Create boot mirror on the two Seagate SSDs:
1. Go to **VD Mgmt → F2 → Create Virtual Drive**
2. RAID Level: **RAID-1**
3. Select only the two 185GB SSDs (slots 0:0 and 0:1)
4. Accept initialization when prompted
5. Confirm VD shows: RAID-1, 185.781 GB, Optimal

### Step 2 — Install Proxmox VE 9.1

Boot from USB (`UEFI: USB Flash MemoryPMAP, Partition 1`):

| Setting | Value |
|---|---|
| Target disk | /dev/sda (185.78GiB, SMC3108) |
| Filesystem | ext4 |
| Hostname | randy.netframe.local |
| IP | 192.168.10.187/24 |
| Gateway | 192.168.10.1 |
| DNS | 192.168.10.177 |

### Step 3 — Post-install repo cleanup

```bash
echo "# disabled" > /etc/apt/sources.list.d/pve-enterprise.list
echo "# disabled" > /etc/apt/sources.list.d/ceph.list
echo "# disabled" > /etc/apt/sources.list.d/pbs-enterprise.list
echo "" > /etc/apt/sources.list.d/pve-enterprise.sources
echo "" > /etc/apt/sources.list.d/ceph.sources
echo "" > /etc/apt/sources.list.d/pbs-enterprise.sources

echo "deb http://download.proxmox.com/debian/pve bookworm pve-no-subscription" \
  > /etc/apt/sources.list.d/pve-no-subscription.list

apt update && apt dist-upgrade -y
```

### Step 4 — Join km-cluster

```bash
echo "192.168.10.204 pve2.netframe.local pve2" >> /etc/hosts
pvecm add 192.168.10.204 --use_ssh
```

### Step 5 — Enable JBOD passthrough

```bash
# Install StorCLI (see Issue 7 above for download procedure)
storcli64 /c0 set jbod=on
storcli64 /c0/eall/sall set jbod

# Verify all data drives show JBOD state
storcli64 /c0/eall/sall show

# Verify OS sees all drives
lsblk -d -o NAME,SIZE,ROTA,TYPE | grep -v loop
```

### Step 6 — Create ZFS pool

```bash
zpool create -f -o ashift=12 datastore \
  raidz2 sdb sdd sde sdf sdh sdi \
  raidz2 sdj sdk sdl sdm sdn sdo \
  raidz2 sdp sdq sdr sds sdt sdu

# Verify
zpool status datastore
zpool list datastore
# Expected: 29.4TB raw / 19.5TB usable (original 3-vdev build)
# NOTE: pool later expanded 2026-06-25 with a 4th RAIDZ2 (4× Seagate ST2000NX0423)
#       → now 36.7TB raw / ~23TB usable
```

### Step 7 — Install Proxmox Backup Server

```bash
echo "deb http://download.proxmox.com/debian/pbs trixie pbs-no-subscription" \
  > /etc/apt/sources.list.d/pbs-no-subscription.list

apt update && apt install proxmox-backup-server -y

# Create datastore
proxmox-backup-manager datastore create datastore /datastore

# Get fingerprint for cluster registration
proxmox-backup-manager cert info | grep Fingerprint
```

**PBS fingerprint:**
```
(stored in Vaultwarden — not published)
```

### Step 8 — Add randy-pbs to cluster storage

In Proxmox web UI: **Datacenter → Storage → Add → Proxmox Backup Server**

| Field | Value |
|---|---|
| ID | randy-pbs |
| Server | 192.168.10.187 |
| Datastore | datastore |
| Username | root@pam |
| Fingerprint | (see above) |

### Step 9 — Base services

```bash
# Tailscale / Headscale
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up --login-server http://192.168.10.186:8080
# On pve3: pct exec 105 -- headscale nodes register --user kyle --key <nodekey>
tailscale set --accept-dns=false  # prevent MagicDNS from breaking DNS

# Prometheus node exporter
apt install prometheus-node-exporter -y

# smartmontools
apt install smartmontools -y
systemctl enable --now smartd

# ZFS scrub timer
cat > /etc/systemd/system/zfs-scrub.service << 'EOF'
[Unit]
Description=ZFS scrub on datastore pool
After=zfs.target
[Service]
Type=oneshot
ExecStart=/usr/sbin/zpool scrub datastore
EOF

cat > /etc/systemd/system/zfs-scrub.timer << 'EOF'
[Unit]
Description=Monthly ZFS scrub on datastore pool
[Timer]
OnCalendar=monthly
Persistent=true
[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now zfs-scrub.timer
```

### Step 10 — Add Randy to Prometheus

On pve3, edit LXC 103's Prometheus config:
```bash
pct exec 103 -- bash -c "cat >> /opt/grafana/prometheus.yml << 'EOF'
  - job_name: 'proxmox-randy'
    static_configs:
      - targets: ['192.168.10.187:9100']
EOF"
pct exec 103 -- bash -c "kill -HUP \$(pgrep prometheus)"
```

---

## Verified State — June 22, 2026

| Service | Status |
|---|---|
| Proxmox VE 9.1 | ✅ Running |
| km-cluster member | ✅ Joined |
| 10G link (nic3 → xe-0/2/0) | ✅ 10000Mb/s Full Duplex |
| RAID-1 boot mirror | ✅ Optimal |
| ZFS datastore pool | ✅ ONLINE, 19.5TB usable (expanded 2026-06-25 → 36.7TB raw / ~23TB usable) |
| PBS 4.2.2 | ✅ Running, datastore configured |
| randy-pbs in cluster | ✅ Shared across all nodes |
| Headscale | ✅ Online at 100.64.0.2 |
| Prometheus node-exporter | ✅ Running, scraped by Grafana |
| smartd | ✅ Monitoring 22 devices |
| ZFS scrub timer | ✅ Monthly, next: July 1 2026 |

---

## Pending

- [ ] 4th DAC cable for nic2 → xe-0/2/2 (second 10G port)
- [x] Scrutiny web UI for visual drive health ✅ (live at 192.168.10.183:8080; collector on Randy)
- [x] Backup schedules on all cluster nodes → randy-pbs ✅ (LXCs 02:00 / VMs 03:00 daily, 7d+4w)
- [ ] ~~Migrate Prometheus/Grafana/Loki from management G4 to Randy~~ — superseded: stack deployed on pve3 LXC 103 instead
- [ ] DS4246 connection via LSI 9207-8e HBA
- [ ] Jellyfin RX 580 ROCm transcoding — Jellyfin installed & live (v10.11.11); hardware transcode still pending RX 580 power cable

---

## Quick Reference

```bash
# Randy SSH
ssh root@192.168.10.187

# PBS web UI
https://192.168.10.187:8007

# Proxmox web UI
https://192.168.10.187:8006

# Check ZFS pool
zpool status datastore

# Check all drives
storcli64 /c0/eall/sall show

# If JBOD mode resets after reboot
storcli64 /c0 set jbod=on
storcli64 /c0/eall/sall set jbod

# Check cluster
pvecm status
```
