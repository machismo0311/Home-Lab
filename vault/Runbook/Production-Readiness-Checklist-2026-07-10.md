# Production-Readiness Checklist — km-cluster (2026-07-10)

**Tags:** #checklist #production #reliability #security #ops
The punch list. ✅ done · ◐ partial · ⏳ open (P1 highest). Grounded in verified state, not a template.
Related: [[Runbook/DNS-HA-OPNsense-Resilience-2026-07-10]] · [[Runbook/Monitoring-Alerting-2026-07-10]] · [[Runbook/CI-CD-2026-07-10]] · [[Runbook/Security-VLAN-Segmentation-Phased-2026-07-03]]

---

## 1. Reliability / Single Points of Failure
- ✅ **DNS**: secondary Pi-hole (`.178`/pve5), DHCP failover on all 7 VLANs, nebula-sync mirror.
- ✅ **DNS-down detection**: blackbox probe + `PiholePrimaryDown` alert (no more silent failover).
- ◐ **OPNsense = single VM on pve2** (whole-`/24` SPOF). Mitigated: verified serial console + DR-tested encrypted config backup + cold-restore runbook (minutes-to-recover, not the 2-h June-14 improvise). ⏳ **P2** — full CARP HA deferred (needs solving single-modem WAN hand-off; likely over-engineered for one household — revisit only if fast-restore proves insufficient).
- ⏳ **P3** — `pve1` (Pi-hole primary) is a standalone Mac mini outside km-cluster HA; acceptable now that `.178` exists.

## 2. Backup & Disaster Recovery
- ✅ PBS nightly (LXCs + VMs) on Randy; on-site RAIDZ2 + sanoid/syncoid.
- ✅ OPNsense config: nightly age-encrypted → private git (offsite), decrypt round-trip tested.
- ⏳ **P1 — Offsite backup for `bulk/fernanda`** (restic→B2): PARKED, but the trigger is **data arriving** (currently empty). Execute when the researcher's data lands. Needs: B2 account + key + passphrase→Vaultwarden.
- ⏳ **P2 — Offsite for the PBS datastore itself** (VM/CT restore points are single-site on Randy). Remote PBS sync or restic the critical-config subset to B2.
- ⏳ **P3** — quarterly **test-restore drill** (PBS + restic). An untested backup is a hope.

## 3. Monitoring & Alerting
- ✅ Prom/Grafana/Loki + Scrutiny; 10 Grafana→Discord alert rules (node/DNS/ZFS/GPU/disk/mem/UPS), 2 channels; config-as-code.
- ✅ UPS alerting verified (both units); GPU util/temp/mem collectors on QuarkyLab+Jarvis.
- ⏳ **P2** — WAN-failover (cellular/dpinger) + PVE cluster-quorum alerts (no OPNsense/pve-exporter metrics yet).
- ⏳ **P3** — dashboards for the new GPU/ZFS/DNS metrics; log-based alerts in Loki.
- ⏳ **P3** — optional: Grafana file-provisioned alerting (currently API-created, persisted in `grafana-data`).

## 4. Security
- ✅ Phase 1 VLAN segmentation (OOB/BMC → VLAN 20, factory creds rotated → Vaultwarden), verified 2026-07-03.
- ✅ Wazuh SIEM, step-ca internal CA, Vaultwarden, pre-commit secret-scan hook, pentest remediation.
- ✅ **Rotated + scoped the OPNsense API key** (2026-07-10): config backup moved off the exposed root key to a least-privilege `svc-backup` user (`Backup / Restore` + `Configuration History`); old root key deleted, verified dead (401). *(Still worth doing: rotate other passwords surfaced in session transcripts if concerned.)*
- ◐ **Hardcoded secrets → env**: CT 103 compose (Grafana admin + InfluxDB) **moved to `600` `.env` 2026-07-10** ✅. Remaining: peanut-ups basic-auth still inline in `prometheus.yml` (Prometheus can't env-interpolate scrape secrets — keep `600` or use `password_file`).
- ⏳ **P2** — lengthen the shared Pi-hole admin password (8 chars).
- ⏳ **P2** — Security-segmentation **Phases 2–3** (services VLAN 30 enforcement, mgmt-plane) — not started.
- ⏳ **P2** — OPNsense firewall: deny non-Ares→VLAN 20 + no BMC egress (Phase 1.5, still pending).

## 5. CI/CD & Change Management
- ✅ GitHub Actions lint/syntax on all 4 code/config repos (green); manual-deploy policy documented.
- ✅ Home-Lab branch-protected; private repos gated by pre-push hooks.
- ⏳ **P3** — GitHub Pro (~$4/mo) for server-side branch protection on private repos (else hooks are the gate).
- ⏳ **P3** — clean netframe-monitor's 8 ruff nits → switch its CI to full `ruff check`.
- ◐ Config-as-code: monitoring stack ✅; **Ansible is a 1-host stub** — decide grow-vs-drop (⏳ P3).

## 6. Network
- ✅ VLANs live (1/20/30/40/50/60/70); servers on VLAN 30 (dual-homed); 10G paths up.
- ✅ **pve5 gateway fixed** (2026-07-10): bogus `192.168.1.1` (pre-renumber `onlink` leftover) → `192.168.10.1`, runtime + config, no disruption.
- ⏳ **P2 — Ares wired mgmt leg `enp0s31f6` is down** (on WiFi) — restore before any pve2/OPNsense work.
- ⏳ **P3** — decide fate of pve2 `nic2`/`vmbr2` (disabled loop-hazard cable).

## 7. Storage & Compute
- ✅ ZFS pools ONLINE (Randy `bulk`+`datastore`, QuarkyLab `workspace`, Jarvis `tank`+`scratch`); pool-degraded alerting added.
- ⏳ **P1 — QuarkyLab OS root at ~82%** (containerd store) — planned-outage relocation to ZFS pending (see [[project-quarkylab-containerd-relocate]]).
- ✅ **Wazuh VM 104 guest-agent installed** (2026-07-10): `qm agent 104 ping` responds; QuarkyLab reboots now gracefully shut it down (agent channel was already live → no restart/power-cycle needed; SIEM undisturbed). Reboot landmine defused.
- ⏳ **P2 — OPNsense (VM 100) qemu-guest-agent** — staged for next reboot.
- ✅ Randy Scrutiny false-positives silenced; boot/HBA config documented.

## 8. Orchestration (the remaining build-out)
- ⏳ **P2 — RKE2 not built** (blockers cleared: VLAN trunk ✅, NVIDIA drivers ✅). Plan sequenced around GPU contention vs SLURM, LXC-first house style. This is the next major project, not a gap in what runs today.

## 9. Ops Hygiene
- ✅ Runbooks + vault (mirrored, byte-identical); memory index; parallel-session git discipline.
- ⏳ **P3** — periodic `diff -rq` vault-mirror check; consider a hook to enforce it.

---

### Suggested next 5 (by risk×effort)
1. Rotate/scope the OPNsense root API key + move CT 103 secrets out of compose (**§4 P1**).
2. QuarkyLab root-disk relocation (**§7 P1**) — it's climbing.
3. Wazuh guest-agent (**§7 P2**) — one reboot away from a broken SIEM.
4. Restore Ares wired leg (**§6 P2**). *(pve5 gateway ✅ 2026-07-10.)*
5. Execute restic→B2 the moment `bulk/fernanda` has data (**§2 P1**).
