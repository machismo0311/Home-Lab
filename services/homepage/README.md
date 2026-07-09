# Homepage Dashboard config

Config for the **NetFRAME** [gethomepage](https://gethomepage.dev/) dashboard.

- **Runs in:** Docker container `homepage` (`ghcr.io/gethomepage/homepage:latest`)
  inside **LXC 106 on pve3**.
- **Live config path:** `/opt/homepage/config/` in that container's host
  (bind-mounted to `/app/config`).
- **Published at:** `https://homepage.kylemason.org` via nginx-proxy-manager, behind
  the "Homepage Auth" NPM access list.

These files are a **sanitized snapshot** — the source of truth is the live config in
LXC 106. Homepage hot-reloads on file change, so edits there take effect without a
restart.

## ⚠️ Secrets are redacted

Home-Lab is a **public** repo. Every credential in `services.yaml` has been replaced
with a `<REDACTED-...>` placeholder. Before deploying this config you must restore the
real values (they live only in the running container / your password manager):

| Placeholder | Widget | What it is |
|---|---|---|
| `<REDACTED-UPS-SNMP-PASSWORD>` | `peanut` (UPS A + B) | PeaNUT/NUT `homepage` user password |
| `<REDACTED-PROXMOX-TOKEN-SECRET>` | `proxmox` (km-cluster) | Secret for API token `root@pam!homepage` |
| `<REDACTED-JELLYFIN-API-KEY>` | `jellyfin` | Jellyfin API key |

## Files

| File | Purpose |
|---|---|
| `services.yaml` | Service tiles (grouped: Infrastructure, Power & UPS, Proxmox Cluster, Storage & Backup, Monitoring & Security, Media & Apps). Includes the **NetFRAME Health** tile → `https://health.kylemason.org`. |
| `settings.yaml` | Title, theme (dark/slate), per-group layout (rows/columns). |
| `widgets.yaml` | Header widgets — logo, greeting, datetime, host resources, search. |
| `bookmarks.yaml` | Static bookmarks (Homelab / Me / Network). |
| `docker.yaml`, `proxmox.yaml`, `kubernetes.yaml` | Provider configs — currently just the shipped commented templates. |

## Deploy / update

```bash
# from this directory, restore secrets in services.yaml first, then:
for f in *.yaml; do
  cat "$f" | ssh pve3 "pct exec 106 -- bash -c 'cat > /opt/homepage/config/$f'"
done
# Homepage hot-reloads; no restart needed.
```

Pulling the live config back down (to refresh this snapshot) — remember to re-redact
secrets before committing:

```bash
for f in services.yaml settings.yaml widgets.yaml bookmarks.yaml docker.yaml proxmox.yaml kubernetes.yaml; do
  ssh pve3 "pct exec 106 -- cat /opt/homepage/config/$f" > "$f"
done
```
