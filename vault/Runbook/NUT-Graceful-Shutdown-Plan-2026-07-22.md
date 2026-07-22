# 🔌 NUT Automated Graceful Shutdown — Plan

**Tags:** #plan #power #ups #nut #highavailability
**Status:** 📋 Planning — actionable now (no new hardware; NUT config only)
**Date:** 2026-07-22
**Related:** [[Power Distribution]] · [[High Availability/High Availability MOC]] · [[Rack-Environmental-Fan-Control-Plan-2026-07-22]]

---

## Goal

Wire **automated graceful shutdown** on sustained UPS battery events. Today NUT
alerts fire (Grafana + `notify-discord.sh` on ONBATT/LOWBATT) but **`upsmon` is
logging-only — nothing actually powers down**, so a long outage ends in a hard
power-cut of 512 GB R730s and Randy's ZFS pools. Listed as a planned HA item in
[[High Availability/High Availability MOC]] ("NUT automated graceful shutdown").

## Current state (from [[Power Distribution]])

- **NUT 2.8.1 on the pve3 host**, `MODE=netserver`, `upsd` on `127.0.0.1:3493` +
  `192.168.10.201:3493`. Monitors **both** UPS units; `upsmon` runs **primary,
  logging only**. Event script `/etc/nut/notify-discord.sh` already fires.
- Drivers: `tripplite` (`usbhid-ups`, USB→pve3), `midatlantic` (`snmp-ups`, SNMP
  card `192.168.10.180`).

## Topology drives the whole design (split bus)

| UPS | Driver | Feeds | Runtime |
|---|---|---|---|
| **A — Middle Atlantic** (~1320 W) | `midatlantic` | **QuarkyLab, Jarvis, Randy, DS4246** | ~10–15 min half-load; **collapses to ~2 min under ML/GPU load >1000 W** |
| **B — Tripp Lite** (~900 W) | `tripplite` | **EX3400, UniFi, EX2300, pve2–pve5, pve1 (Mac Mini), RPi** | ~15–20 min |

> **Key fact:** the NUT server (**pve3**) is itself on **UPS B**. So a UPS-A event
> leaves pve3 alive to coordinate; a UPS-B event takes pve3 **and the switch** down.

## Design decisions

### 1. Trigger on runtime/charge threshold, NOT LOWBATT
UPS-A runtime collapses under GPU load and the big R730s + Randy's ZFS export take
**minutes** to stop cleanly — waiting for the LB flag risks power dying mid-shutdown.
Trigger **early** on a runtime/charge threshold with margin. UPS-B has headroom → a
later threshold is fine.
- Cleanest mechanism: raise each UPS's `battery.runtime.low` / `battery.charge.low`
  via `upsrw` so the **LB flag asserts early** (native `upsmon` shutdown then works
  unchanged). Fallback if the driver won't allow the override (esp. `snmp-ups`
  device-controlled thresholds): an `upssched` timer watching `battery.runtime` that
  issues `FSD` early.

### 2. Shutdown ordering
1. **Guests before hosts** — each PVE host runs `qm shutdown` / `pct shutdown` (with
   timeouts) for its guests, then powers itself off. Guest agents already installed on
   OPNsense (VM 100), Wazuh (VM 104), Home Assistant (VM 110).
2. **NFS/PBS clients before the storage server** — QuarkyLab, Jarvis, and the RKE2
   nodes mount from Randy, so **Randy shuts down LAST on UPS A.**
3. On UPS B, the **EX3400 near-last** (killing it severs SSH to everything).

### 3. Distributed self-shutdown, NOT a central coordinator
A single "pve3 SSHes out and shuts everyone down in order" script works for a **UPS-A**
event (pve3 survives on UPS B) but **fails for a UPS-B event** — pve3 and the switch
are dying, so cross-network SSH is unreliable exactly when it's needed.
**Design:** every node runs `upsmon` as a **secondary** pointing at `upsd` on
`192.168.10.201:3493`, watching **the UPS that actually feeds it**, and running its
**own local** `SHUTDOWNCMD`. pve3 stays **primary** → powers off last after
secondaries release. Ordering within a bus via **staggered pre-shutdown delays**
(compute short, Randy long).

| Node | Monitors | Role |
|---|---|---|
| QuarkyLab, Jarvis | `midatlantic@192.168.10.201` (UPS A) | secondary — early trigger, short delay |
| Randy | `midatlantic@192.168.10.201` (UPS A) | secondary — **longest delay (last)** |
| pve2, pve4, pve5, pve1 | `tripplite@192.168.10.201` (UPS B) | secondary |
| **pve3** | both, locally | **primary** (powers off last) |

### 4. No HA-fencing conflict
`ha-manager` is empty (no Proxmox HA), so a mass shutdown won't trip fencing. ✅

## Implementation sketch (per secondary node)
1. `apt install nut-client`; set `MODE=netclient` in `/etc/nut/nut.conf`.
2. `/etc/nut/upsmon.conf`: `MONITOR <ups>@192.168.10.201 1 <user> <pass> secondary`
   + `SHUTDOWNCMD "/usr/local/sbin/nut-shutdown.sh"`.
3. On pve3, add a secondary user per node in `/etc/nut/upsd.users`
   (`upsmon secondary`); creds → **Vaultwarden**, never git.
4. `/usr/local/sbin/nut-shutdown.sh`: stop this host's guests (`qm`/`pct shutdown`
   with timeout), sync, `shutdown -h now`. Randy's variant sleeps a stagger delay
   first so it exits after its clients.
5. Ordering/timing via `upssched.conf` (ONBATT starts a timer; ONLINE cancels).
6. Raise `battery.charge.low` / `battery.runtime.low` via `upsrw` per §1.

## Testing (safety-critical — do this order)
1. **Dry-run first** on a **non-critical node (pve4)**: `upsmon -c fsd` with
   `SHUTDOWNCMD` swapped for a `logger`/echo stub — verify sequencing only.
2. Confirm Discord events still fire (`notify-discord.sh` unchanged).
3. Arm pve4 for real, pull-the-plug test on its UPS leg (or `upscmd` sim) with the
   rack idle.
4. Only then arm QuarkyLab/Jarvis, and **Randy last** — verify Randy's ZFS pools
   export cleanly and it powers off **after** its NFS clients.
5. Never arm the R730s/Randy before the pve4 dry-run passes.

## Open decisions
- [ ] Exact thresholds per bus (draft: UPS-A trigger at **runtime < 6 min OR charge < 50 %**; UPS-B later).
- [ ] `upsrw` LB-threshold bump vs `upssched` runtime-watch timer (driver-dependent — test `midatlantic` writability first).
- [ ] Stagger delays (draft: compute 0 s, Randy +120 s).
- [ ] Whether to also auto-shutdown pve1 (standalone, primary Pi-hole) or leave it running to the last on UPS B for DNS.
