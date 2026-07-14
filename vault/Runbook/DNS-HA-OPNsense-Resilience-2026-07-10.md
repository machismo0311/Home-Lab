# DNS HA + OPNsense Resilience (Tier-1 SPOF fixes) - 2026-07-10

**Tags:** #runbook #dns #pihole #opnsense #ha #dr #backup
**Related:** [[Infrastructure/Services & VMs]] · [[Networking/Network Overview]] · [[Infrastructure/Proxmox Cluster]] · [[Runbook/Recovery Procedures]]

Two of three Tier-1 single-points-of-failure closed. No disruptive changes to pve2; everything verified, not assumed.

---

## 1. Secondary Pi-hole - DNS SPOF closed ✅

**Problem:** single Pi-hole (`.177`, pve1 standalone Mac Mini). pve1 down = whole-house DNS dead.

**Fix:** second Pi-hole on a cluster node + DHCP failover.

| Field | Value |
|---|---|
| Container | **CT 108 `netframe-pihole2`** on **pve5**, unprivileged, `onboot=1` |
| IP | `192.168.10.178/24`, gw `.1` (bridge vmbr0) |
| Resources | 1 vCPU / 1 GB / 8 GB (`local-lvm`) |
| Pi-hole | v6 (matches primary) |
| Backup | added to nightly `randy-pbs` LXC job (`vmid …107,108`); first backup verified |

**Replication - nebula-sync (v0.11.2):** binary at `/usr/local/bin/nebula-sync` on CT 108, `systemd nebula-sync.timer` every 15 min (oneshot `nebula-sync.service`), `EnvironmentFile=/etc/nebula-sync.env` (600). `FULL_SYNC=true` replicates gravity/adlists/local-DNS/allow-deny **and** config (incl. admin password → both Pi-holes now share one admin password, in Vaultwarden). Note: adlist *config* syncs in 15 min but the replica compiles new lists into gravity on its own weekly `pihole -g` cron (or run manually).

**DHCP failover (the OPNsense side):** OPNsense DHCPv4 (legacy ISC `dhcpd`) now hands out **`.177` then `.178`** on **all 7 scopes** (lan + opt1–opt6 = VLANs 10/20/30/40/50/60/70). Verified via `/api/core/backup/download/this`. `.178` also has a static DHCP reservation (MAC `<MAC>`) so it's never leased out.

**Verified:** both resolvers answer; secondary blocks (576k domains, oisd+StevenBlack, matches primary) and resolves local records (`llm.netframe.local`, `homepage.kylemason.org` → `.181`).

**Rollback:** `pct stop 108 && pct destroy 108`; remove `108` from backup job; delete the second DNS line per scope in OPNsense.

---

## 2. OPNsense resilience (Tier A) - recover fast without full CARP HA ✅

Chose Tier A (cheap, low-blast-radius) over full CARP HA (needs solving the single-modem WAN hand-off; over-engineered for one household).

**Serial console - VERIFIED.** `serial0: socket` already attached to VM 100; `100.conf` perms already `640`. `qm terminal 100` from pve2 gives an OPNsense login (exit **Ctrl-O**). The June-14 "no console during outage" gap is closed.

**Encrypted config backup - LIVE + DR-tested.**
- Repo: **`machismo0311/opnsense-config-backup`** (private). Offsite = GitHub.
- `backup.sh` on **Ares**, daily cron **03:17**: pull `config.xml` via read-only-intent API key → skip if unchanged (plaintext sha) → **age-encrypt** → commit `opnsense-config-latest.xml.age` + dated `history/` copy → push. Only real changes create commits.
- **Decrypt round-trip tested** - valid XML, sha matches live config.
- Secrets (NOT in repo, `~/.config/opnsense-backup/` on Ares, 600): `api.env` (OPNsense key/secret - **least-privilege `svc-backup` user**: privileges `Diagnostics: Backup / Restore` + `Diagnostics: Configuration History`; rotated off root 2026-07-10, old root key deleted/verified dead), `age-key.txt` (**age private/decrypt key - also in Vaultwarden**). Encrypt recipient (public) `age1huwunavthrqxp56e73kn9xljc0aw2a5ax6wpta9fpz6jgvgakf6szmgcws` is in `backup.sh`.
- ⚠️ **Losing the age private key = backups unrecoverable.** Keep the Vaultwarden copy + one independent copy.

**Cold-restore runbook:** `RESTORE.md` in that repo. Covers Case A (VM dead, pve2 alive → rebuild on pve2, no cable moves) and Case B (pve2 dead → rebuild on pve3, **physically move the WAN/modem + LAN trunk cables** - there is no WAN redundancy). Includes the interface-reassign step that was the June-14 failure mode (WAN↔LAN swapped).

**Guest agent - DONE 2026-07-11 (installed + running + verified).** `qm set 100 --agent enabled=1` (pve2) + graceful ACPI reboot to add the channel. **Gotcha:** the `os-qemu-guest-agent` plugin was NOT actually installed at the pkg level despite the GUI showing a trash-can/installed icon (`pkg info` had no match, no `qemu-ga` binary) - so it had to be installed properly: from the OPNsense console shell (`qm terminal 100` → menu opt 8) `pkg install -y os-qemu-guest-agent` (pulls `qemu-guest-agent-10.0.2`), then `service qemu-guest-agent start` + `sysrc qemu_guest_agent_enable=YES`. Verified `qm agent 100 ping` rc=0. Auto-starts on future reboots. NOTE: OPNsense SSH is disabled (port 22 closed) - console/`qm terminal` is the only OPNsense shell path; ACPI graceful shutdown works regardless (validated during this reboot). ⚠️ OPNsense root password was entered over the console during this session - rotate if concerned.

---

## 3. Environment facts confirmed (were unclear/stale before)
- OPNsense DHCP backend = **legacy ISC `dhcpd`** (not Kea) - no granular API; edited via GUI.
- **Unbound** runs on `.1` as the recursive resolver (Pi-hole's upstream). Chain: client → Pi-hole (`.177`/`.178`) → Unbound (`.1`) → internet.
- pve5 gateway **fixed 2026-07-10**: was a bogus `192.168.1.1` (a pre-renumber leftover, routing via `onlink` to OPNsense's LAN MAC) → now the proper `192.168.10.1` (runtime + config, no disruption).
- Pi-hole admin password **lengthened to 24 chars 2026-07-10** (both Pi-holes + nebula-sync env updated; in Vaultwarden).

---

## 4. Still open (Tier-1)
- **Offsite backup (restic → Backblaze B2)** - PARKED: `bulk/fernanda` is empty (205 K), nothing at risk yet. Revisit when the researcher's data grows. Plan: [[Runbook/Offsite-Backup-restic-B2-Plan-2026-07-08]].
- OPNsense guest agent (next reboot); rotate/scope the OPNsense API key + rotate the shared Pi-hole password.
