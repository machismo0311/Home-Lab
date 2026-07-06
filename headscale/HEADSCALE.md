# NetFRAME — Headscale Deployment

> Self-hosted Tailscale control plane for NetFRAME homelab  
> Deployed: June 19–20, 2026 | Version: v0.29.1 | Node: pve3 (LXC 105)

---

## Table of Contents

- [Background](#background)
- [Architecture](#architecture)
- [Installation Record](#installation-record)
- [Current State](#current-state)
- [Operational Runbook](#operational-runbook)
- [Migration Plan](#migration-plan)
- [Pending Items](#pending-items)
- [Troubleshooting Reference](#troubleshooting-reference)
- [Configuration Reference](#configuration-reference)

---

## Background

### Problem

Fernanda's ML environment on QuarkyLab was only accessible via commercial Tailscale. The free tier provides 6 seats — 2 used by Kyle and Fernanda — leaving 4 remaining. With ~15 students needing access each semester, a self-hosted solution was required.

### Decision: Headscale

| Factor | Headscale | WireGuard (OPNsense) |
|--------|-----------|----------------------|
| User limit | Unlimited | Unlimited |
| Client experience | Native Tailscale app | Config file per student |
| User management | CLI commands | Manual key pairs |
| Semester cleanup | One command per user | Manual key revocation |
| Scale friction | Low | High (15 config files) |

Headscale was chosen for clean user lifecycle management, native client experience for students, and future Ansible automation compatibility.

---

## Architecture

### How Headscale Works

Headscale replaces Tailscale's **control plane only**. It does not replace the Tailscale client on devices and does not route traffic. After the initial handshake, devices communicate peer-to-peer via WireGuard mesh. Headscale acts as a directory service — authenticating devices and distributing WireGuard keys.

> **Key implication:** If Headscale goes down, existing connected devices stay connected. Only new registrations and auth renewals fail until it recovers.

### Cluster Placement

Headscale runs as LXC container **105** on **pve3**.

| Node | Hardware | Role | IP |
|------|----------|------|----|
| pve1 | HP EliteDesk G4 SFF | General compute | 192.168.10.200 |
| pve2 | HP EliteDesk G4 SFF | OPNsense, step-ca | 192.168.10.204 |
| **pve3** | HP EliteDesk G4 SFF | **Management services** | 192.168.10.201 |
| pve4 | HP EliteDesk G3 Mini | General compute | 192.168.10.202 |
| pve5 | HP EliteDesk G3 Mini | Fernanda ML node | 192.168.10.203 |
| QuarkyLab | Dell R730 | ML inference, RTX 8000 48GB (installed 2026-07-01) | 192.168.10.x |
| Jarvis | Dell R730 | LLM inference, 2× RTX 6000 planned | 192.168.10.x |
| Randy | SuperMicro CSE-219U | TrueNAS / storage | 192.168.10.x |

### Container Inventory on pve3

| VMID | Hostname | Role | IP |
|------|----------|------|----|
| 101 | nginx-proxy | Reverse proxy | 192.168.10.181 |
| 102 | vaultwarden | Password manager | DHCP |
| 103 | grafana | Metrics & dashboards | DHCP |
| **105** | **headscale** | **VPN coordination server** | **192.168.10.186 (static)** |

### Network Details

| Component | Value |
|-----------|-------|
| Headscale LXC IP | 192.168.10.186 |
| HTTP port | :8080 |
| gRPC port | :50443 |
| Tailscale IPv4 range | 100.64.0.0/10 |
| Tailscale IPv6 range | fd7a:115c:a1e0::/48 |
| MagicDNS base domain | netframe.local |
| DNS pushed to clients | 192.168.10.170 (Pi-hole) |

> ⚠️ **Planned:** Move to VLAN 30 (servers) before student onboarding in fall 2026.

---

## Installation Record

### Pre-flight Checks

```bash
# Verify existing containers and available IDs
pct list

# Check node resource availability
pvesh get /nodes/pve3/status

# Check cluster-wide ID usage (found 104 taken by QuarkyLab — used 105)
pvesh get /cluster/resources --type vm

# Verify Debian 12 template present
pveam list local
# Result: debian-12-standard_12.12-1_amd64.tar.zst
```

**pve3 resources at deployment:**
- RAM: 46.5 GB available / 50 GB total
- Disk: 60.7 GB available / 72 GB total
- Storage pool: `local-lvm` (lvmthin)

### LXC Creation

```bash
pct create 105 local:vztmpl/debian-12-standard_12.12-1_amd64.tar.zst \
  --hostname headscale \
  --cores 1 \
  --memory 512 \
  --swap 512 \
  --rootfs local-lvm:4 \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --ostype debian \
  --start 1 \
  --unprivileged 1

# Enable required features
pct set 105 --features nesting=1,keyctl=1
```

> **Note:** If pasting multi-line commands via SSH produces `^[[200~` prefix errors, run `printf '\e[?2004l'` first to disable bracket paste mode.

### Static IP Assignment

Container received DHCP address `192.168.10.186` — locked in as static:

```bash
pct set 105 --net0 name=eth0,bridge=vmbr0,ip=192.168.10.186/24,gw=192.168.10.1
```

> ⚠️ **Gotcha:** After setting static IP, the container interface had no IPv4 address. A reboot from inside the container was insufficient. Required full `pct stop 105 && pct start 105` from pve3 to rebuild the virtual interface.

### Headscale Installation

```bash
# Inside container: pct exec 105 -- bash
apt update && apt upgrade -y && apt install -y curl

curl -fsSL https://github.com/juanfont/headscale/releases/download/v0.29.1/headscale_0.29.1_linux_amd64.deb \
  -o headscale.deb

dpkg -i headscale.deb
```

> **Note:** Initially installed v0.23.0, then upgraded to v0.29.1 after discovering Ares was running Tailscale client v1.98.4. Upgrade required to ensure compatibility.

### Configuration Changes

Edit `/etc/headscale/config.yaml`:

| Key | Default | Set To |
|-----|---------|--------|
| `server_url` | `http://127.0.0.1:8080` | `http://192.168.10.186:8080` |
| `listen_addr` | `127.0.0.1:8080` | `0.0.0.0:8080` |
| `grpc_listen_addr` | `127.0.0.1:50443` | `0.0.0.0:50443` |
| `base_domain` | `example.com` | `netframe.local` |
| `nameservers.global` | Cloudflare IPs | `192.168.10.170` (Pi-hole) |

Also removed deprecated keys when upgrading to v0.29.1:
- `dns.use_username_in_magic_dns`
- `ephemeral_node_inactivity_timeout`
- `randomize_client_port`

### Systemd Override (LXC Namespace Fix)

The Headscale service file includes security hardening directives incompatible with unprivileged LXC containers, causing `status=226/NAMESPACE`. A drop-in override was created rather than editing the upstream service file:

```bash
mkdir -p /etc/systemd/system/headscale.service.d/
nano /etc/systemd/system/headscale.service.d/override.conf
```

```ini
[Service]
PrivateDevices=false
PrivateMounts=false
PrivateTmp=false
ProtectControlGroups=false
ProtectHostname=false
ProtectKernelLogs=false
ProtectKernelModules=false
ProtectKernelTunables=false
ProtectClock=false
ProtectProc=default
ProcSubset=all
```

```bash
systemctl daemon-reload && systemctl restart headscale
```

### Enable and Verify

```bash
systemctl enable headscale
systemctl start headscale
curl http://192.168.10.186:8080/health
# Expected: {"status":"pass"}
```

### First Device: Ares

```bash
# On Headscale container
headscale users create kyle
headscale users list  # get numeric ID — required in v0.29.1
headscale preauthkeys create --user 1 --reusable --expiration 24h
```

```bash
# On Ares (Debian 12, Tailscale v1.98.4 already installed)
sudo tailscale up \
  --login-server=http://192.168.10.186:8080 \
  --authkey=<preauthkey> \
  --reset
```

`--reset` is required when switching from commercial Tailscale to a self-hosted server.

**Verify registration:**

```bash
headscale nodes list
# ID | Hostname | User | IP addresses | Connected
# 1  | Ares     | kyle | 100.64.0.1   | online
```

---

## Current State

### Headscale Users

| ID | Username | Purpose | Status |
|----|----------|---------|--------|
| 1 | kyle | Admin / Kyle's devices | Active |
| — | fernanda | Fernanda's devices | Pending migration |
| — | student-* | Per-student, per-semester | Created at onboarding |

### Registered Nodes

| ID | Hostname | User | Tailscale IP | Status |
|----|----------|------|-------------|--------|
| 1 | Ares | kyle | 100.64.0.1 | Online |

### Commercial Tailscale Status

Fernanda and remaining devices are still on commercial Tailscale (`machismo0311@`). Migration is planned for a dedicated maintenance window after Headscale is proven stable.

---

## Operational Runbook

### Health Check

```bash
pct exec 105 -- systemctl status headscale
curl http://192.168.10.186:8080/health
pct exec 105 -- headscale nodes list
```

### Add a New User (Student Onboarding)

```bash
# Enter container
pct exec 105 -- bash

# Create user
headscale users create <username>

# Get user ID
headscale users list

# Generate pre-auth key (single use, 7-day expiry for students)
headscale preauthkeys create --user <id> --expiration 168h
```

**Student connection command (Linux/Mac):**

```bash
# Install Tailscale first: https://tailscale.com/download
sudo tailscale up --login-server=http://192.168.10.186:8080 --authkey=<key>
```

### Semester-End Cleanup

```bash
# List all nodes
headscale nodes list

# Remove student node
headscale nodes delete --identifier <node-id>

# Remove student user
headscale users destroy <user-id>

# Remove Linux account on QuarkyLab
ssh quarkylab "sudo userdel -r <username>"
```

> 📋 **Planned:** Ansible playbooks will automate both onboarding and cleanup before fall 2026 semester.

### Restart Headscale

```bash
# From pve3
pct exec 105 -- systemctl restart headscale
```

### View Logs

```bash
# Last 50 lines
pct exec 105 -- journalctl -u headscale -n 50 --no-pager

# Follow live
pct exec 105 -- journalctl -u headscale -f
```

### Revoke a Pre-Auth Key

```bash
headscale preauthkeys list --user <id>
headscale preauthkeys expire --user <id> --key <key-prefix>
```

### Upgrade Headscale

```bash
# Download new version
curl -fsSL https://github.com/juanfont/headscale/releases/download/vX.Y.Z/headscale_X.Y.Z_linux_amd64.deb \
  -o headscale-new.deb

# Install — answer N when asked about config.yaml
dpkg -i headscale-new.deb

# Check CHANGELOG for removed/deprecated config keys
# https://github.com/juanfont/headscale/blob/main/CHANGELOG.md

# Remove any deprecated keys from /etc/headscale/config.yaml

# Reload and restart
systemctl daemon-reload && systemctl restart headscale

# Verify
headscale version
curl http://192.168.10.186:8080/health
```

> ⚠️ **Always check client compatibility before upgrading.** Check the CHANGELOG for minimum supported Tailscale client versions.

### Container Management

```bash
pct start 105
pct shutdown 105   # graceful
pct stop 105       # force
pct status 105
```

---

## Migration Plan

### Phase 1 — Complete ✅ (June 19, 2026)
- [x] Headscale LXC deployed on pve3
- [x] Headscale v0.29.1 installed and running
- [x] Ares connected and verified online

### Phase 2 — Fix Ares DNS Issue
- [ ] Resolve MagicDNS `/etc/resolv.conf` permission error on Ares
- [ ] Verify `.netframe.local` hostnames resolve via Pi-hole

### Phase 3 — Migrate Kyle and Fernanda
- [ ] Choose maintenance window when Fernanda is not actively using QuarkyLab
- [ ] Stage physical console access for pve3 and QuarkyLab
- [ ] Create `fernanda` user in Headscale
- [ ] Migrate devices one at a time — verify each before touching the next

> 🚨 **Risk:** During migration each device has a brief blackout window between commercial Tailscale and Headscale. Do not migrate both devices simultaneously.

### Phase 4 — Move to VLAN 30
- [ ] Change container 105 bridge to VLAN 30
- [ ] Assign new static IP in VLAN 30 range
- [ ] Update all device `--login-server` URLs
- [ ] Create `headscale.netframe.local` DNS record

### Phase 5 — Student Onboarding (Fall 2026)
- [ ] Build Ansible playbook for automated onboarding/offboarding
- [ ] Test with one fake student account
- [ ] Write student onboarding doc (Windows/Mac/Linux)
- [ ] Onboard up to 15 students at semester start
- [ ] Run cleanup playbook at semester end

### Phase 6 — Cancel Commercial Tailscale
- [ ] After Phase 3 stable for 2+ weeks
- [ ] Downgrade or cancel commercial Tailscale account

---

## Pending Items

| Item | Description | Priority |
|------|-------------|----------|
| Ares DNS fix | Resolve MagicDNS `/etc/resolv.conf` permission error | Medium |
| Fernanda migration | Move Fernanda's devices to Headscale | High |
| Kyle device migration | Move remaining Kyle devices | High |
| VLAN 30 migration | Move Headscale to VLAN 30 before student onboarding | High |
| DNS record | Create `headscale.netframe.local` A record → 192.168.10.186 | Medium |
| TLS cert | Issue cert from step-ca; switch `server_url` to HTTPS | Medium |
| Ansible playbook | Student onboarding/offboarding automation | Medium |
| Student onboarding doc | Platform-specific connection guide | Low |
| Cancel Tailscale | After full migration complete | Low |

---

## Troubleshooting Reference

| Symptom | Cause | Fix |
|---------|-------|-----|
| `status=226/NAMESPACE` | Systemd namespace directives incompatible with LXC | Apply `override.conf` drop-in disabling PrivateDevices, PrivateMounts, PrivateTmp, ProtectProc, ProcSubset |
| Health check connection refused | Service crashed after start | Check `journalctl -u headscale -n 20` for FATAL errors |
| FATAL: config key removed | Deprecated key in config after upgrade | Remove key from `/etc/headscale/config.yaml` |
| Container has no IPv4 | Static IP not applied after `pct set` | Run `pct stop 105 && pct start 105` from pve3 (not reboot from inside) |
| Node not appearing after connect | Container unreachable from client | Verify IP assigned: `pct exec 105 -- ip addr show eth0` |
| `no route to host` | Container network not up | Full stop/start of container |
| `tailscale up` flag error | Existing settings conflict with new server | Add `--reset` flag |
| DNS warning on Ares | MagicDNS cannot modify `/etc/resolv.conf` | Known issue, non-critical, connectivity unaffected |
| `invalid argument` for `--user` flag | v0.29.1 requires numeric user ID not name | Run `headscale users list` to get ID, use `--user <id>` |

---

## Configuration Reference

### Key File Locations

| File | Purpose |
|------|---------|
| `/etc/headscale/config.yaml` | Main configuration |
| `/etc/systemd/system/headscale.service.d/override.conf` | LXC namespace override |
| `/var/lib/headscale/db.sqlite` | SQLite database (all state) |
| `/var/lib/headscale/noise_private.key` | WireGuard Noise protocol key |
| `/lib/systemd/system/headscale.service` | Upstream service file — do not edit |

### Backup

```bash
# Snapshot container before upgrades
pct snapshot 105 pre-upgrade-$(date +%Y%m%d)

# Pull critical files
pct pull 105 /var/lib/headscale/db.sqlite ./headscale-db-backup.sqlite
pct pull 105 /etc/headscale/config.yaml ./headscale-config-backup.yaml
```

### Active config.yaml Values

```yaml
server_url: http://192.168.10.186:8080
listen_addr: 0.0.0.0:8080
grpc_listen_addr: 0.0.0.0:50443
metrics_listen_addr: 127.0.0.1:9090

prefixes:
  v4: 100.64.0.0/10
  v6: fd7a:115c:a1e0::/48
  allocation: sequential

database:
  type: sqlite
  sqlite:
    path: /var/lib/headscale/db.sqlite
    write_ahead_log: true

dns:
  magic_dns: true
  base_domain: netframe.local
  nameservers:
    global:
      - 192.168.10.170   # Pi-hole
```

---

## Change Log

| Date | Version | Change |
|------|---------|--------|
| 2026-06-19 | v0.23.0 | Initial installation |
| 2026-06-19 | v0.29.1 | Upgraded for Tailscale client 1.98.4 compatibility |
| 2026-06-20 | — | Ares (100.64.0.1) registered as first node |

---

*NetFRAME Homelab — Kyle Mason (machismo) — [kylemason.org](https://kylemason.org) — [machismo0311/Home-Lab](https://github.com/machismo0311/Home-Lab)*
