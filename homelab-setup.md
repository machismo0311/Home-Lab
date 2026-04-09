# Home Lab Setup Documentation

## Overview
This document covers the setup of a Proxmox virtualization server on an Intel Mac Mini, including Tailscale VPN and Pi-hole DNS ad-blocker running in an LXC container.

---

## Hardware
- **Virtualization Host:** Apple Mac Mini (Intel, 2018 or earlier)
- **Daily Driver:** Dell laptop running Debian KDE (Ares)
- **DNS Backup:** Raspberry Pi 4 (4GB) running Pi-hole at `192.168.1.170`
- **Network:** Spectrum modem → AirPort Extreme → TP-Link TL-SG1024D 24-port unmanaged switch

---

## Step 1: Create Proxmox Bootable USB (from Linux)

1. Download the Proxmox VE ISO from https://www.proxmox.com/en/downloads
   - Version used: **Proxmox VE 9.1**

2. Identify your USB drive:
   ```bash
   lsblk
   ```

3. Unmount the USB drive (if mounted):
   ```bash
   sudo umount /dev/sda1
   ```

4. Flash the ISO to the USB:
   ```bash
   sudo dd if=~/Downloads/proxmox-ve_9.1-1.iso of=/dev/sda bs=1M status=progress
   ```

5. Finalize the write:
   ```bash
   sync
   ```

---

## Step 2: Boot Mac Mini from USB

The Mac Mini required NVRAM reset to recognize the USB boot device.

1. Hold **Windows + Alt + P + R** while pressing the power button
2. Keep holding until the Mac startup chime plays
3. Release keys and allow the Mac to boot
4. Navigate boot menu blind (no display output during picker):
   - Wait ~20 seconds after power on
   - Press **down arrow once** to select Terminal UI installer
   - Press **Enter**

> **Note:** The Proxmox graphical installer did not display on the TV. The Terminal UI installer (`down arrow` from boot menu) was required for display compatibility.

---

## Step 3: Install Proxmox VE

Follow the Terminal UI installer prompts:

| Setting | Value |
|---|---|
| Filesystem | ext4 |
| Target disk | /dev/sda (Mac Mini internal) |
| Hostname | pve.lan |
| IP Address | 192.168.1.193/24 |
| Gateway | 192.168.1.1 |
| DNS | 192.168.1.1 |

- Set a strong root password and write it down
- Allow auto-reboot after installation

Access the web UI after install at:
```
https://192.168.1.193:8006
```

Login: `root` / your password / Realm: Linux PAM standard authentication

---

## Step 4: Fix Proxmox Repository (No Subscription)

Remove enterprise repos and add the free community repo:

```bash
rm /etc/apt/sources.list.d/pve-enterprise.sources
rm /etc/apt/sources.list.d/ceph.sources
echo "deb http://download.proxmox.com/debian/pve trixie pve-no-subscription" > /etc/apt/sources.list.d/pve-community.list
apt-get update
```

---

## Step 5: Install Tailscale on Proxmox

```bash
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up
```

Visit the authentication URL provided, log in with your Tailscale account.

Enable Tailscale on boot:
```bash
systemctl enable tailscaled
```

Enable IP forwarding for subnet routing:
```bash
echo 'net.ipv4.ip_forward = 1' >> /etc/sysctl.conf
sysctl -p
```

Advertise your home network subnet:
```bash
tailscale up --advertise-routes=192.168.1.0/24
```

Approve the subnet route in the Tailscale admin console at:
```
https://login.tailscale.com/admin/machines
```

### Tailscale Network
| Device | Tailscale IP |
|---|---|
| pve (Mac Mini) | 100.116.237.31 |
| ares (Dell Linux) | 100.124.118.63 |

Remote access to Proxmox via Tailscale:
```
https://100.116.237.31:8006
```

---

## Step 6: Create Pi-hole LXC Container

### Download Debian Template
1. In Proxmox web UI, click **local (pve)** → **CT Templates** → **Templates**
2. Download **debian-12-standard**

### Create Container
- **Hostname:** piehole
- **Template:** debian-12-standard
- **Disk:** 8GB
- **CPU:** 1 core
- **Memory:** 512MB
- **Network:** vmbr0 (DHCP)

### Fix Container Networking
After starting the container, the network interface needed manual configuration:

```bash
ip link set eth0 up
dhclient eth0
```

Make persistent by editing `/etc/network/interfaces`:
```
auto lo
iface lo inet loopback

auto eth0
iface eth0 inet dhcp
```

Set DNS inside container:
```bash
echo "nameserver 8.8.8.8" > /etc/resolv.conf
```

### Install Pi-hole
```bash
apt install curl -y
curl -sSL https://install.pi-hole.net | bash
```

Follow the installer prompts, accept defaults, and save the admin password.

### Pi-hole Details
| Setting | Value |
|---|---|
| Container IP | 192.168.1.47 |
| Web UI | http://192.168.1.47/admin |
| Backup Pi-hole | 192.168.1.170 (Pi 4) |

---

## Step 7: Point Linux Desktop to Pi-hole DNS

```bash
sudo nmcli con mod "YourWiFiName" ipv4.dns "192.168.1.47"
sudo nmcli --ask con up "YourWiFiName"
```

Verify:
```bash
nslookup google.com 192.168.1.47
```

---

## Current Network DNS Setup
| Role | IP |
|---|---|
| Primary Pi-hole | 192.168.1.47 (Proxmox LXC) |
| Backup Pi-hole | 192.168.1.170 (Raspberry Pi 4) |

---

## Planned Future Projects

- [ ] Install Proxmox on HP EliteDesk 800 G3 Mini (16GB) and cluster with Mac Mini
- [ ] Install TrueNAS Scale or OPNsense on HP EliteDesk 800 G3 Mini (8GB)
- [ ] Deploy OPNsense as VM to replace AirPort Extreme router
- [ ] Set up Ansible for automated multi-machine management
- [ ] Deploy Jellyfin media server container
- [ ] Deploy Nextcloud container
- [ ] Deploy Home Assistant container
- [ ] Install Tailscale on all devices for full remote access

---

## Useful URLs
| Service | URL |
|---|---|
| Proxmox Web UI (local) | https://192.168.1.193:8006 |
| Proxmox Web UI (Tailscale) | https://100.116.237.31:8006 |
| Pi-hole Admin | http://192.168.1.47/admin |
| Tailscale Admin | https://login.tailscale.com/admin/machines |
| Proxmox Helper Scripts | https://tteck.github.io/Proxmox |

---

## Resources
- [Proxmox Documentation](https://pve.proxmox.com/wiki/Main_Page)
- [Tailscale Documentation](https://tailscale.com/kb)
- [Pi-hole Documentation](https://docs.pi-hole.net)
- [Lawrence Systems YouTube](https://www.youtube.com/@LAWRENCESYSTEMS)
- [Craft Computing YouTube](https://www.youtube.com/@CraftComputing)
- [Techno Tim YouTube](https://www.youtube.com/@TechnoTim)
- [r/homelab](https://www.reddit.com/r/homelab)
- [r/selfhosted](https://www.reddit.com/r/selfhosted)
