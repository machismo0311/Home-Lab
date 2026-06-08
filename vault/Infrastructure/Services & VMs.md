# 🧩 Services & VMs
**Tags:** #infrastructure #services #docker #selfhosted  
**Related:** [[Infrastructure/Proxmox Cluster]] · [[Infrastructure/Storage]] · [[Networking/Network Overview]]

---

## Service Status Dashboard

| Service | Type | Status | Host | URL |
|---|---|---|---|---|
| OPNsense | VM | 🔴 Planned | pve-r730-gen | https://10.0.10.1 |
| Vaultwarden | Docker CT | 🔴 Planned | pve-r730-gen | https://vault.homelab.local |
| Jellyfin | VM | 🔴 Planned | pve-r730-gen | http://jellyfin.homelab.local:8096 |
| Pi-hole | Native (RPi) | 🔴 Planned | RPi 4 | http://10.0.10.20/admin |
| Home Assistant | Docker / RPi | 🔴 Planned | RPi 4 or VM | http://10.0.50.1:8123 |
| Uptime Kuma | Docker CT | 🔴 Planned | pve-g4a | http://uptime.homelab.local:3001 |
| Grafana | Docker CT | 🔴 Planned | pve-g4a | http://grafana.homelab.local:3000 |
| Loki | Docker CT | 🔴 Planned | pve-g4a | — (Grafana data source) |
| UniFi Controller | Docker CT | 🔴 Planned | pve-g4b | https://10.0.10.3:8443 |
| PBS | VM | 🔴 Planned | pve-supermicro | https://10.0.10.30:8007 |
| FreePBX | VM | ⏸️ Deferred | pve-r730-gen | http://10.0.60.5 |
| Frigate | Docker CT | ⏸️ Future | pve-g4b + Coral | — |
| NUT (UPS monitor) | Native | 🔴 Planned | RPi 4 | — |

---

## Service Configs

### Vaultwarden

```yaml
# docker-compose.yml
version: '3'
services:
  vaultwarden:
    image: vaultwarden/server:latest
    container_name: vaultwarden
    restart: unless-stopped
    volumes:
      - ./vw-data:/data
    ports:
      - "8080:80"
    environment:
      WEBSOCKET_ENABLED: "true"
      SIGNUPS_ALLOWED: "false"
      ADMIN_TOKEN: "<generate-with-argon2>"
```

### Jellyfin

```yaml
services:
  jellyfin:
    image: jellyfin/jellyfin:latest
    container_name: jellyfin
    restart: unless-stopped
    volumes:
      - ./config:/config
      - /mnt/media:/media:ro
    ports:
      - "8096:8096"
    devices:
      - /dev/dri:/dev/dri  # HW transcoding (if available)
```

### Uptime Kuma

```yaml
services:
  uptime-kuma:
    image: louislam/uptime-kuma:1
    container_name: uptime-kuma
    restart: unless-stopped
    volumes:
      - ./data:/app/data
    ports:
      - "3001:3001"
```

### Grafana + Loki Stack

```yaml
services:
  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana

  loki:
    image: grafana/loki:latest
    ports:
      - "3100:3100"

  promtail:
    image: grafana/promtail:latest
    volumes:
      - /var/log:/var/log:ro
      - ./promtail-config.yml:/etc/promtail/config.yml
```

### NUT (Network UPS Tools)

```bash
# Install on Proxmox hosts
apt install nut

# /etc/nut/ups.conf
[tripplite]
  driver = usbhid-ups
  port = auto
  desc = "Tripp Lite SMART1500VA"

[middleatlantic]
  driver = usbhid-ups
  port = auto
  desc = "Middle Atlantic UPS-2200R"

# /etc/nut/nut.conf
MODE=netserver

# /etc/nut/upsd.conf
LISTEN 0.0.0.0 3493
```

---

## Pi-hole Setup (RPi 4)

```bash
curl -sSL https://install.pi-hole.net | bash

# Post-install
pihole -a -p              # set admin password
pihole updateGravity      # update blocklists

# Set as DNS in OPNsense: Services > DHCPv4 > DNS = 10.0.10.20
```

---

## Home Assistant

```bash
# Via Docker (recommended for Proxmox VM or RPi)
docker run -d \
  --name homeassistant \
  --privileged \
  --restart=unless-stopped \
  -v /home/machismo/ha-config:/config \
  -p 8123:8123 \
  ghcr.io/home-assistant/home-assistant:stable
```

See [[Projects/IMU Gesture Control]] for IMU → HA integration.

---

## Frigate (Future — Coral TPU required)

> [!NOTE] Deferred
> Frigate NVR requires a Google Coral TPU for efficient ML inference. Purchase Coral USB/PCIe before deploying. Will run as Docker CT on pve-g4b.

---

## SSL / Reverse Proxy (Planned)

- **Nginx Proxy Manager** or **Caddy** as reverse proxy
- Let's Encrypt via DNS challenge (Cloudflare API)
- Internal cert for `*.homelab.local`
