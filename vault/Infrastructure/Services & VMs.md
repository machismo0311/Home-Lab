# 🧩 Services & VMs
**Tags:** #infrastructure #services #docker #selfhosted
**Related:** [[Infrastructure/Proxmox Cluster]] · [[Infrastructure/Storage]] · [[Networking/Network Overview]]

---

## Service Status Dashboard

| Service | Type | Status | Host | IP | URL / Notes |
|---|---|---|---|---|---|
| OPNsense | VM 100 | 🟢 Live router | pve2 | 192.168.10.1 | https://192.168.10.1 (v25.7) |
| Nginx Proxy Manager | LXC+Docker | 🟢 Active | pve3 CT 101 | 192.168.10.181 | http://192.168.10.181:81 (admin, Ares-only F-05) |
| Vaultwarden | LXC+Docker | 🟢 Active | pve3 CT 102 | 192.168.10.182 | https://vault.kylemason.org |
| Grafana | LXC+Docker | 🟢 Active | pve3 CT 103 | 192.168.10.183 | https://grafana.kylemason.org (v13.0.2) |
| Prometheus | LXC+Docker | 🟢 Active | pve3 CT 103 | 192.168.10.183:9090 | localhost-only (F-03); 8 node targets + peanut-ups |
| Loki | LXC+Docker | 🟢 Active | pve3 CT 103 | 192.168.10.183:3100 | - |
| InfluxDB | LXC+Docker | 🟢 Active | pve3 CT 103 | 192.168.10.183:8086 | Scrutiny backend |
| Scrutiny | LXC+Docker | 🟢 Active | pve3 CT 103 (+ collectors on Randy & QuarkyLab) | 192.168.10.183:8080 | ~50 drives |
| Homepage | LXC+Docker | 🟢 Active | pve3 CT 106 | 192.168.10.148 | https://homepage.kylemason.org |
| PeaNUT (UPS) | LXC+Docker | 🟢 Active | pve3 CT 106 | 192.168.10.148:8081 | NUT→Homepage UPS widgets |
| Headscale | LXC | 🟢 Active | pve3 CT 105 | 192.168.10.186 | http://192.168.10.186:8080 (v0.29.1) |
| Pi-hole (primary) | LXC | 🟢 Active | pve1 (Mac Mini) | 192.168.10.177 | http://192.168.10.177/admin (v6) |
| Pi-hole (secondary) | LXC | 🟢 Active | pve5 CT 108 | 192.168.10.178 | http://192.168.10.178/admin (v6) - `netframe-pihole2`, nebula-sync mirror of .177 (2026-07-10) |
| NUT (UPS) | Native | 🟢 Active | pve3 host | 192.168.10.201:3493 | Tripp Lite (USB) + Middle Atlantic (SNMP) |
| step-ca | Native | 🟢 Active | pve2 | 192.168.10.204:443 | *.netframe.local TLS |
| CrowdSec | Native | 🟢 Active | pve3 host | - | https://app.crowdsec.net |
| Wazuh SIEM | VM 104 | 🟢 Active | QuarkyLab | 192.168.10.184 | https://192.168.10.184 |
| PBS | Native | 🟢 Active | Randy | 192.168.10.187:8007 | v4.2.2, 36.7T ZFS (~23T usable) |
| Jellyfin | Native | 🟢 Active | Randy | 192.168.10.187:8096 | v10.11.11 |
| Ollama / llm_router | Native | 🟢 Active | Jarvis | `:8000` (llm.netframe.local) | Ollama v0.31.1 GPU-backed (2× RTX 6000, qwen2.5:72b); llm_router.service OpenAI-compatible (local + RAG + Claude fallback) ACTIVE 2026-07-04 |
| Open WebUI | LXC 107 | 🟢 Active | pve3 (.185) | http://chat.netframe.local | ChatGPT-style UI → llm_router (models local/rag); native pip, systemd, NPM id 6. Created 2026-07-05 |
| RKE2 Kubernetes | 3× VM (HA CP) | 🟢 Active | pve3/4/5 (VMs 201-203) | 192.168.10.54 (VIP) | v1.35.6+rke2r1; Cilium + MetalLB (.71-.75); Randy = bare-metal storage worker; kubectl from Ares (~/.kube/config-rke2). Phases 1-7 (2026-07-10/11); GPU Operator deferred |
| Container registry | k8s (on Randy) | 🟢 Active | Randy (RKE2 worker) | 192.168.10.72 | https://registry.netframe.local (MetalLB LB); registry:2, step-ca TLS + 8h auto-renew CronJob, node-local ZFS PV. See `scripts/rke2/registry/` |
| Uptime Kuma | k8s | 🟢 Active | RKE2 CP nodes | 192.168.10.71 | http://status.netframe.local (MetalLB LB); RKE2 Phase 3 pilot |
| Home Assistant | VM 110 (HAOS) | 🟢 Active | pve5 | 192.168.10.153 (DHCP) | http://homeassistant.netframe.local:8123 - HAOS 18.1 appliance (Supervisor + add-on store); installed 2026-07-16, onboarding pending. See [[Runbook/Home-Assistant-Install-2026-07-16]] |
| FreePBX | VM | ⏸️ Deferred | TBD | - | - |

---

## Deployed Configs (pve3)

All services below run as Docker containers in LXC containers on pve3. Each CT uses a static IP, Debian 12, Docker installed via `curl -fsSL https://get.docker.com | sh`.

### CT 101 - Nginx Proxy Manager

**IP:** 192.168.10.181 | **Ports:** 80, 443, 81 (admin) | **Disk:** 8GB

```yaml
# /opt/nginx-proxy-manager/docker-compose.yml
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

**Proxy Hosts:**

| Domain | Forward to | Port | SSL |
|--------|-----------|------|-----|
| vault.kylemason.org | 192.168.10.182 | 80 | Cloudflare DNS-01 |
| grafana.kylemason.org | 192.168.10.183 | 3000 | Cloudflare DNS-01 |
| homepage.kylemason.org | 192.168.10.148 | 3000 | Cloudflare DNS-01 + basic auth (kyle) |
| wazuh.kylemason.org | 192.168.10.184 | 443 | Cloudflare DNS-01 |

**Cloudflare DNS records** (for each subdomain):
- Type: A → 192.168.10.181, DNS only (grey cloud)

---

### CT 102 - Vaultwarden

**IP:** 192.168.10.182 | **URL:** https://vault.kylemason.org | **Disk:** 10GB

```yaml
# /opt/vaultwarden/docker-compose.yml
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

> Initial setup: set `SIGNUPS_ALLOWED=true`, create account, then set back to `false` and `docker compose up -d --force-recreate`.

---

### CT 103 - Grafana + Prometheus + Loki

**IP:** 192.168.10.183 | **URL:** https://grafana.kylemason.org | **Disk:** 20GB, 2GB RAM

```yaml
# /opt/grafana/docker-compose.yml
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
      - GF_SECURITY_ADMIN_PASSWORD=<set-a-strong-password>   # bootstrap only; rotated post-setup, stored in Vaultwarden

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

> Pre-create data dirs: `mkdir -p grafana-data prometheus-data loki-data && chmod 777 grafana-data prometheus-data loki-data`

**prometheus.yml** (add targets as nodes are onboarded):
```yaml
global:
  scrape_interval: 15s
scrape_configs:
  - job_name: 'proxmox-pve3'
    static_configs:
      - targets: ['192.168.10.201:9100']
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

**Dashboard:** Node Exporter Full - ID 1860
**Node exporter on each host:** `apt install -y prometheus-node-exporter`
After adding targets: `docker compose restart prometheus`

#### Alerting (2026-07-10) - Grafana → Discord
Grafana v13 Unified Alerting → native Discord (no Alertmanager). Channels: `discord-alerts` (infra, label `notify=infra`) and `discord-ups` (UPS, root). 10 rules live: InstanceDown, PiholePrimaryDown/SecondaryDown, ZfsPoolDegraded, GpuTempHigh, GpuMemoryHigh, DiskAlmostFull, LowMemory, UPS battery/runtime. Added **blackbox_exporter** (`:9115`, `dns_ok` DNS probe of `.177`/`.178` → `probe_success`), a **ZFS pool textfile collector** on Randy/QuarkyLab/Jarvis (`node_zfs_pool_health`), and an **nvidia-smi GPU textfile collector** on QuarkyLab/Jarvis (`nvidia_gpu_*`). **Config-as-code:** private repo `machismo0311/netframe-monitoring-stack`. Full detail: [[Runbook/Monitoring-Alerting-2026-07-10]].

---

### CT 105 - Headscale

**IP:** 192.168.10.186 | **Ports:** 8080 (HTTP), 50443 (gRPC) | **Disk:** 4GB | **RAM:** 512MB

Self-hosted Tailscale control plane (WireGuard mesh coordination). Replaces commercial Tailscale for student access to QuarkyLab ML environment.

| Detail | Value |
|--------|-------|
| Version | v0.29.1 |
| MagicDNS domain | netframe.local |
| Tailscale IPv4 range | 100.64.0.0/10 |
| DNS pushed to clients | 192.168.10.177 (Pi-hole) |
| Registered nodes | Ares (.1), Randy (.2), pve5 (.3), pve4 (.4), pve3 (.5), Jarvis (.6) |

```bash
# Health check
curl http://192.168.10.186:8080/health

# Node list
pct exec 105 -- headscale nodes list

# Add student user
pct exec 105 -- headscale users create <username>
pct exec 105 -- headscale preauthkeys create --user <id> --expiration 168h
```

> Full runbook: `Home-Lab/headscale/HEADSCALE.md` · See also [[Projects/Headscale]]

---

## CrowdSec (pve3 host)

```bash
curl -s https://packagecloud.io/install/repositories/crowdsec/crowdsec/script.deb.sh | bash
apt install -y crowdsec crowdsec-firewall-bouncer

cscli hub update
cscli collections install crowdsecurity/linux --force
cscli collections install crowdsecurity/sshd --force
systemctl restart crowdsec

cscli console enroll <YOUR_ENROLL_KEY>
systemctl restart crowdsec
```

Console: https://app.crowdsec.net

---

## Pi-hole (DNS - primary + secondary HA)

| Role | IP | Host | Admin |
|------|----|------|-------|
| Primary | 192.168.10.177 | pve1 LXC (standalone Mac Mini) | http://192.168.10.177/admin (v6) |
| Secondary | 192.168.10.178 | pve5 CT 108 `netframe-pihole2` | http://192.168.10.178/admin (v6) |

> **DNS HA (2026-07-10):** OPNsense DHCP hands out **both** `.177` and `.178` as DNS on **all 7 VLAN scopes**, so clients fail over automatically. The secondary is a full mirror of the primary via **nebula-sync** (systemd `nebula-sync.timer` every 15 min on CT 108 - replicates gravity/adlists/local-DNS/allow-deny). Both admin passwords unified (in Vaultwarden). CT 108 is in the nightly `randy-pbs` LXC backup. The old RPi 4 backup Pi-hole (formerly `192.168.1.170`) is decommissioned. Full detail: [[Runbook/DNS-HA-OPNsense-Resilience-2026-07-10]].

---

## Adding New Services

For every new service:
1. Deploy LXC on appropriate node (Debian 12, static IP)
2. Add A record in Cloudflare: subdomain → 192.168.10.181, DNS only
3. Add Proxy Host in NPM → container IP:port, Cloudflare DNS SSL
4. Install CrowdSec agent on the new container

---

## Planned / Deferred

### UniFi Controller
- Pending deployment decision / node placement (Jellyfin is already live on Randy - see active services above; Home Assistant deployed to pve5 VM 110 on 2026-07-16)
- See [[Infrastructure/Proxmox Cluster]] for hardware status

### Frigate (NVR)
- Requires Google Coral TPU for ML inference
- Future deployment on available node
