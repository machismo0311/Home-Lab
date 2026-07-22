# ARES DISASTER RECOVERY — CONTEXT

> Persistent record of how the old Ares died and how it was recovered.
> **Part 1** below is reconstructed from claude.ai web chats (2026-07-17 →
> 2026-07-20), saved verbatim. **Part 1B** (appended after) is reconstructed
> from local machine history on the new Ares and is ground truth where it
> contradicts Part 1.

================================================================================
PART 1 — WHAT HAPPENED (compiled from claude.ai chats)
================================================================================

## Environment (keep the runbook accurate to these)
- Old Ares: ~8-yr-old laptop, admin/jump box for km-cluster. 32GB RAM,
  aftermarket 1TB Samsung 970 EVO Plus NVMe added later.
- Backup target: Randy — SuperMicro, 192.168.10.187, runs Proxmox + PBS.
- CRITICAL: Ares was NOT in PBS. It was backed up with **restic** to a plain
  directory on Randy: `/mnt/bulk/backups/ares`. This mismatch cost real time
  (Lesson 6).
- restic repo passphrase lived only in Vaultwarden (pve3, LXC 102). On the old
  drive it also existed as `~/.config/restic/ares-randy.pass`.
- New Ares: Dell Latitude 3580, service tag 5HWCNJ2, SATA-only internally.

## Phase 0 — Death
- Died with zero warning mid-Claude-Code-session: no LEDs, no fan, no response to
  battery pull / hard reset / alternate PSU. Motherboard-level power-delivery
  failure, not economically repairable at 8 yrs.
- Data was safe (restic repo on Randy). Cluster kept running — Ares was only the
  admin box, not a cluster member.

## Phase 1 — Replacement hardware
- Evaluated used ThinkPads (T14 Gen 2 rejected for soldered RAM;
  T480/T480s/T580 considered). A T580 was bid on, but a Dell Latitude 3580 was
  actually put into service as a stopgap.
- Decision: reuse hostname `ares` on the new box — specifically to avoid editing
  Ansible inventory, Pi-hole DNS, DHCP MAC reservations, Headscale node entries,
  and every script that hardcodes the name.
- On any machine that had SSH'd to old Ares, clear the stale host key:
  `ssh-keygen -R ares` (and `-R <old-ip>`).

## Phase 2 — The NVMe salvage trap
- Pulled the 1TB 970 EVO Plus from dead Ares intending to reuse it.
- The 3580 has NO M.2 NVMe slot — 2.5" SATA bay + WLAN/WWAN only. The RWMDF
  caddy carries M.2 **SATA** only, not NVMe/PCIe. The salvaged NVMe CANNOT be
  used internally. A WD Black 2.5" SATA HDD went in the bay instead.
- To even READ the old NVMe (holds the restic passphrase, SSH keys, and Ansible
  vault key directly), a USB 3.2 NVMe enclosure is required (ORICO/UGREEN,
  M-key/NVMe, ~$15-20). That drive is the fallback source of truth and would
  have made the entire Vaultwarden detour unnecessary (Lesson 2).

## Phase 3 — Debian install (Windows wipe)
- Target: Debian 13 Trixie + KDE Plasma 6 (better 7th-gen Intel firmware than
  Debian 12).
- Installer MUST be the full **DVD-1 ISO**, not netinst: the Intel Wireless-AC
  card needs non-free firmware and netinst assumes a working network to fetch it.
  DVD carries firmware + full KDE set offline.
- Flash with **Rufus in DD mode** (NOT ISO mode — ISO mode corrupts Debian's
  hybrid-ISO boot sector). GPT / UEFI target.
- Software selection: UNCHECK GNOME, CHECK KDE Plasma (Debian defaults to GNOME,
  easy to blow past). Hostname `ares`.
- ISSUE — GRUB installed but wouldn't boot: no `debian` entry in the firmware
  boot menu. GRUB's EFI files were present on the ESP (`\EFI\debian\`) but the
  NVRAM boot variable didn't stick (cleared when the USB was pulled and firmware
  reshuffled boot order).
- ISSUE — Secure Boot: Dell firmware can silently re-enable Secure Boot after
  changes; shim then refuses to load. Had to re-confirm Secure Boot OFF
  (F2 -> Boot Configuration).
- FIX (what worked): added the boot entry manually in firmware ->
  `\EFI\debian\shimx64.efi` (fallback `grubx64.efi`), named it `debian`, moved it
  to top of boot order.
- FIX (alternative, rescue mode on the same USB -> Advanced -> Rescue):
```
  grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=debian --recheck
  update-grub
  efibootmgr -v
```
  Stale Windows entries removable with `efibootmgr -b <NNNN> -B`.

## Phase 4 — Getting the restic passphrase out of Vaultwarden
Biggest time sink, and entirely avoidable (Lesson 2).
- The passphrase was only in Vaultwarden. Vaultwarden requires HTTPS and couldn't
  be hit directly from the fresh laptop.
- Reached it via an SSH local-forward tunnel to 8080, verified with:
  `ss -tlnp | grep -E '8080|8443'`
- ISSUE — nginx wasn't installed on the new machine. Had to build a TLS proxy
  from scratch:
```
  sudo apt install -y nginx openssl
  sudo openssl req -x509 -newkey rsa:2048 -nodes -days 30 \
    -keyout /etc/ssl/private/vw.key -out /etc/ssl/certs/vw.crt -subj "/CN=localhost"
```
  Then an nginx server block on `8443 ssl` -> `127.0.0.1:8080`, `nginx -t`,
  restart, open `https://localhost:8443` in Firefox, accept the self-signed cert,
  log in, copy the entry `Ares restic backup -> Randy (repo password)`.

## Phase 5 — The restic restore
- Planning initially assumed PBS + `proxmox-backup-client` +
  `host/ares/<timestamp>` `.pxar`. Wrong — it was a restic repo (Lesson 6).
- ISSUE — repo path assumed wrong TWICE. A `find` searched only `/datastore`; the
  repo was at `/mnt/bulk/backups/ares` (with `jarvis-netframe` alongside). ZFS
  pools should have been enumerated first.
- ISSUE — permissions: `/mnt/bulk/backups/ares` is root-owned, mode 700. restic
  could NOT read it as the SFTP user. Resolution — run restic AS ROOT directly on
  Randy over SSH, not over SFTP from the laptop:
```
  ssh root@192.168.10.187
  restic -r /mnt/bulk/backups/ares snapshots
  restic -r /mnt/bulk/backups/ares restore latest --target /mnt/bulk/restore-ares
```
  Then rsync `/mnt/bulk/restore-ares` -> new Ares. Staging on Randy first (not
  straight across the network into live `/home`) means the result can be
  inspected before overwriting anything, and a network drop doesn't kill the
  restore.
- ISSUE — staleness: repo mtime was Jul 13 and a Grafana staleness alert had
  already fired; the laptop died later. The newest snapshot predated the failure
  by days — the last few days of changes were not captured.
- Laptop side: restore into a scratch dir (`~/restore`), NEVER straight onto live
  `/home` (KDE had dotfiles open; overwriting live is unpredictable). Then
  selectively copy dotfiles / SSH keys / the Home-Lab repo out of staging.

## Phase 6 — Claude Code + account
- Installed Claude Code via the official curl installer (v2.1.215).
- ISSUE — `claude: command not found`: `~/.local/bin` wasn't on PATH. The export
  was only in `~/.profile` (login shells) and missing from `~/.bashrc`
  (interactive non-login — the normal desktop-terminal case). Fixed by appending
  to `.bashrc` with printf (not echo, to avoid newline edge cases) and sourcing.
- ISSUE (UNRESOLVED) — Claude login: the new laptop landed in an empty account
  with a payment prompt despite an active subscription. Likely a duplicate
  account from a different auth method. The account ID can't be used as a CLI
  credential. Open with Anthropic support (support.claude.com) — the runbook
  can't fix this, only flag it.

## LESSONS LEARNED (the whole point of the runbook)
1. Hostname reuse was correct — kept Ansible/DNS/DHCP/Headscale/scripts
   untouched. Keep doing it.
2. Biggest avoidable cost: the restic passphrase was reachable only through
   Vaultwarden, which needed a tunnel + a from-scratch nginx TLS proxy on a
   machine with nothing installed. An offline copy of the passphrase (+ SSH keys
   + Ansible vault key) — on the salvaged NVMe via enclosure, in a phone password
   manager, or on paper in a safe — collapses Phase 4 to nothing.
3. Check drive interface (NVMe vs SATA, M.2 slot presence) BEFORE buying or
   planning to reuse a drive. The NVMe salvage was dead on arrival for the 3580.
4. Keep a USB NVMe enclosure in the kit permanently — fastest path to the old
   secrets and the ultimate fallback source of truth.
5. Always DVD ISO + Rufus DD for offline-firmware laptops, and expect the Dell
   UEFI NVRAM / Secure-Boot boot-entry dance. Bake it into the runbook so it
   isn't rediscovered under pressure.
6. Document the ACTUAL backup mechanism + exact path: restic at
   `sftp:randy:/mnt/bulk/backups/ares` (root-owned 700 -> run restic AS ROOT on
   Randy), NOT PBS. Enumerate ZFS pools before hunting for a repo.
7. Backup freshness must be monitored and trusted. The snapshot was days stale at
   death; the alert fired but recovery still assumed a current backup. Verify
   snapshot age FIRST, every time.
8. Restore to staging, inspect, then rsync — never straight onto a live /home.


================================================================================
PART 1B — RECONSTRUCTED FROM LOCAL HISTORY (2026-07-20)
================================================================================

Reconstructed on the new Ares from local machine history. Where this section
contradicts Part 1, **Part 1B is ground truth** (Part 1 was hand-transcribed from
claude.ai chats; this is from the machine's own logs). Additive only — Part 1 is
left intact above.

**Sources mined (read-only):**
- `~/.bash_history` — line numbers cited as `bh:NNNN`. NOTE: this file is a MIX of
  *restored old-Ares* history (low line numbers, e.g. the June EX3400 RCA
  `ssh-keygen -R 192.168.10.2` lines) and *new-Ares recovery* history (roughly
  `bh:1863+`). Only the high-numbered block is the actual rebuild session.
- Claude Code transcripts `~/.claude/projects/-home-machismo/*.jsonl`.
- `~/Home-Lab` git log (commits cited by hash).
- Live filesystem state: `~/restore`, `~/.config/restic/`, `~/.ssh/`, `lsblk`.

--------------------------------------------------------------------------------
## CONTRADICTIONS with Part 1 (ground truth wins)
--------------------------------------------------------------------------------

### C1 — The restore was run FROM the laptop over SFTP-as-root, straight to `~/restore`. There was no Randy-side `/mnt/bulk/restore-ares` staging dir and no rsync step.
Part 1 Phase 5 says: "run restic AS ROOT directly on Randy over SSH, not over SFTP
from the laptop … then rsync `/mnt/bulk/restore-ares` -> new Ares." The machine
history shows otherwise. The working sequence (`bh:1961-1967`):
```
export RESTIC_REPOSITORY="sftp:randy:/mnt/bulk/backups/ares"
export RESTIC_PASSWORD='<redacted>'
restic snapshots
restic restore latest --target ~/restore
```
The "as root" requirement was satisfied *without* logging into Randy: the `randy`
SSH alias resolves to **`root@192.168.10.187`** (`~/.ssh/config`), so
`sftp:randy:` is already an SFTP session as root and can read the root-owned,
mode-700 repo dir. Earlier failed/abandoned attempts before landing on this form:
`restic -r /mnt/bulk/backups/ares snapshots` (`bh:1925` — bare local path, only
works when run *on* Randy) and `restic -r sftp:root@192.168.10.187:/mnt/bulk/backups/ares snapshots`
(`bh:1927`). restic itself was not installed on the fresh laptop — `sudo apt
install -y restic` (`bh:1926, bh:1959`).
- **Confirmation on disk:** `~/restore/home/machismo/` holds the full old home
  (Home-Lab, Vaults, dotfiles, `.ssh`, the netframe-* repos, etc.), with old
  mtimes preserved — i.e. it is a restic restore target on the laptop, not a
  Randy export.
- The restic excludes file (`~/.config/restic/excludes.txt`, updated 2026-07-19)
  now excludes `/home/machismo/restore` and describes it as "the staged rsync
  copy of the OLD home pulled from Randy during recovery … already captured in
  snapshots 42af7c8f..245709de." That "rsync" wording is loose — `bh:1967` shows
  it was produced by `restic restore --target ~/restore`, not rsync. Same intent
  (stage, inspect, then selectively reinstate), different mechanism.

### C2 — Last good snapshot was 2026-07-17 04:03 (~2.5 days stale at recovery), NOT "Jul 13 / days stale," and nothing was corrupt.
Part 1 Phase 5 / Lesson 7 say the repo mtime was Jul 13 and "the newest snapshot
predated the failure by days." A transcript walks this back explicitly: the live
repo held **5 snapshots**, newest **2026-07-17 04:03 at 110.212 GiB**, and it
**passed `restic check`**. As of 2026-07-19 that is ~2.5 days stale. The "Jul 13"
figure matches the mtime of `~/.config/restic/ares-randy.pass` (41 bytes, Jul 13
11:48), not the newest snapshot.
- An *intermediate* wrong claim during recovery — that the last good backup was
  07-16 and a snapshot was truncated — was self-corrected: it came from reading
  the backup log *inside the restored copy* (which had been captured mid-run, so
  it ended at "backup starting" with no completion line). The live repo, checked
  after, showed the real picture.
- **Why backups had stopped:** the rebuild wiped the tooling — no `restic`
  binary, no `ares-backup.sh`, no `~/.config/restic/`, and zero user timers on
  the fresh install. Backups stopped because the tooling left with the old OS,
  not because a run failed. `AresBackupStale` (>26h) was a true positive. A stale
  restic lock was also found and cleared.
- Caveat noted at the time: `restic check` without `--read-data` verifies
  structure/metadata, not pack contents; a full `--read-data` would pull all
  ~110 GiB back over SFTP. ZFS checksums on `bulk` cover bit-rot underneath.

--------------------------------------------------------------------------------
## ADDITIONS (detail not in Part 1)
--------------------------------------------------------------------------------

### A1 — Vaultwarden passphrase retrieval: TWO paths were exercised, plus remediation.
- **nginx TLS-proxy path** (as Part 1 Phase 4): `sudo apt install -y nginx
  openssl` (`bh:1954`), edit `/etc/nginx/sites-available/vw` (`bh:1956`), symlink
  into `sites-enabled` (`bh:1957`), `sudo nginx -t` + restart (`bh:1952, bh:1958`).
- **Direct cluster-side secret pull** (bypasses the browser entirely): secrets
  were also read straight out of the containers over SSH —
  `ssh root@192.168.10.201 "pct exec 102 -- grep ADMIN_TOKEN /etc/vaultwarden.env"`
  (`bh:1929`; pve3 = `.201`, Vaultwarden = LXC 102) and an NPM/LetsEncrypt token
  via `pct exec 101 -- docker exec … grep …` (`bh:1873`). On a live cluster,
  `pct exec` / `docker exec` grep of a container's env is a faster path to a
  service secret than standing up a TLS proxy.
- **Remediation acted on during recovery (Lesson 2):** scratchpad scripts were
  run to check for and *add* the restic passphrase to Vaultwarden —
  `check-restic-in-vault.sh` (`bh:1863`) and `add-restic-to-vault.sh` (`bh:1865`).

### A2 — SECURITY EXPOSURE created during recovery (needs cleanup).
The live restic repo passphrase was passed on the command line as
`export RESTIC_PASSWORD='…'` (`bh:1965`) and is therefore sitting in **plaintext
in `~/.bash_history`**. It also exists on disk at `~/.config/restic/ares-randy.pass`
(restored). Action: scrub that line from shell history (and prefer
`RESTIC_PASSWORD_FILE=~/.config/restic/ares-randy.pass`, which the healthy backup
script already uses, over inlining the secret). The value is deliberately NOT
reproduced in any recovery doc.

### A3 — PATH / Claude Code fix: echo was tried first, then printf.
Part 1 Phase 6 says the fix used printf "not echo." History shows both, in order:
first `echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source
~/.bashrc` (`bh:1902`); then a diagnosis `grep -n 'local/bin' ~/.bashrc
~/.profile` (`bh:1976`); then the definitive `printf '\nexport
PATH="$HOME/.local/bin:$PATH"\n' >> ~/.bashrc` (`bh:1978`) and
`source ~/.bashrc && which claude && claude --version` (`bh:1980`). printf is the
form to keep; echo was the first pass.

### A4 — SSH keys on the rebuilt Ares.
A fresh key was generated during bring-up: `ssh-keygen -t ed25519 -C
"machismo@ares"` (`bh:1908`). Restored keys are also present:
`~/.ssh/{id_ed25519, id_ed25519.pub, id_ed25519_github, id_ed25519_github.pub}`,
plus `~/.ssh/config` with the `randy` -> `root@192.168.10.187` alias that made the
SFTP-as-root restore work (see C1).

### A5 — An authoritative pre-existing runbook already documents the restic mechanism.
`vault/Runbook/Ares-Backup-Restore.md` (committed 2026-07-13, `83c134b`, i.e.
BEFORE the death) already carries the correct repo path, the `randy`=root alias,
the "restore to a scratch dir first" guidance, and Vaultwarden-as-password-store.
Post-rebuild reconciliation landed in `6e716f0` ("version the Ares crontab, fix
DS4246 expectation, correct README storage drift"). The new
`runbooks/laptop-recovery.md` should reference `Ares-Backup-Restore.md`, not
duplicate it.

--------------------------------------------------------------------------------
## GAP — dying-session transcripts remain INACCESSIBLE
--------------------------------------------------------------------------------
The Claude Code session that was live when the old Ares died went down with the
old machine; those transcripts, if they exist anywhere, are on the salvaged
Samsung 970 EVO Plus NVMe. That drive is **not currently attached**: `lsblk`
shows a single SATA disk (`sda`, 465.8G — the WD Black 2.5" bay drive) and there
is no `/dev/nvme*` node. No USB NVMe enclosure is connected (transcripts
corroborate "no enclosure"). Until the 970 EVO is mounted via a USB M-key/NVMe
enclosure, its `~/.bash_history` and `~/.claude/` cannot be mined — this gap is
unfilled.
