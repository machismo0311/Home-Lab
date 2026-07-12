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
dead timer). **Report wiring:** the report is standalone for now.
`netframe_monitor.py` is a self-contained collector that writes its own
`last_run.json`; it does not read an external report, so auto-ingestion into
the Ollama summarizer is a deliberate follow-up (a small collector tweak),
not part of this role.

### PBS token (required for the `pbs` check)

Create a read-only token on Randy, then store it in the vault:

```bash
# on Randy:
proxmox-backup-manager user generate-token root@pam ansible-verify
proxmox-backup-manager acl update /datastore Audit --auth-id 'root@pam!ansible-verify'
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
```

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
2. **Live-verify the `pbs` path** — once the token exists, confirm the API
   JSON parsing (per-datastore `backup-time`) against real data. `zfs`,
   `scrutiny`, and `ds4246` are already live-verified against Randy.
3. **Ollama ingestion** — optional follow-up to merge the report into
   `last_run.json` so the existing summarizer picks it up.
