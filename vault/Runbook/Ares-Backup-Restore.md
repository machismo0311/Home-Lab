# Ares Backup and Restore

**Tags:** #runbook #backup #disaster-recovery #ops
**Created:** 2026-07-13

How Ares (the admin workstation) is backed up to Randy, and how to restore it if Ares dies. Reusable runbook, not a one-time report.
Related: [[Runbook/Production-Readiness-Checklist-2026-07-10]] · [[Infrastructure/Services & VMs]] · [[00 - Homelab MOC]]

---

## What the backup is

| Item | Value |
|---|---|
| Tool | `restic` (static binary in `~/.local/bin/restic` on Ares, no sudo needed) |
| Source | `/home/machismo` (whole home dir), excluding caches/venvs/node_modules/pycache/snap/nvm/trash |
| Repository | `sftp:randy:/mnt/bulk/backups/ares` (encrypted) on Randy's `bulk` ZFS pool |
| Target host | Randy `192.168.10.187` (VLAN 1), reachable from BOTH Ares NICs (wired + wifi, same subnet), so the backup runs on whichever link is up |
| Schedule | systemd user timer `ares-backup.timer`, daily `04:00` local, `Persistent=true` (catches missed runs) |
| Script | `~/.local/bin/ares-backup.sh` |
| Retention | 7 daily, 4 weekly, 6 monthly (auto-pruned) |
| Log | `~/.local/state/ares-backup.log` |
| Freshness metric | writes `ares_backup_last_success_timestamp_seconds` to Randy's node_exporter textfile dir; Grafana rule **AresBackupStale** fires to Discord if no success in >26h |

## The encryption password (READ THIS FIRST)

The repo is encrypted. Without the password the backup is **unrecoverable**.

- On a healthy Ares it lives at `~/.config/restic/ares-randy.pass` (mode 600).
- **It MUST also live in Vaultwarden**, because if Ares is dead that on-disk copy is gone with it. Storing it in Vaultwarden is a pinned when-home task; confirm it is there. Vaultwarden runs on a different box (pve3 LXC 102), so it survives an Ares failure.

## Everyday checks

```bash
export XDG_RUNTIME_DIR=/run/user/$(id -u)
systemctl --user list-timers ares-backup.timer      # next run
tail -n 20 ~/.local/state/ares-backup.log           # last run result
export RESTIC_REPOSITORY="sftp:randy:/mnt/bulk/backups/ares"
export RESTIC_PASSWORD_FILE=~/.config/restic/ares-randy.pass
restic snapshots                                     # list backups
```
A firing **AresBackupStale** alert in Discord means no successful backup in >26h. Check the log; usually Randy was unreachable or the timer did not fire.

## Restore procedure (Ares dead or rebuilt)

On the replacement / rebuilt Ares (Debian):

1. **Get restic.** Download the static binary to `~/.local/bin/restic` (same as the original install), or `apt install restic` if you have sudo.
2. **Ensure SSH to Randy works** as root (key in `~/.ssh/config` Host `randy` -> `192.168.10.187`). On a fresh machine you will need to restore or recreate that key and have Randy trust it. If you only have the password and no SSH key yet, add the new host key to Randy's `authorized_keys` first.
3. **Set the repo and password** (password from **Vaultwarden**):
   ```bash
   export RESTIC_REPOSITORY="sftp:randy:/mnt/bulk/backups/ares"
   export RESTIC_PASSWORD='<paste from Vaultwarden>'
   restic snapshots            # confirm you can read the repo
   ```
4. **Restore** the latest snapshot:
   ```bash
   restic restore latest --target /home/machismo        # or a scratch dir first to inspect
   ```
   To restore a subset, add `--include /home/machismo/Home-Lab` etc.
5. **Repopulate excluded content.** Upstream git submodules (`claude-desktop-debian`, `pacextractor`, `spreadtrum_flash`, `CVE-...`) and caches/venvs were excluded to save space. From the restored dotfiles repo: `git submodule update --init --recursive`, and rebuild venvs from their `requirements.txt` as needed.
6. **Re-verify** the working tree: `git -C /home/machismo status`, check `.ssh/` perms (600 on keys), and confirm CLAUDE.md files are present (they are backed up but gitignored, so they restore as plain files).

## Rollback / point-in-time

`restic snapshots` lists all retained snapshots by ID and date. Restore a specific one with `restic restore <snapshot-id> --target <dir>`. Mount without restoring: `restic mount ~/mnt` (browse, then copy out).
