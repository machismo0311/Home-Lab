# 🔒 Headscale — Self-Hosted VPN Control Plane
**Tags:** #project #networking #vpn #tailscale #headscale
**Related:** [[Infrastructure/Services & VMs]] · [[Networking/Network Overview]] · [[Runbook/Daily Operations]]

---

> **Status:** Phase 1 complete — Ares connected. the researcher migration pending.
> **Full runbook:** `Home-Lab/headscale/HEADSCALE.md`

---

## Summary

Headscale replaces the commercial Tailscale control plane for NetFRAME. It lets unlimited students connect to QuarkyLab's ML environment using the native Tailscale app, with per-semester lifecycle management via CLI. The commercial Tailscale free tier (6 seats) couldn't scale to ~15 students per semester.

Headscale handles **authentication and key distribution only** — it does not carry traffic. After registration, devices communicate peer-to-peer via WireGuard. If Headscale goes down, existing connections stay up.

---

## Deployment Details

| Item | Value |
|------|-------|
| Host | pve3 CT 105 |
| IP | 192.168.10.186 |
| Version | v0.29.1 |
| MagicDNS domain | netframe.local |
| Tailscale IP range | 100.64.0.0/10 |
| DNS | 192.168.10.177 (Pi-hole) |

---

## Phase Status

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Deploy Headscale, connect Ares | ✅ Complete (2026-06-19) |
| 2 | Fix Ares MagicDNS `/etc/resolv.conf` error | ⏳ Pending |
| 3 | Migrate Kyle + the researcher off commercial Tailscale | ⏳ Pending |
| 4 | Move CT 105 to VLAN 30, new static IP | ⏳ Pending |
| 5 | Student onboarding (fall 2026, ~15 students) | ⏳ Pending |
| 6 | Cancel commercial Tailscale account | ⏳ Pending |

---

## Quick Reference

```bash
# Health
curl http://192.168.10.186:8080/health

# Nodes
pct exec 105 -- headscale nodes list

# Add student (7-day key)
pct exec 105 -- headscale users create <name>
pct exec 105 -- headscale users list   # get numeric ID
pct exec 105 -- headscale preauthkeys create --user <id> --expiration 168h

# Student connect command
sudo tailscale up --login-server=http://192.168.10.186:8080 --authkey=<key>
```

---

## Known Issues

| Issue | Status |
|-------|--------|
| Ares MagicDNS permission error on `/etc/resolv.conf` | Open — non-critical, connectivity unaffected |
| the researcher still on commercial Tailscale | Pending migration window |
| No TLS — server_url is plain HTTP | Planned: step-ca cert after VLAN 30 migration |
