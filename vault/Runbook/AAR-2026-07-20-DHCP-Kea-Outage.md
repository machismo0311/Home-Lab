# After Action Report: Network-Wide DHCP Outage (empty Kea backend)

**Date of incident:** 2026-07-19 (evening onset) → 2026-07-20 (resolved midday)
**Duration:** DHCP leasing down network-wide for ~12–20h (exact onset unobserved; first
logged failure 2026-07-20 00:24 EDT, resolved ~13:00 EDT). All times EDT unless noted.
**Severity:** Medium–High. No new DHCP leases anywhere; primary DNS (Pi-hole `.177`) down
by cascade. Impact was masked because existing clients kept working on valid leases +
secondary DNS `.178`. No data loss.
**Report filed:** 2026-07-20, same day.

---

## 1. Executive summary

OPNsense's DHCP service stopped handing out leases sometime the evening of 2026-07-19.
The root cause was a **backend switch from the legacy ISC `dhcpd` to Kea, where Kea was
left completely empty** — enabled, but with **zero subnets and no listening interface**.
An empty Kea starts and immediately exits, so the LAN had **no functioning DHCP server**
on any of the 7 VLAN scopes.

The blast radius was quiet by luck of timing. Every device holding a **valid lease kept
working** — it already had its IP plus both DNS servers (`.177`+`.178`), and the secondary
Pi-hole `.178` (pve5) stayed up throughout. What broke was anything that needed a **new
lease**: the owner's laptop (Ares), returning from sleep/roam, associated to Wi-Fi
perfectly but got no IP, fell back to a phone hotspot, and presented as "my Wi-Fi is
broken." The Pi-hole **primary** container `.177` (pve1 LXC 103) was itself a DHCP client
(`ip=dhcp`), so it also lost its address when its lease could not renew — taking primary
DNS down with it and turning one dead service into two.

Recovery: the empty Kea was disabled; ISC `dhcpd` would **not** restart via the API on
OPNsense 25.1.12 (ISC is deprecated on 25.1, and the box exposes no SSH — only the web UI
and API), so DHCP was restored by **rebuilding Kea to mirror the intact ISC config** —
7 subnets, pools, gateways, DNS-HA (`.177`+`.178`), and all host reservations — entirely
via the OPNsense REST API. The owner's laptop then pulled back its original lease
`192.168.10.152` with both DNS servers. Two hardening changes were made along the way, and
one wrong hypothesis (a "pve2 NIC failure") was investigated and disproven.

## 2. Timeline

| Time (EDT) | Event |
|---|---|
| 07-19 ~13:27 | Ares last renews home Wi-Fi lease `192.168.10.152` cleanly (last known-good DHCP). |
| 07-19 evening | **DHCP silently stops serving.** Onset unobserved (Ares asleep/away). OPNsense DHCP backend is now an empty Kea; ISC no longer serving. Existing clients unaffected (valid leases + `.178` DNS). |
| 07-20 00:24:32 | First **logged** failure: Ares associates to `PrettyflyforaWiFi`, `dhcp4` begins, 45s timeout, `ip-config-unavailable`, `no lease`. Loops every ~50s; NM falls back to the phone hotspot (`Das Phone`, 172.20.10.x). |
| 07-20 ~10:20 | Incident engaged ("fix my wifi"). Initial finding: Ares associates fine but gets no lease; on the hotspot, burning cellular, homelab `.10.x` unreachable. |
| 07-20 ~10:50 | A parallel Claude session briefly contended on the same NIC (MAC/priority/static edits) — corrupting results until the owner closed it. Diagnosis stabilized after. |
| 07-20 ~11:xx | Static-IP probe from Ares (`.240`) proves the LAN is healthy: gateway `.1`, pve1 `.193`, pve3 `.201` all UP; **Pi-hole `.177` DOWN**. DHCP `no lease` reproduced live. |
| 07-20 ~11:xx | Into pve1 LXC 103: Pi-hole **running**, `pihole-FTL` active, but `eth0` has **no IP** — its `net0` is `ip=dhcp` and it never got a lease. Root of the DNS-primary loss. **Pi-hole hardened: `net0` → static `192.168.10.177`** (its own reservation MAC), container rebooted, DNS restored. |
| 07-20 ~12:xx | Router located by gateway MAC `bc:24:11:12:30:00`: **OPNsense VM 100 on pve2**. VM up and routing; DHCP service dead. |
| 07-20 ~12:xx | Via OPNsense API: **Kea `enabled=1` but crashes on start; 0 subnets, no interface. Legacy ISC `<dhcpd>` config fully intact** (LAN `.100–.199`, 4 reservations, all 7 VLANs, DNS `.177`+`.178`). ISC service stopped; API `start`/`restart` no-op while Kea enabled. |
| 07-20 ~12:xx | **Kea disabled** via API. ISC still would not start (deprecated on 25.1.12, no shell to diagnose — SSH disabled on OPNsense). |
| 07-20 ~12:xx | **Kea rebuilt to mirror ISC** via API: 7 subnets + pools + gateways + reservations. Owner approved the Kea-rebuild path over further ISC attempts. Kea comes up **running**. |
| 07-20 ~13:00 | Ares reverted to DHCP → pulls **`192.168.10.152`** (its original IP), gateway via DHCP, DNS `.177`. **Wi-Fi restored.** NM profile restored to pre-incident state. |
| 07-20 ~13:xx | Cross-check against Home-Lab docs caught two rebuild gaps: DNS-HA `.178` (parser bug) and the Home Assistant `.60` static-map (stale snapshot). **Both fixed**; Ares re-leased and now receives **both** DNS servers. |
| 07-20 ~13:xx | "pve2 NIC down" hypothesis disproven: pve2 mgmt IP `.204` is UP; the real issue is a stale `/etc/pve/.members` entry (`.200`). Filed as follow-up. **Incident closed.** |

## 3. Root cause analysis

**Primary cause.** OPNsense's active DHCP backend was switched from the legacy **ISC
`dhcpd`** to **Kea**, but Kea was left **empty** — `general.enabled=1` with **no subnets and
no interface selected**. Kea DHCPv4 with nothing to serve fails to stay running; the
service flapped green→red on every start. Result: no DHCP server on any VLAN. The exact
trigger (OPNsense update vs. manual backend enable vs. a config event) is **undetermined**
— OPNsense 25.1 deprecates ISC and steers toward Kea, and the switch was not migrated.
The intact `<dhcpd>` config proves the box had been running ISC and simply had the empty
Kea activated in front of it.

**Cascade (DNS primary).** The primary Pi-hole container (pve1 LXC 103) was configured
`ip=dhcp`. When DHCP died, its lease could not renew and `eth0` went address-less, so
`192.168.10.177` went dark even though `pihole-FTL` was running. A DNS server depending on
the very DHCP service that failed is a self-inflicted second outage.

**Why it stayed hidden.** DNS is HA by design (2026-07-10): OPNsense hands out both `.177`
and `.178`, and the **secondary Pi-hole `.178` (pve5 CT 108) kept its address** and served
throughout. Every device with a live lease therefore kept name resolution and
connectivity. Only clients needing a *new* lease (Ares returning from sleep, any reboot or
roam) actually failed — so a network-wide DHCP outage surfaced as a single "laptop Wi-Fi"
complaint.

**Recovery constraint.** ISC could not be restarted to restore the exact prior backend:
on **OPNsense 25.1.12** the API `service/start|restart|reconfigure` for `dhcpd` returned
OK but never brought the daemon up or logged anything, and **OPNsense SSH is disabled**
(port 22 closed) so the daemon could not be diagnosed from a shell. The pragmatic,
owner-approved fix was to **reconstruct the config on Kea** (the supported backend) —
functionally identical for every client.

## 4. Impact

| Service / function | State during outage | Notes |
|---|---|---|
| DHCP leasing (all 7 VLANs) | **Down** ~12–20h | No new/renewed leases anywhere |
| Ares (owner laptop) Wi-Fi | **Down** until ~13:00 07-20 | Associated fine; no IP; stuck on phone hotspot |
| Pi-hole primary DNS `.177` | **Down** (cascade) | Container up, no IP (`ip=dhcp` couldn't lease) |
| Pi-hole secondary DNS `.178` | **UP throughout** | Kept its address; carried DNS for live clients |
| Devices with valid leases | **No impact** | Had IP + both DNS; why the outage stayed quiet |
| LAN routing / internet | **No impact** | OPNsense kept routing; gateway `.1` up the whole time |
| Cluster / storage / services | **No impact** | 7/7 quorate; no guest affected |
| Data | **None lost** | Config-only incident |

## 5. What went well

1. **DNS HA earned its keep.** The 07-10 secondary Pi-hole `.178` stayed up and served the
   whole outage, so a dead primary + dead DHCP still left resolution working for every
   already-connected device. The blast radius was a fraction of what it could have been.
2. **The intact ISC config made an exact rebuild possible.** Nothing had been deleted —
   pools, gateways, reservations and DNS-HA were all still in `config.xml`, so Kea could be
   populated to match rather than guessed.
3. **API-only recovery.** With SSH disabled on OPNsense and (as it turned out) cross-node
   proxying to pve2 broken, the entire fix was driven through the REST API from Ares over a
   temporary static IP — no console, no hands.
4. **Evidence over assumption.** DHCP failure was reproduced live; the "pve2 NIC down"
   hypothesis was tested against corosync/`.members`/pings and **disproven** before it
   reached this report.
5. **Cross-checking docs caught silent regressions.** Reconciling the rebuild against
   CLAUDE.md surfaced the dropped `.178` DNS and the missing HA `.60` reservation before
   they could bite.

## 6. What went wrong

1. **A DHCP backend was left empty and in front of a working one.** Enabling Kea without
   migrating the ISC config silently disabled a functioning DHCP server and replaced it
   with a crashing empty one.
2. **The primary DNS server depended on DHCP to exist.** `ip=dhcp` on the Pi-hole
   container turned a DHCP outage into a DNS outage.
3. **Nothing alerted on it.** DHCP/Kea health is not monitored; a network-wide DHCP outage
   was discovered only because a human couldn't get on Wi-Fi. Monitoring covers node/service
   up-ness but not "is the DHCP server actually leasing / does Kea have subnets."
4. **No shell path to the router under fault.** OPNsense SSH is disabled; the documented
   console path is `qm terminal 100` **from pve2** — and pve2 cross-node management was
   itself broken by the `.members` bug (below). The one time console access matters, the
   access path had its own latent fault.
5. **Config read returned a stale revision.** `/api/core/backup/download/this` served a
   ~07-13 snapshot (the known gotcha from the HA runbook), which is why the first rebuild
   missed the 07-16 HA reservation. Reconstruction from an API config read needs a
   freshness check.
6. **Rebuild parser dropped multi-value options.** Reading only the first `<dnsserver>`
   silently halved DNS-HA in the first pass.
7. **Initial misdiagnosis of pve2.** `.200` (a wrong guess for pve2's IP) was probed and
   read as a NIC failure; pve2 is actually `.204` and healthy. Corrected with evidence, but
   it briefly pointed at the wrong subsystem.

## 7. Corrective actions

**Completed during the incident:**

| # | Action | Where |
|---|---|---|
| 1 | Disabled empty Kea; **rebuilt Kea to mirror ISC** — 7 subnets, pools, gateways, 6 reservations | OPNsense VM 100 (API) |
| 2 | Restored **DNS-HA** (`.177`+`.178`) on all 7 Kea subnets | OPNsense (API) |
| 3 | Re-added **Home Assistant `.60`** reservation (missing from stale snapshot) | OPNsense (API) |
| 4 | **Hardened Pi-hole primary**: LXC 103 `net0` `ip=dhcp` → **static `192.168.10.177`** (matches its reservation; immune to future DHCP loss) | pve1 |
| 5 | Restored Ares NetworkManager profile to pre-incident state; verified `.152` lease + both DNS | Ares |
| 6 | Verified full chain: lease, gateway, internet, DNS resolution, Pi-hole reachability | — |

**Open items (follow-up):**

| # | Action | Rationale |
|---|---|---|
| 7 | **Fix pve2 `.members` address (`.200` → `.204`)** | Cross-node API proxy + web-UI management of pve2/OPNsense VM 100 is broken; console DR path depends on it. *(Next task.)* |
| 8 | **Monitor DHCP/Kea** — alert on Kea service down **and** on "0 subnets / not leasing" (an empty-but-enabled Kea reads as "service present") | This outage went undetected by design |
| 9 | **Decide ISC vs Kea and make it deliberate** — the box is now on Kea; either keep and remove the stale ISC `<dhcpd>` config, or restore ISC intentionally (needs console/shell). Don't leave two half-configured backends | Prevent a repeat empty-backend switch |
| 10 | **Update CLAUDE.md**: DHCP backend is now **Kea** (not ISC); OPNsense reports **25.1.12** (docs say 25.7 — reconcile); note the `.members` pve2 anomaly | Docs must match reality |
| 11 | **Fresh-config diff** once pve2 console/pvesh works — pull live `/conf/config.xml` and diff against the rebuilt Kea to confirm no other reservations were missed beyond `.60` | Close the stale-snapshot risk |
| 12 | **Break-glass for OPNsense** — SSH disabled + console-via-pve2 broken = no shell to the router under fault. Add a resilient admin path | Same credential/access circular-dependency lesson as the pve3 AAR |
| 13 | **Revoke the temporary OPNsense API key** created for this recovery | Key + secret transited the session |

## 8. Lessons learned

1. **An enabled service is not a working service.** Kea was "enabled" and present, yet
   served nothing. Health checks must assert function (is it leasing? does it have
   subnets?), not just process/enabled state.
2. **Don't let a dependency point at the thing that can fail.** A DNS server on `ip=dhcp`
   dies with DHCP. Infrastructure that must survive an outage should not depend on the
   service most likely to be *in* that outage. (Primary Pi-hole is now static.)
3. **HA that's invisible until tested is still worth it.** The secondary Pi-hole quietly
   absorbed most of the impact. Keep at least one leg of every critical service independent
   of the others' failure domain.
4. **Deprecation is a migration, not a toggle.** Switching ISC→Kea without carrying the
   config is an outage waiting to happen. Any backend change needs an explicit
   config-migration + verify step.
5. **Trust live state over cached reads.** `download/this` served a stale config and
   `.members` served a stale address; both nearly produced wrong conclusions. Verify
   against ground truth before acting.
6. **A hung/misaddressed management plane hides in a "quorate" cluster.** pve2 shows
   `online` on corosync (`.204`) while API proxying to it is dead (`.200`). "Quorate" ≠
   "manageable."

## 9. References

- `Runbook/DNS-HA-OPNsense-Resilience-2026-07-10.md` (DNS HA + OPNsense DR: console
  `qm terminal 100`, age-encrypted `config.xml` backup, guest-agent)
- `Runbook/Home-Assistant-Install-2026-07-16.md` (HA `.60` static-map; the
  `download/this` stale-revision note)
- `Runbook/AAR-2026-07-16-Pve3-Outage.md` (prior e1000e outage — the pattern this one was
  briefly misread as)
- OPNsense VM 100 (pve2), gateway/DHCP `192.168.10.1`; primary Pi-hole pve1 LXC 103
  (`.177`), secondary pve5 CT 108 (`.178`)
- Rebuilt Kea: 7 subnets (LAN/opt1–opt6 = .10/.20/.30/.40/.50/.60/.70), pools `.100–.199`
  (LAN) / `.100–.200` (VLANs), DNS `.177`+`.178`, 6 reservations (R2-D2 `.2`, HA `.60`,
  Pi-hole `.177`, secondary `.178`, brother-printer `.40.10`, bambu-p1s `.40.20`)
