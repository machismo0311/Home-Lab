# 40 — Remediation Backlog

Every finding as a ticket. **Sev · Effort · Blast radius · Fix · Rollback.** Kyle picks; this
audit executes none of the infra items (read-only). Doc items map to the Phase 4 PR.

## Operational (infra — NOT done by audit)

### R-01 · CRITICAL — Replace faulted `bulk` drive `mpathv`
- **Effort:** S (physical swap + resilver). **Blast radius:** the `bulk` pool; a 2nd fault in
  `raidz2-2` before replace = data loss.
- **Fix:** identify bay for WWN `5000c500631a54fb` (Seagate ST4000NM0023); insert a ≥4TB drive
  (2 free bays); `zpool replace bulk mpathv <new-by-id>`; watch resilver; scrub after.
- **Rollback:** n/a (replacing a dead drive). If new drive faults, pull it — pool returns to
  current degraded (not worse). **Do this first.**

### R-02 · CRITICAL/UNKNOWN — Verify ZfsPoolDegraded alert delivered to Discord
- **Effort:** XS. **Blast radius:** none (read).
- **Fix:** check `discord-alerts` for a `bulk` degraded alert (last 3 days). If absent, inspect
  Grafana rule eval + Discord contact point. **A silent CRITICAL is worse than no monitoring.**
- **Rollback:** n/a.

### R-03 · HIGH — Back up standalone pve1 (primary Pi-hole CT103 + CT104)
- **Effort:** XS. **Blast radius:** low (adds a PBS job).
- **Fix:** add a vzdump job on pve1 → Randy `datastore` (reachable); `keep-daily=7,keep-weekly=4`.
- **Rollback:** delete the job. (Mitigation exists: secondary Pi-hole CT108 is backed up + synced.)

### R-04 · HIGH — Offsite backup (3-2-1)
- **Effort:** M. **Blast radius:** low (additive). **Fix:** PBS remote-sync to a second PBS, or
  `rclone`/PBS→Backblaze B2 for `datastore` (+ `bulk/fernanda`). **Rollback:** remove sync job.

### R-05 · MEDIUM — Add alert rules: backup-stale, verify-failed, cert-expiry, quorum-lost
- **Effort:** S (needs R-06 for PVE metrics). **Fix:** rules in `netframe-monitoring-stack` repo.
  **Rollback:** revert the rule commit.

### R-06 · MEDIUM — Deploy prometheus-pve-exporter
- **Effort:** S. **Blast radius:** low (read-only scrape). **Fix:** LXC or on CT103; PVE API
  token (read-only role); add scrape job. **Rollback:** remove exporter + scrape config.

### R-07 · MEDIUM — Audit NUT graceful-shutdown coverage
- **Effort:** S. **Fix:** confirm `upsmon` on every node with correct `SHUTDOWNCMD` + staged
  `HOSTSYNC`/timers for the dual-PSU cross-feed. **Rollback:** config-managed, revertible.

### R-08 · MEDIUM — Deploy Oxidized (network config → git nightly)
- **Effort:** M. **Fix:** LXC; add EX3400/OPNsense/UniFi; nightly pull. Also fixes the
  can't-scrape-EX3400 problem. **Rollback:** stop container.

### R-09 · MEDIUM — Reconcile EX3400 SSH access + pull config once
- **Effort:** XS. **Fix:** `ssh-keygen -R 192.168.10.50`, re-add key, pull `show config | display
  set`, diff vs repo. **Rollback:** n/a (client-side).

### R-10 · LOW — Mask failed `openipmi.service` on pve1 (no BMC)
- **Effort:** XS. **Fix:** `systemctl mask openipmi`. **Rollback:** `systemctl unmask`.

### R-11 · LOW/MEDIUM — Fleet patch + staged reboots
- **Effort:** M. **Fix:** rolling `apt upgrade` + reboot (respect kernel holds on QuarkyLab/Jarvis!),
  one node at a time keeping quorum. pve1 (133 pending) most behind. **Rollback:** kernel pin/boot
  previous. **Caution:** never upgrade kernel on QuarkyLab/Jarvis (holds enforce this).

### R-12 · LOW — Investigate duplicate homepage (pve1 CT104 still running)
- **Effort:** XS. **Fix:** confirm CT104 is the retired instance; stop/disable if so (docs say it
  was shut down 2026-06-24 but it's running). **Rollback:** start CT104.

## Documentation (→ Phase 4 PR, docs-only, branch)

| ID | Sev | Finding | Fix | Files |
|---|---|---|---|---|
| D-01 | HIGH | Grafana stack shown on pve3 | pve3 → **pve4** | README, topology .md, MOC |
| D-02 | HIGH | Headscale shown on pve3 | pve3 → **pve5** | README, topology .md, netframe-runbook.tex, ADR-0004 |
| D-03 | HIGH | Randy CPU v4/28c | → **v3 / 24c/48t** | docs/*, netframe-runbook.tex, update-logs |
| D-04 | HIGH | Randy "2 spare/unallocated" | → **4 in-pool** | docs/randy-commissioning |
| D-05 | HIGH | `bulk` 58.2T/2-vdev | → **80T / 3-vdev (8+8+6)** | topology .md, Proxmox Cluster.md |
| D-06 | HIGH | OPNsense 25.7 | → **25.1.12** (25.7 = target, keep in CARP plan only) | README, topology, MOC, Network Overview, Services&VMs, Proxmox Cluster, netframe-runbook.tex |
| D-07 | HIGH | Jarvis "RTX 8000" (pre-swap) | → **2× RTX 6000** | netframe_update_2026-06-22 |
| D-08 | MED-HIGH | "native-vlan-id not supported" | → **supported, interface-level** | homelab-setup, Network Procedures×3, Juniper EX3400 note |
| D-09 | MED | Homepage on pve1 LXC104 | → **pve3 LXC106** | homelab-setup:16 |
| D-10 | MED | EX3400-RCA / homelab-setup present-tense stale | add **"historical" banner** | EX3400-SSH-RCA, homelab-setup |
| D-11 | LOW | docs/ vs runbooks/ em-dash drift | note; long-term single-source | (structural) |
| D-12 | INFO | dotfiles CLAUDE.md homepage=104 | fix in **dotfiles repo** (out of scope) | — |

**PR rule:** one commit per finding class (D-01…D-09 separable), branch only, no merge, PR body
table of `file:line | old | new | evidence`. `.tex` edits change source; PDFs regenerate separately.
