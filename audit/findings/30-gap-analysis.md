# 30 — Gap Analysis (Phase 3)

**Basis:** Phase 1 repo + Phase 2 live scan. Ranked by **(risk reduced ÷ effort)**, tied to
*observed* gaps in THIS lab. Nothing already deployed is recommended.

## First: the audit spec's candidate list is partly stale — corrected against live state

| Spec candidate | Reality (live/repo) | Verdict |
|---|---|---|
| **NUT** ("highest risk, no shutdown daemon") | **DEPLOYED** — NUT 2.8.1 on pve3:3493, both UPS (SNMP `.180` + USB), PeaNUT widget, `discord-ups` alert | **Not absent** — only *verify graceful-shutdown* config (below) |
| Second Pi-hole / Unbound | **DEPLOYED** — CT 108 `netframe-pihole2` (pve5, `.178`), nebula-sync mirror, DHCP hands out both | Already done |
| ntfy/Gotify (alert delivery) | Grafana → **Discord** already delivers (`discord-alerts`/`discord-ups`) | Already covered |
| CrowdSec | **DEPLOYED** on pve3 (per AAR-2026-07-16 outage list) | Already done |
| Vaultwarden ("installed, never activated") | **ACTIVE & healthy** (CT 102, VLAN30 `.30.182`) | Spec stale |
| RKE2 / k8s integration | **DEPLOYED** — 3-node HA CP + Randy agent (Phase 1/2/5 done) | Spec stale |
| "RTX 8000 → Jarvis blocked on cables" | RTX 8000 is **installed on QuarkyLab** (07-01) | Spec stale (pre-swap) |

## Tier 1 — genuinely absent, highest value here

| # | Gap | Why it matters in THIS lab | Effort | Where |
|---|---|---|---|---|
| G1 | **Verify + fix alert *delivery*** | A drive (`mpathv`) is FAULTED right now and I could not confirm the ZfsPoolDegraded alert reached Discord. The 2026-07-16 AAR already saw "zero alerts fire". If the pipeline is silently broken, every rule is a no-op. **Verify first; this is free.** | XS | Grafana CT103/pve4 + Discord |
| G2 | **prometheus-pve-exporter** | Prometheus has only OS metrics. No cluster-quorum, per-guest, or **PBS backup-task** metrics — so there's no way to alert on "quorum lost" or "guest missed backup". Cheapest new signal given the stack exists. | S | LXC on pve4 (scrape from CT103) |
| G3 | **Backup-stale / verify-failed / cert-expiry alert rules** | pve1's Pi-hole silently has no backup (F-B1); no rule would ever tell you a backup went stale. step-ca certs expire silently. | S | Grafana rules (config-as-code repo) |
| G4 | **Offsite backup (PBS remote sync or rclone→B2)** | ALL backups live on Randy, same rack, same UPS. `bulk/fernanda` research data has no second copy. This is 1-1-1, not 3-2-1. Highest *data-loss* risk after the faulted drive. | M | Randy → B2/remote PBS |
| G5 | **pve1 into a PBS backup job** | Primary Pi-hole (CT103) + CT104 unprotected; pve1 can already reach Randy's datastore. | XS | pve1 vzdump job |
| G6 | **Oxidized (or RANCID)** | EX3400 is password-auth-only and its config isn't pulled to git (§23) — network drift is invisible until an outage. Also captures OPNsense/UniFi. | M | LXC; nightly pull |

## Tier 2 — high value

| Gap | Why |
|---|---|
| **NUT graceful-shutdown audit** | NUT *monitors* both UPS, but verify `upsmon` runs on **every** node with a working `SHUTDOWNCMD` + staged timers — monitoring ≠ orchestrated shutdown. Dual-PSU cross-feed makes ordering subtle. (Not "add NUT" — *finish* it.) |
| **SNMP exporter** | APC AP7901 PDU per-outlet draw + EX3400 port counters + UPS load are ungraphed managed power. |
| **Uptime Kuma** | Synthetic external checks (PBS:8007, Wazuh:443, Jellyfin, Ollama, llm_router) — catches "process up, service broken", which node-exporter can't. |
| **step-ca / SSO (Authentik)** | ~8 web UIs, ~8 logins; step-ca PKI already exists to back SSO. |
| **Semaphore (Ansible UI)** | The hardening + backup-verify playbooks run ad-hoc from Ares; scheduled/logged runs = auditable. |
| **Network syslog → Loki** | Confirm EX3400 + OPNsense ship logs to Loki; host logs without network logs is half the picture. |
| **NetBox** | The *reason this audit exists* — facts drift across markdown. NetBox makes IP/VLAN/rack/cabling drift structurally impossible and generates the rack diagram. Heavier lift; high long-term payoff. |

## Tier 3 — nice to have
Forgejo (local git mirror — survives GitHub loss) · MkDocs/Docusaurus from the vault ·
Diun (image-update notifications) · restic/Kopia for **Ares itself** · LibreNMS · speedtest-tracker
(FirstNet failover path).

## Still-open loops (verified against live state — the ones that ARE still open)
- **Headscale Phase 2** (QuarkyLab + Fernanda's Mac) — pending (CLAUDE.md).
- **RX 580 power cable** → Jellyfin GPU transcode — pending.
- **FreePBX 17 + CP-8841s** — not deployed.
- **Rack SVG diagram** — planned (NetBox G-tier would generate it).
- **Randy RAM 128→192 GB** (+64 on hand since 07-11) — pending.
- ~~Vaultwarden activate~~, ~~RKE2~~, ~~2nd Pi-hole~~, ~~NUT~~ — **already closed** (spec stale).

## Ranking (risk ÷ effort, top to bottom)
**G1 (verify alerts, free) → G5 (pve1 backup, XS) → G2 (pve-exporter) → G3 (alert rules) →
G4 (offsite) → G6 (Oxidized)**, then Tier 2 starting with the NUT-shutdown audit.
