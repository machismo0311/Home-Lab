# Homepage Dashboard Setup
**Date:** 2026-06-26
**Location:** pve3 LXC 106 (hostname `homepage`, 192.168.10.148)
**URL:** https://homepage.kylemason.org (Let's Encrypt, basic auth)

---

## What Was Built

Homepage (gethomepage.dev, Docker in LXC 106) configured from default placeholders to a
full NetFRAME dashboard with **live status widgets**.

### Service groups (services.yaml)
- **Infrastructure**: OPNsense, Pi-hole, NPM, Headscale
- **Proxmox Cluster**: km-cluster (widget), Randy, QuarkyLab, Jarvis
- **Storage & Backup**: PBS, Scrutiny (widget)
- **Monitoring & Security**: Grafana, Prometheus, Wazuh
- **Media & Apps**: Jellyfin (widget), Vaultwarden

### Live widgets (verified pulling data)
| Widget | Auth method | Status |
|---|---|---|
| Proxmox | API token `root@pam!homepage` (PVEAuditor) | 7 nodes ✅ |
| Pi-hole | v6, no API password set | live ✅ |
| Jellyfin | API key (inserted into jellyfin.db ApiKeys) | live ✅ |
| Scrutiny | no auth | 43 drives ✅ |

API tokens live in `/opt/homepage/config/services.yaml` inside LXC 106 — **not in git**.
docker-compose has `NODE_TLS_REJECT_UNAUTHORIZED=0` so the Proxmox HTTPS (self-signed) widget works.

---

## Access Layer (NPM)

**Correction to prior docs:** NPM is NOT empty. It runs as a Docker container inside LXC 101
(`nginx-proxy-manager-app-1`, v2.15.1) — the proxy host configs live in the *container's*
`/data`, not the LXC's. There are 4 proxy hosts: vault, grafana, homepage, wazuh.

The `homepage.kylemason.org` proxy host (id 4) already forwarded to `192.168.10.148:3000`
but had **no SSL cert** (`certificate_id: 0`) — that's why `:443` failed. Fixed:

- **Cert (id 6):** Let's Encrypt via **Cloudflare DNS-01** challenge. Auto-renews (CF token
  stored in NPM). Valid → 2026-09-23.
- **Auth:** NPM access list (id 2), basic auth, user `kyle`.
- Proxy host id 4 updated: `certificate_id=6`, `ssl_forced=true`, `access_list_id=2`,
  http2 + block_exploits + websocket on.

NPM API workflow (v2.15.1): `meta` for LE certs only allows `dns_challenge`, `dns_provider`,
`dns_provider_credentials`, `propagation_seconds`, `key_type` — `letsencrypt_email`/`_agree`
are NOT valid meta fields (taken from account/global config).

---

## DNS

Two records resolve `homepage.kylemason.org → 192.168.10.181` (NPM):
- **Cloudflare public A-record** (DNS-only / not proxied) — resolves for ALL devices regardless
  of their DNS. Needed because Ares + most devices use public resolvers (8.8.8.8/1.1.1.1), not
  Pi-hole. Points at a private IP (benign; internal-only access by design).
- **Pi-hole v6 local record** (`dns.hosts` via `pihole-FTL --config`) — for Pi-hole clients.

Note: browsers cache the pre-existing NXDOMAIN (negative cache) — clear browser/OS DNS cache
after adding the record.

---

## Verification
```
https://homepage.kylemason.org → 401 (no auth) / 200 (with creds)
SSL: issuer = Let's Encrypt, CN = homepage.kylemason.org
```

Credentials delivered to user out-of-band (not stored here).

---

## Addendum — UPS widgets + tile fixes (2026-06-26)

### Power & UPS group (PeaNUT)
- Homepage v1.13 has **no `nut` widget** — NUT is surfaced only via the **`peanut`** widget, which needs a **PeaNUT** instance.
- Added `peanut` container to `/opt/homepage/docker-compose.yml` (`brandawg93/peanut`, `8081→8080`, `NUT_HOST=192.168.10.201`, basic-auth user `homepage`).
- `services.yaml` "Power & UPS" group: two `peanut` widgets — **UPS A** = Middle Atlantic (`midatlantic`), **UPS B** = Tripp Lite (`tripplite`). Full NUT→PeaNUT→Prometheus→Grafana→Discord stack documented in Power Distribution.md.

### Tile siteMonitor fixes
| Tile | Was | Now |
|---|---|---|
| Headscale | `:80` (refused) | `http://192.168.10.186:8080` |
| Nginx Proxy Manager | siteMonitor `:81` (DROP-except-Ares, F-05) | siteMonitor `:80`; href stays `:81` |
| Grafana | `:3000` (filtered from LXC 106) | `https://grafana.kylemason.org` (NPM path) |
| Prometheus | `:9090` (127.0.0.1-only, F-03) | siteMonitor removed; label only |

> Homepage `siteMonitor` checks run **server-side from the container**, so services firewalled away from LXC 106 (NPM admin :81, Prometheus localhost) can't be probed that way — point them at a reachable endpoint or drop the monitor.

### Basic-auth note
- The Homepage basic-auth user (`kyle`) and the Grafana admin password are **distinct** credentials; both are stored in Vaultwarden. (NPM keeps its access-list htpasswd material under `/data` on the NPM container — treat that path as sensitive.)
