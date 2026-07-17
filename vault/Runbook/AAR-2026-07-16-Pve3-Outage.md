# After Action Report: pve3 Outage and Cascade
**Date of incident:** 2026-07-16
**Duration:** 06:55 to 20:10 EDT (13h 15m total; user-facing services restored in stages)
**Severity:** High. All published web fronts, the password vault, all alerting, the admin VPN control plane, and (by cascade) the Kubernetes control plane were down. No data loss.
**Report filed:** 2026-07-16, same day. All times EDT unless noted.

---

## 1. Executive summary

At 06:55:04 the onboard Intel I219 NIC on pve3 suffered the well-known
`e1000e Detected Hardware Unit Hang` and stayed wedged for 12.5 hours. The host and
all six of its containers kept running; only its network died. Because pve3
concentrated NPM (every published front), Vaultwarden, the entire Grafana
monitoring/alerting stack, Headscale, Homepage, and OpenWebUI, one hung NIC silenced
the homelab's front door, password vault, and its own ability to alert about any of it.

Emergency recovery restored the fronts and alerting within two hours of detection by
PBS-restoring NPM and Grafana onto pve4. That recovery's unthrottled restore IO then
starved etcd on rke2-cp2 (same thin pool), and with the cluster already at 2 of 3
members, a single stalled member meant no quorum: both surviving RKE2 control planes
fatal-exited on lost leader leases at 12:56:00 to the second and crash-looped for ten
hours (~2,000 restarts each) behind zombie containers, until an evening health check
found it and a coordinated killall/restart recovered the cluster without data loss.

The original outage was misdiagnosed as a power/UPS failure for 13 hours. The box was
never off; Wake-on-LAN failed all day because the machine was running with a dead NIC.
A power-button press at 19:27 (clean shutdown resets the NIC) plus WoL at 19:46
revived it. Boot forensics then identified the true cause. The NIC mitigation
(TSO/GSO offloads disabled, persisted) is applied, all services are back on their
original nodes, and two monitoring gaps this incident exposed were fixed the same day.

## 2. Timeline

| Time (EDT) | Event |
|---|---|
| 06:55:04 | pve3 `e1000e` NIC hang begins (first of 22,605 kernel messages). Corosync drops pve3 within 1s. Cluster stays quorate 6/7. |
| 06:55+ | Down with pve3's network: NPM/all `*.kylemason.org` fronts, Vaultwarden, Grafana/Prometheus/Loki/InfluxDB/Scrutiny, Headscale, Homepage/PeaNUT, OpenWebUI, RKE2 cp1, NUT, CrowdSec. **Zero alerts fire: Grafana is on the dead node.** |
| 07:04 | netframe collector's first post-hang cycle. pve3 reads as scattered WARNs and even `journal_errors=OK` / `smart=OK` (no UNREACHABLE concept). No page, no DM. |
| ~08:15 | Outage discovered incidentally during unrelated work (config-drift build). Diagnosis from Ares/Jarvis: no ping, no route, 6/7 quorum, NPM dead, Grafana dead. |
| 08:2x | WoL attempted, no response. **Misdiagnosis locks in: "total power loss"** (a hung NIC is remotely indistinguishable; the switch-port link check that would have distinguished them was blocked because EX3400 credentials live in Vaultwarden, which was itself down). |
| 08:44 | Owner (remote, no physical access) approves PBS restore of NPM + Grafana to pve4. |
| 08:48–08:52 | CT 101 (8G) and CT 103 (20G) restored from the same morning's 06:00 UTC backups. Unthrottled restore stream + Grafana stack cold-start saturates pve4's thin pool, which also backs rke2-cp2's disk. |
| 08:56:00 | **RKE2 cascade.** etcd on cp2 logs 5–10s applies (1,096 warnings); 2-member etcd goes leaderless; both survivors' rke2 leader leases expire; `rke2-server` fatal-exits on cp2 and cp3 simultaneously. Restart deadlock: bootstrap needs a quorate etcd read; the crash killed containerd, orphaning zombie etcd containers that never re-elect. Crash-loop begins (~2,000 restarts/node over 10h). Not noticed: kubectl untested during emergency recovery. |
| ~09:00 | Fronts verified restored on pve4: health/console 401, Grafana serving, Discord alerting live again. Vaultwarden not restorable (VLAN 30-only; pve4 has no VLAN 30 path). Runbook #23 filed. |
| Day | Same-day hardening shipped: config-drift env-file coverage (PR #62), UNREACHABLE verdict + Grafana-independent Discord DM alerter (PR #63, live-fire validated against this outage). |
| ~18:30 | Owner requests full health check. RKE2 found dead; zombie state diagnosed (apiserver answers 401 but API hangs; etcd logs frozen since 12:56). |
| ~18:50 | Owner approves fix. `rke2-killall.sh` + simultaneous restart on cp2/cp3. Quorum restored in ~3 min; VIP reclaimed; registry and Uptime Kuma serving; 45 pods Running. Runbook addendum #24; root cause pinned via journals + LV timestamps (#25). |
| 19:27:32 | Owner restores "power" and presses the power button. `Power key pressed short` → clean shutdown at 19:28:33 (NIC hang messages continue up to the final second). The shutdown resets the NIC. |
| 19:46 | WoL loop from pve4 wakes pve3 on the second magic packet. Boot completes 19:48. |
| 19:46–19:52 | CTs 102/105/106/107 + VM 201 autostart. cp1 rejoins etcd: RKE2 back to 3/3 + randy, all Ready. Boot forensics reveal the true root cause: previous boot ran continuously since Jul 06; UPS online at 100% throughout. |
| 19:53–20:05 | NIC mitigation applied and persisted (`ethtool -K nic0 tso off gso off`, post-up in `/etc/network/interfaces`). Orphan LVs deleted. NPM migrated back to pve3 (3m09s, `--bwlimit 51200`): **vault.kylemason.org serving again after 13h.** Grafana migrated back (7m15s). |
| 20:05–20:10 | Prometheus container found Exited(255), manually started. Config-drift re-blessed (7/7 nodes; it correctly flagged both legitimate changes today). Full netframe cycle: every node clean. Deterministic alerter sends the green NODE RECOVERED DM. **Incident closed.** |

## 3. Root cause analysis

**Primary cause:** Intel I219 onboard NIC (`0000:00:1f.6`) hardware transmit-unit hang
under the `e1000e` driver, a long-documented failure mode commonly triggered by
TSO/GSO hardware offloads, which were enabled (driver defaults). The hang persisted
because nothing resets the NIC short of a driver reload or power cycle, and the box
was headless with no out-of-band management (EliteDesk, no iDRAC/IPMI).

**Cascade cause (RKE2):** the emergency restore concentrated ~28GB of unthrottled
PBS restore IO plus a monitoring-stack cold start onto the pve4 thin pool that also
backs rke2-cp2's VM disk. etcd is fsync-latency sensitive; at 2 of 3 members it has
zero stall tolerance (one slow member = no majority). RKE2 v1.35.6 amplified the
~60-second stall into a 10-hour outage via two behaviors: `rke2-server` fatal-exits
when its leader lease lapses rather than re-campaigning, and its restart requires a
quorate etcd read while its crash orphans the very etcd containers that could form
that quorum.

**Detection failure causes:**
1. The alerting stack lived on the failed node (monitoring-on-the-monitored SPOF).
2. The netframe collector had no node-unreachable concept: ssh transport failures
   fell through to per-check defaults, so a dead node read as `journal_errors=OK`,
   `smart=OK`, and scattered WARNs. Nothing said "node down."

**Misdiagnosis contributors:** WoL silence reads as "no power" but is equally
consistent with "powered on with a hung NIC." The one remote check that
distinguishes them (switch port link state) was unavailable because EX3400
credentials exist only in Vaultwarden, which was down with pve3: a circular
dependency between the credential store and the infrastructure it describes.

## 4. Impact

| Service | Down (user-facing) | Notes |
|---|---|---|
| All published fronts (health, console, grafana, homepage, vault) | 06:55–~09:00 (~2h) | Restored via PBS restore to pve4 |
| Discord alerting | 06:55–~09:00 (~2h) | Zero alerts during the window it was needed most |
| Vaultwarden (vault.kylemason.org) | 06:55–19:56 (**13h**) | VLAN 30-only, not restorable on pve4. Cached Bitwarden clients kept working offline; bw CLI dead |
| Headscale (tailnet control plane) | 06:55–19:46 (12.9h) | Established tunnels degraded gracefully |
| Homepage, OpenWebUI | 06:55–19:4x (12.9h) | |
| RKE2 control plane (kubectl, VIP) | 08:56–~18:53 (10h) | Self-inflicted cascade. Worker data plane (registry, Kuma pods) largely kept running |
| UPS monitoring (NUT) | 06:55–19:46 | pve3 is the NUT host |
| DNS | **No impact** | Pi-hole HA (.177 pve1 / .178 pve5) worked exactly as designed |
| Data | **None lost** | PBS backups were 5h old at failure; restored services carry a 06:00–06:55 config gap only; etcd recovered from disk |

## 5. What went well

1. **Backup posture.** Every pve3 guest had a same-morning PBS backup (06:00–06:02
   UTC). Restores were fast, clean, and made remote recovery possible at all.
2. **DNS HA design paid off.** The 2026-07-10 secondary Pi-hole meant a day-long
   outage of a core node caused zero DNS disruption anywhere.
3. **Remote recovery without hands.** Fronts and alerting were back ~2h after
   detection with the owner fully remote: config-move + PBS restore, conflict-safe
   for the node's eventual return (nothing double-started when pve3 revived).
4. **Same-day hardening, live-fire validated.** The two detection gaps were fixed
   during the incident itself: an UNREACHABLE verdict (a dead node now says so
   loudly) and a deterministic, Grafana-independent Discord DM path that alerted on
   this very outage and sent the recovery message when pve3 returned. The new
   config-drift env coverage also caught its first two real changes the same day.
5. **Forensics closed the loop.** Journals, LV creation timestamps, and boot history
   produced a to-the-second causal chain for both the outage and the cascade, and
   overturned a wrong 13-hour assumption with evidence.
6. **Documentation discipline held under pressure.** Four runbook PRs (#23–#26),
   tracker updates at every stage, and config-drift baselines re-blessed at each
   legitimate change.

## 6. What went wrong

1. **One node was a single point of failure for six critical services.** NPM,
   Vaultwarden, Grafana, Headscale, Homepage, and OpenWebUI all lived on pve3. The
   blast radius of one NIC was the entire homelab's face, vault, and voice.
2. **The alerting system could not report its own host's death.** Proven, not
   theoretical: zero Discord messages for a 13-hour outage.
3. **The collector actively masked the failure.** `journal_errors=OK` on a dead node
   is worse than no data; it reads as health.
4. **The recovery caused a second outage.** Unthrottled restore IO next to a
   degraded etcd took down Kubernetes for 10 hours, and nobody checked kubectl
   after the restores because attention was on the restored services.
5. **Misdiagnosis persisted ~13 hours.** "Power loss" was assumed from WoL silence
   and never re-tested against alternatives. The discriminating evidence (switch
   port link state) was locked behind the outage itself.
6. **Credential circular dependency.** EX3400 and OPNsense credentials live only in
   Vaultwarden; Vaultwarden was down; the bw CLI additionally depends on NPM and
   Pi-hole records. During exactly the incidents where switch/firewall access
   matters most, it is unavailable.
7. **No headless cold-start path.** BIOS "power on after AC loss" is off and WoL
   only works from a clean shutdown state, so a hung-then-powered-off pve3 needed a
   human finger regardless.

## 7. Corrective actions

**Completed same day:**

| # | Action | Where |
|---|---|---|
| 1 | e1000e mitigation: TSO/GSO off, persisted via post-up; backup of interfaces kept | pve3 |
| 2 | UNREACHABLE verdict in the collector (spoof-proof, ranked with TIMEOUT/AUTH-FAIL) | netframe-monitor PR #63 |
| 3 | Deterministic node-down/recovery Discord DM, independent of Grafana, no LLM in path | netframe-monitor PR #63 |
| 4 | Config-drift env-file coverage (the 07-14 outage class) + outage-safe baselines | netframe-monitor PR #62 |
| 5 | RKE2 recovery procedure documented and proven (killall + simultaneous restart) | Runbook #24 |
| 6 | Original topology restored with bandwidth-limited migrations | pve3/pve4 |

**Filed and tracked (OPEN-ITEMS):**

| # | Action | Rationale |
|---|---|---|
| 7 | RKE2 failover test with the repro recipe (IO-stall a CP disk with one member down); root-cause rke2's fatal-loop behavior | The HA control plane must be proven, not assumed |
| 8 | BIOS "power on after AC loss" on pve3 | Headless recovery after any hard-down |
| 9 | e1000e recurrence watch; escalate to InterruptThrottleRate or discrete NIC if it repeats | Mitigation, not cure |
| 10 | Restore/migrate `--bwlimit` policy near etcd or latency-critical VMs | Recovery IO is a failure vector |

**Recommendations 11–14: IMPLEMENTED same day (owner-directed, evening):**

| # | Recommendation | Status |
|---|---|---|
| 11 | Break-glass credentials outside Vaultwarden | **Built + verified** (`scripts/break-glass/`): `breakglass-refresh.sh` snapshots named Vaultwarden items into an age-encrypted file (existing DR key; plaintext never on disk) on Ares + off-host copy on Randy; `breakglass-read.sh` needs only age + the local key. Round-trip tested with the real key. **One owner action remains: run the refresh once with an unlocked bw session** (`export BW_SESSION="$(bw unlock --raw)" && ./breakglass-refresh.sh`), and re-run after any rotation. |
| 12 | De-concentrate pve3 | **Done (distribution arm):** Grafana stack (103) → pve4, Headscale (105) → pve5, both `--bwlimit`, verified serving. Alerting no longer shares a node with NPM/Vaultwarden; tailnet control plane on a third node. NPM/Vaultwarden/OpenWebUI stay pinned to pve3 by the VLAN 30 trunk (only pve3 among the EliteDesks is trunked); un-pinning them = EX3400 port change, deferred to the Compute HA item. Collector followed: prometheus wrapper + guests check on pve4, sudoers pins updated (netframe-monitor PR #64). |
| 13 | Switch-port link-state triage | **Done:** `Runbook/Triage-Node-Unreachable.md` — decision tree (host-down vs NIC-down), the exact Junos commands, WoL limits, and a node→MAC table for all 7 nodes collected while healthy. Depends on break-glass for EX3400 creds when Vaultwarden is down. |
| 14 | UPS state in the collector | **Done + live** (netframe-monitor PR #64): Jarvis polls both UPSes (tripplite, midatlantic) via pve3's LAN-listening NUT every cycle; WARN on on-battery/low-battery AND when fewer than both report — losing UPS monitoring itself now alarms instead of dying silently with its host. First cycle: both OL, 100%. |

## 8. Lessons learned

1. **A hung NIC is indistinguishable from power loss, remotely, unless you check
   link state.** Build the check into triage before the next 13-hour assumption.
2. **Monitoring must not live solely on the thing it monitors.** The deterministic
   DM path now runs from Jarvis; keep at least one alert channel independent of
   every monitored node.
3. **"No data" must never render as "OK."** Verdict systems need an explicit
   unreachable/unknown state that ranks as loudly as failure.
4. **Recovery operations are load, and load is a failure vector.** Throttle restore
   and migration IO near quorum systems, and health-check the whole estate after
   any recovery, not just the services you touched.
5. **Degraded quorum systems have zero margin.** At n-1 members, etcd's next hiccup
   is an outage; treat 2-of-3 as an active incident state, not a comfortable one.
6. **The credential store is infrastructure.** If it lives behind the same failure
   domains it documents, every incident locks the toolbox.
7. **Fresh backups turn disasters into inconveniences.** The entire recovery stood
   on backups taken 55 minutes before the failure. Keep the schedule sacred.

## 9. References

- `Runbook/Pve3-Outage-Recovery-2026-07-16.md` (incident runbook + RKE2 addendum + resolution; Home-Lab PRs #23, #24, #25, #26)
- netframe-monitor PRs #62 (config-drift env coverage), #63 (UNREACHABLE + DM alerter)
- `netframe-monitor/docs/OPEN-ITEMS.md` (tracked follow-ups)
- Grafana/Loki metrics gap: 06:00–12:52 UTC (restored from the 06:00 backup)
