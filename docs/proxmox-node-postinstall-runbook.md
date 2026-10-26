# Proxmox VE 9 — Five-Node Post-Install Runbook

**Author:** Kyle Mason  
**Date:** May 2026  
**Environment:** Home lab / pre-production cluster  
**Purpose:** Standardized post-installation checklist applied to all five Proxmox VE 9.1 nodes prior to cluster formation

---

## Overview

This document covers the post-installation hardening and configuration applied to a five-node Proxmox VE 9.1 compute fleet before clustering. Each step includes the rationale behind it, not just the commands, because understanding *why* matters as much as knowing *what*.

The fleet consists of:

| Node | Hardware | IP | Role |
|------|----------|----|------|
| pve1 | Apple Mac mini (2011, Intel Sandy Bridge) | 192.168.1.193 | Lightweight always-on services |
| pve2 | HP EliteDesk 800 G4 SFF (i7-8700, 32GB) | 192.168.1.200 | OPNsense host, network gateway |
| pve3 | HP EliteDesk 800 G4 SFF (i7-8700, 48GB) | 192.168.1.201 | General compute |
| pve4 | HP EliteDesk 800 G3 Mini (i5-7500T, 32GB) | 192.168.1.202 | General compute |
| pve5 | HP EliteDesk 800 G3 Mini (i5-7500T, 32GB) | 192.168.1.203 | General compute |

All nodes run **Proxmox VE 9.1** on **Debian 13 (Trixie)** with kernel **7.0.0-3-pve** post-update.

---

## Step 1 — Repository Configuration

### Problem
Proxmox ships with enterprise repository sources enabled by default. These require a paid subscription and return HTTP 401 errors on `apt update`, blocking all package management. PVE 9 uses the Deb822 format (`.sources` files) rather than the legacy one-liner `.list` format.

### Fix

Remove enterprise repos and add the no-subscription community repo:

```bash
# Remove enterprise repos (Deb822 format used in PVE 9)
rm -f /etc/apt/sources.list.d/pve-enterprise.sources \
      /etc/apt/sources.list.d/ceph.sources \
      /etc/apt/sources.list.d/pve-enterprise.list \
      /etc/apt/sources.list.d/ceph.list

# Add no-subscription repo in Deb822 format
cat > /etc/apt/sources.list.d/pve-no-subscription.sources <<'EOF'
Types: deb
URIs: http://download.proxmox.com/debian/pve
Suites: trixie
Components: pve-no-subscription
Signed-By: /usr/share/keyrings/proxmox-archive-keyring.gpg
Enabled: true
EOF
```

> **Note:** Verify the `Suites` field matches your Debian release. PVE 9 = `trixie`, PVE 8 = `bookworm`. A mismatch here causes the system to pull packages from the wrong release, resulting in missed updates.

### Force IPv4 for apt (optional but recommended)

If your network does not route IPv6, apt will attempt IPv6 connections first, fail, and fall back to IPv4 — generating warnings that can obscure real errors. Suppress this:

```bash
echo 'Acquire::ForceIPv4 "true";' > /etc/apt/apt.conf.d/99force-ipv4
```

### Update

```bash
apt update && apt full-upgrade -y
```

---

## Step 2 — Essential Tooling

Install diagnostic and monitoring utilities used throughout administration:

```bash
apt install -y htop iotop iftop nload tmux \
  smartmontools lm-sensors \
  curl wget git nano \
  intel-microcode \
  net-tools dnsutils \
  prometheus-node-exporter \
  intel-gpu-tools va-driver-all vainfo

sensors-detect --auto
systemctl enable --now prometheus-node-exporter
```

**Why each matters:**

- `htop/iotop/iftop/nload` — real-time resource visibility at the terminal
- `smartmontools` — drive health monitoring via S.M.A.R.T.
- `lm-sensors` — CPU and motherboard temperature monitoring
- `intel-microcode` — stability and security patches for Intel CPUs; applies silently at boot
- `prometheus-node-exporter` — exposes host metrics on port 9100 for Grafana/Prometheus ingestion
- `intel-gpu-tools` / `vainfo` — Intel QuickSync validation for hardware video transcoding (Jellyfin, Frigate)

> **Hardware note:** The Intel HD 630 (7th/8th gen) supports QuickSync hardware transcoding. Validate with `vainfo` — a healthy output shows the `iHD` driver and supported codec profiles. The Mac mini (Sandy Bridge) does not benefit from this step.

---

## Step 3: Tailnet Access via Tailscale (alternate network path)

Tailscale gives the node a WireGuard-based path into the self-hosted Headscale tailnet (`http://192.168.10.186:8080`, CT105 on pve5) with no open WAN ports.

```bash
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up --login-server http://192.168.10.186:8080
```

Do **not** pass `--ssh`. Tailscale SSH is disabled estate-wide (on pve1, the last node that had it, since 2026-10-26, Tailworm remediation M1). Administrative access to a node is OpenSSH with keys, reached over the LAN or over the tailnet.

The tailnet is an **alternate network path, not out-of-band management.** It runs on the same host OS, kernel, and network stack as everything else, and it depends on the Headscale control plane (a guest on pve5) and on DNS. If the host is powered off, hung, or has lost its network, the tailnet is down with it. True out-of-band management means a BMC or console that works independently of the host OS (iDRAC on the R730s, IPMI on Randy, on VLAN 20). As of 2026-10-26 that BMC plane is unreachable from every tested vantage point (risk R-71), so no node currently has a verified out-of-band console. Do not count the tailnet as a recovery path in a DR plan.

> **Architecture note:** Each Proxmox host runs its own Tailscale agent, tagged by Headscale policy (`tag:infra`, `tag:recovery`, `tag:ssh`). pve3 is the only subnet router and advertises two host routes, `192.168.10.181/32` (NPM) and `192.168.10.201/32` (pve3 web UI). Both routes are approved in Headscale, and policy limits their use to `kyle@` devices. Network ACLs, not Tailscale SSH rules, decide which tailnet sources may reach TCP 22.

> **Access evidence levels.** When recording an access path for a node, state which level of evidence it has. An HTTP 200 or a listening SSH port alone does not verify administrative access.
> - **Verified:** a fresh, authenticated administrative session over that path, recorded with its date.
> - **Reachable, unauthenticated:** the service answers, but nobody has logged in over that path.
> - **Inferred from configuration:** the ACL, firewall, and listener should allow it, but nothing has tested it.
>
> pve1 (standalone Mac mini, `192.168.10.193`), as of 2026-10-26:
> - **Verified:** OpenSSH over the LAN, key-only.
> - **Reachable, unauthenticated:** Proxmox web UI `:8006` returns HTTP 200.
> - **Inferred from configuration:** OpenSSH over the tailnet from `kyle@` devices.
> - **None:** pve1 has no out-of-band console. There is no BMC and Wake-on-LAN is falsified, so a power-off needs someone at the machine.

---

## Step 4 — IOMMU (Intel VT-d)

IOMMU enables PCIe passthrough — assigning physical devices (GPUs, NICs, USB controllers) directly to VMs with near-native performance. Enabling it at the host level now means no additional reboot when passthrough is configured later.

```bash
sed -i 's|GRUB_CMDLINE_LINUX_DEFAULT="quiet"|GRUB_CMDLINE_LINUX_DEFAULT="quiet intel_iommu=on iommu=pt"|' /etc/default/grub
update-grub
```

The `iommu=pt` flag enables passthrough mode, which improves performance for devices not assigned to VMs by bypassing unnecessary IOMMU translation.

**Verify after reboot:**

```bash
dmesg | grep -e DMAR -e IOMMU
```

Expected output includes `DMAR: IOMMU enabled` and `Intel(R) Virtualization Technology for Directed I/O`.

---

## Step 5 — Kernel Tuning

### Swappiness

The default `vm.swappiness=60` is tuned for spinning hard drives with RAM pressure. On SSD-based nodes it causes excessive swap usage that degrades SSD lifespan. Lowering to 10 tells the kernel to prefer keeping data in RAM:

```bash
echo 'vm.swappiness=10' >> /etc/sysctl.d/99-pve-tuning.conf
sysctl --system
```

---

## Step 6 — VLAN-Aware Bridge

Proxmox bridges are not VLAN-aware by default. Enabling this allows VMs and LXCs to be assigned to specific VLANs without creating separate physical bridges — essential for network segmentation (IoT VLAN, VoIP VLAN, management VLAN, etc.).

Edit `/etc/network/interfaces` and add two lines to the `vmbr0` stanza:

```
auto vmbr0
iface vmbr0 inet static
        address 192.168.1.X/24
        gateway 192.168.1.1
        bridge-ports nic0
        bridge-stp off
        bridge-fd 0
        bridge-vlan-aware yes      # <-- add this
        bridge-vids 2-4094         # <-- and this
```

Or inject with sed (safe for single-bridge nodes):

```bash
sed -i '/bridge-fd 0/a\        bridge-vlan-aware yes\n        bridge-vids 2-4094' /etc/network/interfaces
```

> **Important:** Apply via reboot rather than `ifreload -a` or live `ip link` toggle on production nodes. Toggling `vlan_filtering` on a live bridge can drop active SSH sessions. A clean reboot applies the config atomically.

**Verify after reboot:**

```bash
ip -d link show vmbr0 | grep vlan_filtering
# Expected: vlan_filtering 1
```

---

## Step 7 — SSH Hardening

Disable password authentication once key-based access is confirmed working. This prevents brute-force attacks against the root account.

From the admin workstation, copy the public key first:

```bash
ssh-copy-id root@<node-ip>
```

Then on the node, disable password auth:

```bash
sed -i 's|^#*PasswordAuthentication.*|PasswordAuthentication no|' /etc/ssh/sshd_config
systemctl reload ssh
```

> **Always verify key-based login works in a separate session before closing your current one.**

---

## Step 8 — Pre-Cluster Snapshot

Before clustering (a difficult-to-reverse operation), snapshot the configuration state of each node:

```bash
tar czf ~/$(hostname)-preCluster-$(date +%F).tar.gz \
  /etc/pve \
  /etc/network/interfaces \
  /etc/hosts \
  /etc/hostname
```

This captures Proxmox config, network config, and hostname resolution. If clustering goes wrong, this is the baseline to diff against.

---

## Step 9 — Reboot and Verify

A single reboot applies: the new kernel (if updated), IOMMU flags, VLAN-aware bridge config, and swappiness.

```bash
reboot
```

Post-reboot verification:

```bash
uname -r                                          # kernel version
hostname                                          # correct node name
dmesg | grep -e DMAR -e IOMMU | head -3           # IOMMU active
ip -d link show vmbr0 | grep vlan_filtering       # vlan_filtering 1
systemctl is-active tailscaled prometheus-node-exporter ssh
```

---

## Troubleshooting Notes

### apt returns HTTP 401 on enterprise repos
The enterprise `.sources` files were not removed. Check `ls /etc/apt/sources.list.d/` for `pve-enterprise.sources` or `ceph.sources` and remove them.

### apt targets configured multiple times warning
Two repo files point to the same component. Check for both a `.list` and `.sources` file for the same repo and remove the duplicate.

### SSH locked out after PasswordAuthentication change
If key-based auth was not confirmed before disabling passwords, recover from the Proxmox web shell at `https://<node-ip>:8006` (another cluster node's web UI can open a shell on this node), from the iDRAC/IPMI console where the node has one, or from the physical console. Tailscale SSH is not a recovery path: it is disabled estate-wide, and the tailnet only reaches the same OpenSSH daemon that is locked out.

### vlan_filtering remains 0 after ifreload
Toggling `vlan_filtering` on a live bridge via `ifreload -a` or `ip link set` is unreliable in some configurations. Always apply via a clean reboot when using the interfaces file method.

### Proxmox node shows as offline after hostname change
Proxmox node names are stored in the pmxcfs cluster filesystem, separate from the system hostname. Changing hostname with `hostnamectl` alone does not rename the Proxmox node — it creates a new node entry while leaving VM configs registered under the old name. Proper node renaming requires pmxcfs database manipulation and should be performed as part of the cluster formation procedure, not independently.

---

## Final State

All five nodes confirmed post-reboot:

| Node | Kernel | IOMMU | vlan_filtering | Tailscale | node_exporter |
|------|--------|-------|----------------|-----------|---------------|
| pve1 | 7.0.0-3-pve | ✓ | 1 | ✓ | ✓ |
| pve2 | 7.0.0-3-pve | ✓ | 1 | ✓ | ✓ |
| pve3 | 7.0.0-3-pve | ✓ | 1 | ✓ | ✓ |
| pve4 | 6.17.x-pve | ✓ | 1 | ✓ | ✓ |
| pve5 | 7.0.0-3-pve | ✓ | 1 | ✓ | ✓ |

---

## Next Steps

- Physical rack installation and CAT6 runs
- Proxmox cluster formation (Corosync quorum, shared storage)
- OPNsense VLAN configuration and VoIP VLAN
- TrueNAS deployment on SuperMicro with DS4246 JBOD (24x 2TB HGST)
- Service stack deployment: Vaultwarden, Jellyfin, Uptime Kuma, Grafana, Wazuh, Frigate
