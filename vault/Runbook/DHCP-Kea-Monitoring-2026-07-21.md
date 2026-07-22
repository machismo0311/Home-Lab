# DHCP / Kea Health Monitoring + DR (Phase 3, 2026-07-21)

Closes the detection gap the [[AAR-2026-07-20-DHCP-Kea-Outage]] exposed: a network-wide
DHCP outage (OPNsense Kea enabled but **0 subnets** / `kea-dhcp4` crashed) went unnoticed
until a human couldn't get on Wi-Fi. Nothing was watching DHCP itself.

## 1. Kea health monitor

- **Script:** `~/.local/bin/kea-health-monitor.py` (Ares).
- **Timer:** `kea-health-monitor.timer` (systemd `--user`) — every 10 min, `Persistent=true`.
- **Check (no API key — survives key rotation):** Ares → `ssh pve2` → `qm guest exec 100`
  (OPNsense) → `pgrep kea-dhcp4` running **and** `grep -c pools kea-dhcp4.conf ≥ 1`
  (healthy = **7**; the empty-Kea outage = **0**).
- **Alert (transitions only):** reuses the on-call Discord bot on **Jarvis**
  (`send_dm` + `/etc/netframe-alert.env`) via an arg-passed call — **the token never leaves
  Jarvis**. Fires 🔴 on down, 🟢 on recovery; first-run-healthy is silent.
- **State/log:** `~/.local/state/kea-health.{json,log}`.

**Operate:**
```bash
systemctl --user list-timers kea-health-monitor.timer   # armed?
systemctl --user start kea-health-monitor.service        # run now
tail ~/.local/state/kea-health.log                       # history
```

**⚠️ Caveat — runs on Ares (a workstation).** It's blind while Ares is off/asleep. Placed
here to avoid touching Jarvis/pve2 SSH trust (Jarvis→pve2 currently fails host-key
verification — adjacent to the deferred pve2 `.members` `.200`→`.204` issue). **Follow-up:**
move the monitor to an always-on host (Jarvis, alongside the bot) once Jarvis→pve2 SSH is
established — then it never has a blind window. Detection + alert logic are host-agnostic.

## 2. Reservation-drift — largely designed out

Phase 2 made the critical DHCP-dependent LXCs **static-in-container** (Pi-hole `.177`,
NPM `.181`, Grafana `.183`, Homepage `.148`), so they can't drift on a DHCP hiccup. The
only remaining reservation-dependent guest is **Wazuh VM 104 (`.184`)** (a VM, not an LXC).
Existing Grafana→Discord alerts (`InstanceDown`, `PiholePrimaryDown/Secondary`) cover
per-service reachability, so no separate drift probe was added — the Kea monitor covers the
systemic failure those per-service checks would only see as scattered symptoms.

## 3. DR restore of the OPNsense config

The nightly age-encrypted config backup is now **trustworthy** (see AAR §10): it reads the
**live** `/conf/config.xml` via the guest agent (the `download/this` API is stale on 25.1.x)
and runs on a `systemd --user` timer (`opnsense-config-backup.timer`, 03:17, `Persistent`).
Encrypt→decrypt round-trip verified 2026-07-21.

- **Repo:** `~/opnsense-config-backup` (`machismo0311/opnsense-config-backup`, private).
- **Restore:** follow `RESTORE.md` in that repo. Decrypt key: `~/.config/opnsense-backup/age-key.txt`
  (+ copy in Vaultwarden).
- **Verify quarterly (manual):** decrypt `opnsense-config-latest.xml.age`, confirm it parses,
  the `<revision>` is recent, and it holds the current reservations:
  ```bash
  age -d -i ~/.config/opnsense-backup/age-key.txt \
      ~/opnsense-config-backup/opnsense-config-latest.xml.age | \
    python3 -c 'import sys,xml.etree.ElementTree as ET;r=ET.parse(sys.stdin).getroot();\
print("rev",r.find("revision").findtext("time"),"staticmaps",sum(len(i.findall("staticmap")) for i in r.find("dhcpd")))'
  ```

## 4. Not done on purpose (safety)

Per the "nothing gets broken" mandate this work ran under: pve2 `.members` left as-is
(owner's call); the inactive ISC `<dhcpd>` config left in place (harmless; the Kea monitor
above is the real safeguard against another empty backend); no changes to the
actively-developed `netframe-monitor` collector (this monitor is standalone to avoid
conflicting with parallel work).
