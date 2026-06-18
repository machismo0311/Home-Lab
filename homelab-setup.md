# Homelab Infrastructure Setup Documentation
**Date:** June 17-18, 2026
**Location:** Vermilion, OH — NetFRAME CS9000 42U rack
**Domain:** kylemason.org
**DNS/CDN:** Cloudflare
**Hypervisor:** Proxmox VE 9.1.9

---

## Cluster Overview

| Node | Hardware | CPU | RAM | Storage | IP | Role |
|------|----------|-----|-----|---------|-----|------|
| pve1 | Apple Mac Mini (2011) | Core i5 | — | Internal SSD | 192.168.10.193 | Cluster management |
| pve2 | HP EliteDesk 800 G4 SFF | i7-8700 | 32GB | — | 192.168.10.204 | Services |
| pve3 | HP EliteDesk 800 G4 SFF | i7-8700 | 48GB | 256GB NVMe + 1TB SATA | 192.168.10.201 | Primary services node |
| pve4 | HP EliteDesk 800 G3 Mini | i5-7500T | 32GB | — | 192.168.10.202 | Services |
| pve5 | HP EliteDesk 800 G3 Mini | i5-7500T | 32GB | — | 192.168.10.203 | Services |
| quarkylab | Dell R730 (svc tag: 1S8WR22) | Dual E5-2699 v4 | 512GB (target) | — | iDRAC: 192.168.10.20 | Heavy compute (pending) |
| Jarvis | Dell R730 | Dual E5 | 384GB | — | iDRAC: 192.168.10.21 | AI/ML workloads (pending) |
| pve-supermicro | Supermicro CSE-219U | 24c/48t | 128GB | 11x 4TB HDD | TBD | TrueNAS storage (pending) |
| NetApp DS4246 | NetApp | — | — | 24-bay SAS shelf | — | Storage expansion (pending) |
| OPNsense VM | VM 100 on pve2 | — | — | — | — | Router/Firewall (pending cutover) |

---

## Network

- **Current routing:** UniFi Dream Router (temporary, pending OPNsense cutover)
- **OPNsense:** VM 100 on pve2, installed and configured, not yet in network path
- **Subnet:** 192.168.10.0/24
- **Tailscale:** Installed on all nodes (mesh VPN for remote access)

### Switches

| Device | Model | Management IP | Notes |
|--------|-------|--------------|-------|
| Core switch | Juniper EX3400-48P | 192.168.10.50 | JunOS 23.4R2-S7.4; ge-0/0/32 is copper uplink to UniFi (access port, not trunk) |
| Secondary switch | Juniper EX2300-48P | — | — |
| Access switch | UniFi USW-24-250W | — | — |

> **⚠️ WiFi → EX3400 path is broken.** Ares on WiFi cannot reach EX3400-connected devices. Must use wired `enp0s31f6` with a static IP to access the switch and cluster nodes:
> ```bash
> sudo ip addr add 192.168.10.100/24 dev enp0s31f6
> sudo ip link set enp0s31f6 up
> ```

> **⚠️ ge-0/0/32 uplink** is configured as an access port on default VLAN only — VLANs are not yet trunked to the rest of the network. Fixing this is the next network task.

### Static IPs Assigned

| Device/Service | IP | Notes |
|---------------|----|-------|
| pve1 (Mac Mini) | 192.168.10.193 | Tailscale: 100.116.237.31 |
| pve2 | 192.168.10.204 | |
| pve3 | 192.168.10.201 | |
| pve4 | 192.168.10.202 | |
| pve5 | 192.168.10.203 | |
| Ares (Dell laptop) | DHCP / 192.168.10.100 (wired) | Tailscale: 100.124.118.63 |
| Juniper EX3400 | 192.168.10.50 | SSH: `ssh mason@192.168.10.50` |
| quarkylab iDRAC | 192.168.10.20 | R730 svc tag 1S8WR22 |
| Jarvis iDRAC | 192.168.10.21 | R730 (MAC: 18:66:da:97:0f:8e) |
| Nginx Proxy Manager | 192.168.10.181 | CT 101 on pve3, admin port 81 |
| Vaultwarden | 192.168.10.182 | CT 102 on pve3 |
| Grafana | 192.168.10.183 | CT 103 on pve3 |
| Pi-hole (primary) | 192.168.1.47 | Proxmox LXC on pve1, admin: http://192.168.1.47/admin |
| Pi-hole (backup) | 192.168.1.170 | Raspberry Pi 4 |

---

## OPNsense Configuration

### Wildcard SSL Certificate (os-acme-client)

**Plugin:** os-acme-client
**CA:** Let's Encrypt
**Challenge type:** DNS-01 via Cloudflare API
**Certificate:** `*.kylemason.org` + `kylemason.org`
**Key type:** ec-256
**Auto-renewal:** Every 90 days via Cloudflare DNS challenge

**Cloudflare API Token permissions required:**
- Zone → DNS → Edit
- Scoped to: kylemason.org only

**Steps taken:**
1. Installed os-acme-client plugin via System → Firmware → Plugins
2. Created Let's Encrypt account under Services → ACME Client → Accounts
3. Added Cloudflare DNS challenge type with API token
4. Issued wildcard certificate for `*.kylemason.org`
5. Applied cert to OPNsense web UI under System → Settings → Administration

### Tailscale

**Plugin:** os-tailscale
**Purpose:** Remote access to full home subnet when away from home
**Config:** Advertise LAN subnet route, approve in Tailscale admin console

### DNS Fix on pve3

Tailscale was overwriting `/etc/resolv.conf` with only its own DNS servers (100.100.100.100), breaking external name resolution. Fixed by:

```bash
tailscale set --accept-dns=false
cat > /etc/resolv.conf << 'EOF'
nameserver 8.8.8.8
nameserver 1.1.1.1
nameserver 100.100.100.100
EOF
```

Also set DNS in Proxmox UI: pve3 → System → DNS → 8.8.8.8, 1.1.1.1

This same issue affects pve4 and pve5 — apply the same fix if apt/DNS resolution breaks.

---

## Proxmox Post-Install (all nodes)

### Remove enterprise repos (no subscription)

```bash
rm /etc/apt/sources.list.d/pve-enterprise.sources
rm /etc/apt/sources.list.d/ceph.sources
echo "deb http://download.proxmox.com/debian/pve trixie pve-no-subscription" > /etc/apt/sources.list.d/pve-community.list
apt-get update
```

### Install Tailscale

```bash
curl -fsSL https://tailscale.com/install.sh | sh
tailscale up --advertise-routes=192.168.10.0/24
systemctl enable tailscaled
echo 'net.ipv4.ip_forward = 1' >> /etc/sysctl.conf
sysctl -p
```

Approve subnet route in Tailscale admin console.

---

## Proxmox Storage Setup (pve3)

Storage was physically present but not registered in the cluster config. Added via Datacenter → Storage:

| Storage ID | Type | Purpose |
|------------|------|---------|
| local | Directory (/var/lib/vz) | CT templates, ISO images, backups |
| local-lvm | LVM-Thin (pve/data) | Container and VM disks |

---

## CT Template

Downloaded Debian 12 Bookworm template via CLI (UI download failed due to DNS issue):

```bash
pveam update
pveam download local debian-12-standard_12.12-1_amd64.tar.zst
```

---

## Service Deployments

### CT 101 — Nginx Proxy Manager

**Purpose:** Reverse proxy for all services, SSL termination
**Node:** pve3
**IP:** 192.168.10.181 (static)
**Port:** 81 (admin UI), 80 (HTTP), 443 (HTTPS)

**LXC Specs:**
- Unprivileged container
- 8GB disk (local-lvm)
- 2 cores
- 512MB RAM / 512MB swap
- Debian 12

**Installation:**
```bash
apt update && apt upgrade -y
apt install -y curl
curl -fsSL https://get.docker.com | sh
mkdir -p /opt/nginx-proxy-manager && cd /opt/nginx-proxy-manager
```

**docker-compose.yml:**
```yaml
version: '3'
services:
  app:
    image: 'jc21/nginx-proxy-manager:latest'
    restart: unless-stopped
    ports:
      - '80:80'
      - '443:443'
      - '81:81'
    volumes:
      - ./data:/data
      - ./letsencrypt:/etc/letsencrypt
```

```bash
docker compose up -d
```

**Static IP set in** `/etc/network/interfaces`:
```
auto lo
iface lo inet loopback

auto eth0
iface eth0 inet static
    address 192.168.10.181/24
    gateway 192.168.10.1
```

**Proxy Hosts configured:**

| Domain | Forward IP | Port | SSL |
|--------|-----------|------|-----|
| vault.kylemason.org | 192.168.10.182 | 80 | Cloudflare DNS challenge |
| grafana.kylemason.org | 192.168.10.183 | 3000 | Cloudflare DNS challenge |

---

### CT 102 — Vaultwarden

**Purpose:** Self-hosted Bitwarden-compatible password manager
**Node:** pve3
**IP:** 192.168.10.182
**URL:** https://vault.kylemason.org

**LXC Specs:**
- Unprivileged container
- 10GB disk (local-lvm)
- 2 cores
- 512MB RAM / 512MB swap
- Debian 12

**Installation:**
```bash
apt update && apt upgrade -y
apt install -y curl
curl -fsSL https://get.docker.com | sh
mkdir -p /opt/vaultwarden && cd /opt/vaultwarden
```

**docker-compose.yml:**
```yaml
version: '3'
services:
  vaultwarden:
    image: vaultwarden/server:latest
    restart: unless-stopped
    ports:
      - '80:80'
    volumes:
      - ./data:/data
    environment:
      - DOMAIN=https://vault.kylemason.org
      - SIGNUPS_ALLOWED=false
```

> **Note:** `SIGNUPS_ALLOWED` was initially set to `true` to create the admin account, then set to `false` and container recreated with `docker compose up -d --force-recreate`

**Cloudflare DNS record:**
- Type: A
- Name: vault
- Value: 192.168.10.181 (NPM IP)
- Proxy: DNS only (grey cloud)

---

### CT 103 — Grafana + Prometheus + Loki

**Purpose:** Observability stack — metrics, logs, and dashboards
**Node:** pve3
**IP:** 192.168.10.183
**URL:** https://grafana.kylemason.org

**LXC Specs:**
- Unprivileged container
- 20GB disk (local-lvm)
- 2 cores
- 2048MB RAM / 512MB swap
- Debian 12

**Installation:**
```bash
apt update && apt upgrade -y
apt install -y curl
curl -fsSL https://get.docker.com | sh
mkdir -p /opt/grafana && cd /opt/grafana
mkdir -p grafana-data prometheus-data loki-data
chmod 777 grafana-data prometheus-data loki-data
```

> **Note:** Directories must be created and chmod'd before starting containers or they crash with permission errors.

**docker-compose.yml:**
```yaml
version: '3'
services:
  grafana:
    image: grafana/grafana:latest
    restart: unless-stopped
    ports:
      - '3000:3000'
    volumes:
      - ./grafana-data:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=changeme

  prometheus:
    image: prom/prometheus:latest
    restart: unless-stopped
    ports:
      - '9090:9090'
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - ./prometheus-data:/prometheus

  loki:
    image: grafana/loki:latest
    restart: unless-stopped
    ports:
      - '3100:3100'
    volumes:
      - ./loki-data:/loki
```

**prometheus.yml:**
```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'proxmox-pve3'
    static_configs:
      - targets: ['192.168.10.201:9100']
```

```bash
docker compose up -d
```

**Grafana Data Sources configured:**
- Prometheus: http://192.168.10.183:9090
- Loki: http://192.168.10.183:3100

**Dashboard imported:**
- Node Exporter Full — Grafana Dashboard ID: 1860

**Node Exporter installed on pve3:**
```bash
apt install -y prometheus-node-exporter
```

**Cloudflare DNS record:**
- Type: A
- Name: grafana
- Value: 192.168.10.181 (NPM IP)
- Proxy: DNS only (grey cloud)

---

## CrowdSec (installed on pve3 host)

**Purpose:** Collaborative intrusion prevention system
**Agent:** Watches logs for attack patterns, shares threat intel
**Bouncer:** crowdsec-firewall-bouncer — blocks IPs via iptables

**Installation:**
```bash
curl -s https://packagecloud.io/install/repositories/crowdsec/crowdsec/script.deb.sh | bash
apt install -y crowdsec
apt install -y crowdsec-firewall-bouncer
```

**Collections installed:**
```bash
cscli hub update
cscli collections install crowdsecurity/linux --force
cscli collections install crowdsecurity/sshd --force
systemctl restart crowdsec
```

**Console enrollment:**
```bash
cscli console enroll <YOUR_ENROLL_KEY>
systemctl restart crowdsec
```

> Accept enrollment at https://app.crowdsec.net

**Status at time of setup:**
- 8,546 IPs banned (HTTP brute force)
- 2,403 IPs banned (HTTP DoS)
- 2,045 IPs banned (HTTP scanning)
- 1,991 IPs banned (SSH brute force)
- 11 IPs banned (exploits)

---

## Pi-hole DNS

Originally running on pve1 (Mac Mini). Two instances for redundancy.

| Role | IP | Admin URL |
|------|----|-----------|
| Primary | 192.168.1.47 | http://192.168.1.47/admin |
| Backup | 192.168.1.170 | Raspberry Pi 4 |

Point clients to Pi-hole for ad blocking and local DNS:
```bash
sudo nmcli con mod "YourWiFiName" ipv4.dns "192.168.1.47"
sudo nmcli --ask con up "YourWiFiName"
```

---

## Pending / Deferred

### Wazuh SIEM
- **Deferred until quarkylab is online**
- Deploy as a VM (not LXC) on quarkylab
- Requires minimum 4GB RAM for the indexer
- URL will be: wazuh.kylemason.org
- Add agents on every node after deployment

### OPNsense Cutover
- Currently not in network path (Dream Router still routing)
- OPNsense is VM 100 on pve2, accessible via serial console: `qm terminal 100`
- Cutover plan: hardwire rack → swap cables → ~2 min downtime
- Pre-configure VLANs, DHCP, firewall rules before cutover

### VLANs to configure in OPNsense pre-cutover
| VLAN | Purpose |
|------|---------|
| 10 | Trusted (PCs, phones) |
| 20 | IoT (smart home, tablets) |
| 30 | Servers/Lab (Proxmox nodes) |
| 40 | Guest Wi-Fi |

### EX3400 trunk fix
- ge-0/0/32 is currently access-only (default VLAN) — VLANs not trunked to UniFi
- Need to configure proper trunk without `native-vlan-id` (not supported on EX3400)
- Once fixed, WiFi → EX3400 path will work and VLANs will propagate

### R730 quarkylab (192.168.10.20)
- iDRAC/LC must be updated to 2.86 first via TFTP `racadm fwupdate` using `firmimg.d7` (no Enterprise license required)
- Then flash BIOS via iDRAC 2.86 web UI (also no Enterprise license required)
- Known trap: mismatched CPU S-spec steppings cause silent QPI hang with no error logged — verify both CPUs match before installing

### Remaining nodes to add to monitoring
Install `prometheus-node-exporter` on each node and add to `/opt/grafana/prometheus.yml`:
```yaml
  - job_name: 'proxmox-pve2'
    static_configs:
      - targets: ['192.168.10.204:9100']

  - job_name: 'proxmox-pve4'
    static_configs:
      - targets: ['192.168.10.202:9100']

  - job_name: 'proxmox-pve5'
    static_configs:
      - targets: ['192.168.10.203:9100']
```
Then `docker compose restart prometheus` on the grafana container.

---

## Adding New Services via NPM

For every new service:
1. Deploy LXC on appropriate node
2. Add **A record** in Cloudflare: subdomain → 192.168.10.181 (NPM IP), DNS only
3. Add **Proxy Host** in NPM: domain → container IP:port, Cloudflare DNS SSL challenge
4. Install CrowdSec agent on new container/node

---

## Troubleshooting Notes

### Tailscale overwriting resolv.conf
Tailscale sets itself as the sole DNS resolver, breaking apt and external name resolution on pve3–pve5. Fix:
```bash
tailscale set --accept-dns=false
cat > /etc/resolv.conf << 'EOF'
nameserver 8.8.8.8
nameserver 1.1.1.1
nameserver 100.100.100.100
EOF
```
Also set DNS in Proxmox UI: node → System → DNS → 8.8.8.8, 1.1.1.1

### Docker containers crashing on startup (permission denied)
Pre-create data directories before running `docker compose up`:
```bash
mkdir -p grafana-data prometheus-data loki-data
chmod 777 grafana-data prometheus-data loki-data
```

### pveam template download failing
If UI download fails, use CLI after running `pveam update`:
```bash
pveam available | grep debian
pveam download local <exact-template-name>
```

### Proxmox storage not showing in UI
Storage exists but isn't registered in cluster config. Add via:
Datacenter → Storage → Add → Directory (local) and LVM-Thin (local-lvm)

### OPNsense VM serial console access (pve2)
If the web UI is unreachable, access OPNsense via serial console from pve2:
```bash
qm terminal 100
```
If the VM config is read-only: `chmod 640 /etc/pve/nodes/pve2/qemu-server/100.conf`

### Ares cannot reach EX3400/cluster nodes over WiFi
WiFi path to EX3400 is broken. Use wired interface with static IP:
```bash
sudo ip addr add 192.168.10.100/24 dev enp0s31f6
sudo ip link set enp0s31f6 up
ssh mason@192.168.10.50   # EX3400
ssh root@192.168.10.201   # pve3, etc.
```
