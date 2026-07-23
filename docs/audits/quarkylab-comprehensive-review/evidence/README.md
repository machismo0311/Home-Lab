# Evidence locations and collection methods

This directory deliberately holds **no raw evidence dumps**. Raw logs, full
configuration exports, and secret-bearing captures are not copied here. Instead this
file records **where** each class of evidence lives and **how** it was collected, so
the review is reproducible without redistributing sensitive material. The structured
distillation of the evidence lives in `../data/*.csv` and the section text.

## Collection posture

All collection was **read-only and low-risk**. Commands were classified before running;
nothing in the config-changing, service-affecting, destructive, or external-target
categories was executed. See `../appendices/command-log.tex` for the chronological log.

## Live evidence (2026-07-23, ~09:22-09:30 EDT)

Collected by the reviewer from Ares over SSH using existing key-based access. Not stored
here; reproduce with the commands in the command-log appendix. Highlights:

| Evidence | Host | Command (read-only) |
|---|---|---|
| Cluster quorum + corosync ring | pve3 | `pvecm status`, `corosync-cfgtool -s` |
| GPU assignment + ZFS + SLURM | quarkylab | `nvidia-smi`, `zpool list/status`, `sinfo` |
| GPU + ZFS + AI services | jarvis | `nvidia-smi`, `zpool list`, `systemctl is-active` |
| ZFS incl. degraded bulk pool | randy | `zpool status bulk/datastore`, `proxmox-backup-manager datastore list` |
| Standalone node + pending updates | pve1 (192.168.10.193) | `pveversion`, `pct list`, `apt list --upgradable` |
| Cluster-wide guests + storage + HA | pve3 | `pvesh get /cluster/resources`, `cat /etc/pve/storage.cfg`, `ha-manager status` |
| Live UPS load | pve3 (NUT) | `upsc tripplite`, `upsc midatlantic` |
| Backup freshness | randy | `ls -dt /datastore/{ct,vm,host}/*/2026-07-23*` |

Access that failed (recorded as limitations): `ssh ex3400` (key auth broken, finding
R-09); OPNsense was not queried (no API credentials used, VM untouched by design).

## Repository evidence (on disk, not copied here)

| Source | Path | Nature |
|---|---|---|
| Prior audit (findings, live captures, fact ledger) | `../../../audit/` | generated + live-captured 2026-07-22 |
| Canonical cluster context | `../../../CLAUDE.md` | operator-maintained (most-accurate doc) |
| Public reference docs | `../../../README.md`, `../../../topology/`, `../../../vault/` | manual (some drift) |
| Automation | `../../../playbooks/`, `../../../ansible/` | ansible roles + systemd scheduling |
| Monitoring config-as-code | `~/netframe-monitoring-stack/` | Grafana rules, exporters |
| AI-ops system | `~/netframe-monitor/` | Python source (read statically) |
| Prior assessments | `~/netframe-enterprise-assessment/`, `~/netframe-security-assessment/`, `~/netframe-reliability-assessment/` | generated reports |

## Secrets handling

The security review reports candidate secrets by **type, path, and a redacted
indicator only** (see `../sections/security-review.tex`). No secret value is reproduced
in any deliverable, CSV, or diagram. Discovered credentials were never used.

## Reliability tiers (used in `../data/evidence-register.csv`)

- **live** - observed directly this session; authoritative for point-in-time state.
- **live-captured** - captured live in the 2026-07-22 audit; re-verified where re-run.
- **generated** - produced by a tool or prior assessment; corroborated where possible.
- **manual** - operator-authored documentation; treated as a claim to verify.
- **inferred** - derived by reading source/config, not a runtime trace.
