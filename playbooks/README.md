# km-cluster Ansible

Baseline hardening (desired-state) and backup verification for the 7-node
km-cluster homelab. Built from `ansible-homelab-spec.md`.

> **Status:** `hardening` and `backup_verify` roles built; both lint clean at
> ansible-lint's `production` profile and have been dry-run/live-verified
> against real nodes. Outstanding before production use: create the PBS API
> token (below) and decide on scheduling.

## Layout

```
playbooks/
├── ansible.cfg
├── requirements.yml               # ansible.posix (sysctl)
├── inventory/hosts.yml            # static YAML inventory, grouped by role
├── group_vars/
│   ├── all/
│   │   ├── vars.yml               # non-secret (ansible_user via inventory)
│   │   ├── vault.yml              # (create + ansible-vault encrypt — NOT committed)
│   │   └── vault.yml.example      # template of expected vault_ keys
│   ├── proxmox_nodes.yml
│   ├── compute.yml
│   ├── storage.yml
│   └── monitoring_targets.yml
├── roles/
│   ├── hardening/                 # repo / ssh / sysctl / packages
│   └── backup_verify/             # pbs / zfs / scrutiny / ds4246 → JSON report
├── desired-state.yml              # playbook 1 — hardening
└── backup-verify.yml              # playbook 2 — backup verification
```

## Inventory groups

| Group | Hosts |
|---|---|
| `proxmox_nodes` | pve2, pve3, pve4, pve5, quarkylab, jarvis, randy |
| `compute` | quarkylab, jarvis |
| `storage` | randy |
| `monitoring_targets` | = `proxmox_nodes` (all 7) |

`pve1` (standalone Mac Mini / Pi-hole) and `sandbox` are **not** cluster
members and are excluded by design. Connection user is `root` on all 7 hosts
(set once as an `all`-group var).

## Playbook 1 — `desired-state.yml` (hardening)

Idempotent baseline hardening. Always preview first:

```bash
ansible-playbook desired-state.yml --check --diff              # all nodes
ansible-playbook desired-state.yml --limit pve3 --tags ssh --check --diff
```

Tags: `repo` (PVE no-subscription + disable enterprise), `ssh` (key-only,
`PermitRootLogin prohibit-password` via an `sshd_config.d` drop-in, validated),
`sysctl` (kernel/fs only — no networking knobs), `packages` (cache refresh;
baseline installs and upgrades are opt-in and default off, to protect the
pinned GPU-node kernels).

**pve2 is excluded** (`exclude_from_hardening: true`); it stays visible in the
group but no task runs against it, and nothing here ever touches OPNsense
config. Manual only.

## Playbook 2 — `backup-verify.yml` (storage/backup health)

Runs on `storage` (Randy), read-only except for writing one JSON report to
`/var/log/netframe-monitor/backup-report.json`. Four checks, each pass/fail:

| Check (tag) | Source | Notes |
|---|---|---|
| `pbs` | PBS REST API (`https://127.0.0.1:8007`) | newest snapshot per datastore within 25h; needs a vault token (below) |
| `zfs` | `zpool` on Randy | all pools ONLINE + `status -x` healthy; covers `datastore` **and** `bulk` |
| `scrutiny` | Scrutiny API (`.183:8080`) | asserts 0 failing drives (count is reported, not hardcoded — it's ~79 cluster-wide) |
| `ds4246` | `lsblk` on Randy | counts physical shelf disks (dedup by WWN — the shelf is dual-pathed) vs. expected 16 |

```bash
ansible-playbook backup-verify.yml --check          # preview
ansible-playbook backup-verify.yml                  # run + write report
ansible-playbook backup-verify.yml --tags zfs,ds4246   # subset
```

The report's `generated` timestamp doubles as `last_run` (a stale file = a
dead timer). The run also writes a node_exporter textfile metric on Randy
(`/var/lib/prometheus/node-exporter/backup_verify.prom`:
`backup_verify_report_generated_timestamp_seconds` + `backup_verify_overall_pass`).

**Consumers of the report:**
- **NetFRAME monitor** (`netframe_monitor.py` on Jarvis) reads it every 15 min as
  a `backup_verify` check → `last_run.json` + the LLM report / `health.kylemason.org`
  (WARN if stale >26h or any sub-check failed).
- **Grafana** (via the textfile metric) → Discord `discord-alerts`:
  `BackupVerifyReportStale` (`time()-generated > 26h` — dead cron) and
  `BackupVerifyFailing` (`overall_pass == 0` — a fresh run that failed a check).
  Rules live in `machismo0311/netframe-monitoring-stack`.

### PBS token (required for the `pbs` check)

Create a read-only token on Randy, then store it in the vault:

```bash
# on Randy:
proxmox-backup-manager user generate-token root@pam ansible-verify
proxmox-backup-manager acl update /datastore DatastoreAudit --auth-id 'root@pam!ansible-verify'
```

Put the returned id/secret in `group_vars/all/vault.yml` as `vault_pbs_token_id`
/ `vault_pbs_token_secret` (see `vault.yml.example`). Until then the `pbs`
check records `status: error` and the report's `overall` is `fail` by design.

## Scheduling

Runs daily from **Ares** (the control node) via a **user cron job**, mirroring
the `opnsense-config-backup` pattern (Ares has no passwordless sudo, and the
sibling backup automation already uses user cron, not a system unit).

`scheduling/run-backup-verify.sh` is the versioned wrapper (it adds the vault
password file only when it exists, and appends to a run log). The crontab entry
itself is Ares-local state — reproduce it with:

```cron
0 6 * * * /home/machismo/Home-Lab/playbooks/scheduling/run-backup-verify.sh >> /home/machismo/.config/netframe-backup-verify/run.log 2>&1
30 6 * * * /home/machismo/Home-Lab/playbooks/scheduling/run-hardening-drift-check.sh >> /home/machismo/.config/netframe-backup-verify/hardening-drift.log 2>&1
```

The 06:30 job is the **hardening drift check** (`run-hardening-drift-check.sh`):
it runs the hardening desired-state in **`--check` mode (read-only, never
enforces)** and writes a world-readable JSON report to Randy at
`/var/log/netframe-monitor/hardening-drift.json`. `netframe_monitor` ingests it
as a `hardening_drift` check (WARN if any node drifted from the hardened baseline,
or if the report goes stale = a dead cron). Enforcement stays a deliberate manual
`ansible-playbook desired-state.yml` (without `--check`). Note: the `Update APT
cache` task is `changed_when: false` so a clean fleet reports `changed=0`, making
real drift unambiguous.

06:00 is after the nightly backups (LXC 02:00 / VM 03:00) and the 03:17
opnsense backup, so the newest snapshot is well inside the 25h window. The
wrapper exits 0 when the *run* succeeds; the pass/fail verdict lives in the
report's `overall` field (and the `generated` freshness stamp), not the exit
code. Inspect with `tail ~/.config/netframe-backup-verify/run.log`.

> If you later want a systemd system timer instead (needs root on Ares), the
> equivalent is a `Type=oneshot` service with `User=machismo` calling the same
> wrapper, plus a daily `OnCalendar=*-*-* 06:00:00` `Persistent=true` timer.

## Secrets

Single `ansible-vault` file: `group_vars/all/vault.yml` (only the PBS token so
far). Vault password lives outside the repo (password manager):

```bash
ansible-playbook backup-verify.yml --vault-password-file ~/.ansible-vault-pass
```

## Conventions

- Every role is tagged; every run is previewable with `--check --diff`.
- Prefer real modules over `shell`/`command` (the one `shell` — DS4246 count —
  is annotated, as it needs a pipe).
- Roles apply to whatever group they're pointed at — no hardcoded host counts.

## Still open

1. ~~Scheduling~~ — **done:** daily 06:00 user cron on Ares (see Scheduling).
2. ~~Live-verify the `pbs` path~~ — **done:** token created (`root@pam!ansible-verify`,
   `DatastoreAudit`), vault encrypted; live run parses real snapshots and all
   four checks pass. `vault.yml` is gitignored.
3. ~~Ollama ingestion~~ — **done:** `netframe_monitor.py` reads the report as a
   `backup_verify` check (folds into `last_run.json` / LLM report / web page).
4. ~~Grafana alerting~~ — **done:** `BackupVerifyReportStale` + `BackupVerifyFailing`
   → Discord (see the metric note under Playbook 2).
5. **Hardening not yet applied** — `desired-state.yml` is built and `--check`-verified
   but has never run for real against any node. Apply per-node when ready.
6. **⚠️ Vault password backup** — the only copy is `~/.config/ansible/vault-pass`
   on Ares. Save it in Vaultwarden.
