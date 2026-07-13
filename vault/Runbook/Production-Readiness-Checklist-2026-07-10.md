# Production-Readiness Checklist - km-cluster (2026-07-10)

**Tags:** #checklist #production #reliability #security #ops
The punch list. ✅ done · ◐ partial · ⏳ open (P1 highest). Grounded in verified state, not a template.
Related: [[Runbook/DNS-HA-OPNsense-Resilience-2026-07-10]] · [[Runbook/Monitoring-Alerting-2026-07-10]] · [[Runbook/CI-CD-2026-07-10]] · [[Runbook/RKE2-Phase1-HA-ControlPlane-2026-07-10]] · [[Runbook/QuarkyLab-Containerd-Relocate-to-ZFS-2026-07-10]] · [[Runbook/Security-VLAN-Segmentation-Phased-2026-07-03]]

> ## Status summary (updated 2026-07-11)
> **All P1s and every actionable P2 are DONE.** Nothing open is both major *and* actionable now - the rest is gated on external conditions, physical, or deferred by design.
>
> **✅ Done:** DNS HA (secondary Pi-hole + failover) · OPNsense DR (console + encrypted config backup, key rotated+scoped) · Monitoring→Discord alerting (10 rules, config-as-code) · CI/CD (4 repos + gates) · **RKE2 k8s Phases 1–3** (HA control plane + NFS storage + first workload) · QuarkyLab disk relocation (reboot-validated, 82%→16%) · Wazuh guest-agent · CT103 secrets→.env · pve5 gateway · Pi-hole password · security segmentation Phases 1–3 (per updated tracker).
>
> **⏳ Gated / not-yet-triggered:** restic→B2 offsite (waiting on `bulk/fernanda` data) · restore Ares wired leg (physical).
>
> **◷ Deferred by design:** OPNsense CARP HA (mitigated by fast-restore) · RKE2 Phase 4 GPU scheduling (until a card frees) · peanut-ups auth→password_file (minor).

---

## 1. Reliability / Single Points of Failure
- ✅ **DNS**: secondary Pi-hole (`.178`/pve5), DHCP failover on all 7 VLANs, nebula-sync mirror.
- ✅ **DNS-down detection**: blackbox probe + `PiholePrimaryDown` alert (no more silent failover).
- ◐ **OPNsense = single VM on pve2** (whole-`/24` SPOF). Mitigated: verified serial console + DR-tested encrypted config backup + cold-restore runbook (minutes-to-recover, not the 2-h June-14 improvise). ⏳ **P2** - full CARP HA deferred (needs solving single-modem WAN hand-off; likely over-engineered for one household - revisit only if fast-restore proves insufficient).
- ⏳ **P3** - `pve1` (Pi-hole primary) is a standalone Mac mini outside km-cluster HA; acceptable now that `.178` exists.

## 2. Backup & Disaster Recovery
- ✅ PBS nightly (LXCs + VMs) on Randy; on-site RAIDZ2 + sanoid/syncoid.
- ✅ **RKE2 control-plane VMs 201/202/203 now backed up** (2026-07-12): added a daily vzdump job to randy-pbs (they were previously uncovered) and gave all three an immediate restore point. Added a **per-guest coverage check** to `backup_verify` (all 12 expected guests must be fresh, not just per-datastore freshness) which flows to the existing `BackupVerifyFailing` alert. Validated live (12/12 fresh).
- ✅ OPNsense config: nightly age-encrypted → private git (offsite), decrypt round-trip tested.
- ⏳ **P1 - Offsite backup for `bulk/fernanda`** (restic→B2): PARKED, but the trigger is **data arriving** (currently empty). Execute when the researcher's data lands. Needs: B2 account + key + passphrase→Vaultwarden.
- ⏳ **P2 - Offsite for the PBS datastore itself** (VM/CT restore points are single-site on Randy). Remote PBS sync or restic the critical-config subset to B2.
- ⏳ **P3** - quarterly **test-restore drill** (PBS + restic). An untested backup is a hope.

## 3. Monitoring & Alerting
- ✅ Prom/Grafana/Loki + Scrutiny; 10 Grafana→Discord alert rules (node/DNS/ZFS/GPU/disk/mem/UPS), 2 channels; config-as-code.
- ✅ UPS alerting verified (both units); GPU util/temp/mem collectors on QuarkyLab+Jarvis.
- ◐ **P2** - **PVE cluster-quorum alerts: collector DEPLOYED 2026-07-12.** `corosync-quorumtool` -> node_exporter textfile on all 7 nodes; `node_pve_cluster_{quorate,expected_votes,total_votes,votes_needed}` scraping in Prometheus (7/7 series). Rules `ClusterNotQuorate` (critical) + `ClusterVotesBelowExpected` (warning) staged in netframe-monitoring-stack. **Remaining:** apply the 2 rules to Grafana (API/import; needs admin cred). **WAN-failover (cellular/dpinger) alert still pending** the MR7400 WAN2 build.
- ⏳ **P3** - dashboards for the new GPU/ZFS/DNS metrics; log-based alerts in Loki.
- ⏳ **P3** - optional: Grafana file-provisioned alerting (currently API-created, persisted in `grafana-data`).

## 4. Security
- ✅ Phase 1 VLAN segmentation (OOB/BMC → VLAN 20, factory creds rotated → Vaultwarden), verified 2026-07-03.
- ✅ Wazuh SIEM, step-ca internal CA, Vaultwarden, pre-commit secret-scan hook, pentest remediation.
- ✅ **Rotated + scoped the OPNsense API key** (2026-07-10): config backup moved off the exposed root key to a least-privilege `svc-backup` user (`Backup / Restore` + `Configuration History`); old root key deleted, verified dead (401). *(Still worth doing: rotate other passwords surfaced in session transcripts if concerned.)*
- ◐ **Hardcoded secrets → env**: CT 103 compose (Grafana admin + InfluxDB) **moved to `600` `.env` 2026-07-10** ✅. Remaining: peanut-ups basic-auth still inline in `prometheus.yml` (Prometheus can't env-interpolate scrape secrets - keep `600` or use `password_file`).
- ✅ **Pi-hole admin password lengthened** (2026-07-10): 8 → 24 chars on both Pi-holes; nebula-sync env updated + sync verified; old (transcript-exposed) password dead. In Vaultwarden.
- ✅ **Security-segmentation Phases 1–3 COMPLETE** per the segmentation tracker (2026-07-10: P1 BMCs→VLAN20; P2 Vaultwarden+OpenWebUI→VLAN30, Grafana/Homepage kept on VLAN1; P3 VLAN30→VLAN1 mgmt clamp). *Completed by a parallel workstream - not independently re-verified this session; see [[Runbook/Security-VLAN-Segmentation-Phased-2026-07-03]].*

## 5. CI/CD & Change Management
- ✅ GitHub Actions lint/syntax on all 4 code/config repos (green); manual-deploy policy documented.
- ✅ Home-Lab branch-protected; private repos gated by pre-push hooks.
- ⏳ **P3** - GitHub Pro (~$4/mo) for server-side branch protection on private repos (else hooks are the gate).
- ⏳ **P3** - clean netframe-monitor's 8 ruff nits → switch its CI to full `ruff check`.
- ◐ Config-as-code: monitoring stack ✅; **Ansible is a 1-host stub** - decide grow-vs-drop (⏳ P3).

## 6. Network
- ✅ VLANs live (1/20/30/40/50/60/70); servers on VLAN 30 (dual-homed); 10G paths up.
- ✅ **pve5 gateway fixed** (2026-07-10): bogus `192.168.1.1` (pre-renumber `onlink` leftover) → `192.168.10.1`, runtime + config, no disruption.
- ⏳ **P2 - Ares wired mgmt leg `enp0s31f6` is down** (on WiFi) - restore before any pve2/OPNsense work.
- ⏳ **P3** - decide fate of pve2 `nic2`/`vmbr2` (disabled loop-hazard cable).

## 7. Storage & Compute
- ✅ ZFS pools ONLINE (Randy `bulk`+`datastore`, QuarkyLab `workspace`, Jarvis `tank`+`scratch`); pool-degraded alerting added.
- ✅ **QuarkyLab OS root** - containerd store relocated to ZFS pool + **reboot-validated + reclaimed 2026-07-11**: `/` **82% → 16%**. Cold reboot confirmed the ZFS auto-mount (drop-in), NVIDIA kernel pin, and graceful Wazuh cycle all hold. See [[Runbook/QuarkyLab-Containerd-Relocate-to-ZFS-2026-07-10]].
- ✅ **Wazuh VM 104 guest-agent installed** (2026-07-10): `qm agent 104 ping` responds; QuarkyLab reboots now gracefully shut it down (agent channel was already live → no restart/power-cycle needed; SIEM undisturbed). Reboot landmine defused.
- ⏳ **P2 - OPNsense (VM 100) qemu-guest-agent** - staged for next reboot.
- ⏳ **RKE2 CP VMs (201/202/203) qemu-guest-agent - PINNED, do when home.** Channel is already enabled (`agent: 1`); only the in-guest package is missing (2026-07-13 backup log: "skipping guest filesystem freeze - agent configured but not running?"). Install per node: `apt install qemu-guest-agent && systemctl enable --now qemu-guest-agent` (no reboot needed). Wins: graceful shutdown protects etcd on host reboot, fs-freeze gives consistent nightly backups, and `qm agent`/`guest exec` introspection (which is why the gateway check needed a hostNetwork-pod workaround). Blocker for remote automation: no SSH key/console creds to `.51/.52/.53` from Ares. All three currently verified on gateway `192.168.10.1` (host default route read via hostNetwork pods 2026-07-13).
- ✅ Randy Scrutiny false-positives silenced; boot/HBA config documented.
- ⏳ **GitHub signing-key registration - PINNED, do when home (git/security).** SSH commit signing is ON globally (id_ed25519, all commits sign + verify locally as of 2026-07-13), but the gh token lacks `admin:ssh_signing_key` scope so the key is not yet registered on GitHub and commits show unverified there. Fix: `gh auth refresh -h github.com -s admin:ssh_signing_key` then have Claude register it, OR add the pubkey in GitHub -> Settings -> SSH and GPG keys -> New SSH key -> type **Signing Key**. See [[project-git-hardening]] (memory).
- ⏳ **Scrutiny InfluxDB token rotation - PINNED, do when home (git/security, M-1).** A real 88-char InfluxDB token was committed literally to the private `netframe-monitoring-stack` repo (the `4b836f6` secrets-to-.env move missed line 56 of `ct103/docker-compose.yml`). HEAD is now redacted to `${VAR}` (2026-07-13, commit 17b37c3), but the token is still live AND still in the repo's git history. Blast radius is LOW (InfluxDB `:8086` is localhost-only on CT103, drive-health metrics, private repo), so this is hygiene not an emergency. Rotate: create a new scoped InfluxDB token on CT103 -> update `/opt/grafana/.env` `SCRUTINY_WEB_INFLUXDB_TOKEN` -> restart the Scrutiny container -> verify drive metrics resume -> revoke the old token -> store the new one in Vaultwarden. Rotation makes the historical copy dead, so no git-history rewrite is needed. See [[project-git-hardening]].

## 8. Orchestration (the remaining build-out)
- ⏳ **P2 - RKE2 not built** (blockers cleared: VLAN trunk ✅, NVIDIA drivers ✅). Plan sequenced around GPU contention vs SLURM, LXC-first house style. This is the next major project, not a gap in what runs today.

## 9. Ops Hygiene
- ✅ Runbooks + vault (mirrored, byte-identical); memory index; parallel-session git discipline.
- ⏳ **P3** - periodic `diff -rq` vault-mirror check; consider a hook to enforce it.

---

### What's actually left (nothing major + actionable remains)
The original "next 5" (OPNsense key rotate/scope, QuarkyLab disk, Wazuh agent, pve5 gateway, CT103 secrets) are **all ✅ done 2026-07-10/11**. Remaining, none urgent:
1. **restic→B2 offsite** - execute the moment `bulk/fernanda` has real data (**§2 P1**, gated).
2. **Restore Ares wired leg** `enp0s31f6` (**§6 P2**, physical - plug the cable). *(reconnected during the 2026-07-11 OPNsense reboot; verify it stays up.)*
3. **peanut-ups auth → `password_file`** in `prometheus.yml` (**§4**, minor hardening).
4. **Rotate OPNsense root password** - entered over the console 2026-07-11 (now in-session); rotate if concerned.
   *(OPNsense guest-agent ✅ done 2026-07-11 - installed+running+verified.)*
5. Deferred-by-design (revisit only if needed): OPNsense CARP HA · RKE2 Phase 4 GPU · security Phases beyond current tracker.
