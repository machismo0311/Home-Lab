# 📄 Off-site Backup Plan — restic → Backblaze B2 (`bulk/fernanda`)

**Tags:** #plan #backup #offsite #restic #b2 #randy #dr
**Related:** [[Runbook/DS4246-Pool-Buildout-Plan-2026-07-07]] · [[Infrastructure/Storage]] · [[00 - Homelab MOC]]

| | |
|---|---|
| **Goal** | The **off-site** tier for `bulk/fernanda` (survives site loss: fire/theft/flood) |
| **Why** | Existing protection = RAIDZ2 + sanoid snapshots + syncoid off-box to QuarkyLab — all **same rack**. This adds the 3rd leg of 3-2-1. |
| **Choice** | **restic → Backblaze B2** (encrypted, dedup, incremental) |
| **Status** | PLAN — not executed. Needs a B2 account + key (user action) first. |

## Pricing verified 2026-07-08 (why B2)
| Option | Storage | Notes |
|---|---|---|
| AWS Glacier Deep Archive | ~$1.01/TB/mo | cheapest but **restic can't operate on it**, 12–48 h restores + retrieval fees, 180-day min → wrong tool |
| **Backblaze B2** ✅ | **$6.95/TB/mo** | free egress ≤3× stored/mo (free via Cloudflare), no min duration, restic-native |
| Wasabi | $7.99/TB/mo | no egress fee but **1 TB min billing** + 90-day min |
| rsync.net (zfs-send) | $60/mo min (4 TB) | keeps syncoid workflow but wasteful for small data |

At current size (`bulk/fernanda` ~empty) this is **pennies/month**; ~$0.70/mo per 100 GB.

## Prerequisites (operator, one-time)
1. Create a Backblaze account → **B2 bucket** (e.g. `netframe-offsite`, private).
2. Create an **Application Key** scoped to that bucket → note `keyID` + `applicationKey`.
3. Pick a **strong restic repo passphrase** and store it in **Vaultwarden** (LXC 102). ⚠️ *Lose this passphrase = backups unrecoverable. No recovery.*

## Setup (on Randy — has the data locally)
```bash
apt-get install -y restic

# secrets file, root-only
cat > /root/.restic-b2.env <<EOF
export B2_ACCOUNT_ID=<keyID>
export B2_ACCOUNT_KEY=<applicationKey>
export RESTIC_REPOSITORY=b2:netframe-offsite:randy/fernanda
export RESTIC_PASSWORD_FILE=/root/.restic-pw
EOF
chmod 600 /root/.restic-b2.env
printf '%s' '<strong-passphrase-also-in-Vaultwarden>' > /root/.restic-pw && chmod 600 /root/.restic-pw

set -a; . /root/.restic-b2.env; set +a
restic init                                   # one-time repo creation
```

**First + recurring backup** (snapshot-consistent: back up the newest sanoid snapshot, not the live dir):
```bash
# make snapshot dirs visible so restic can read a consistent point-in-time
zfs set snapdir=visible bulk/fernanda
snap=$(zfs list -t snapshot -o name -s creation -H -r bulk/fernanda | tail -1 | cut -d@ -f2)
restic backup "/mnt/bulk/fernanda/.zfs/snapshot/$snap" --tag fernanda --host randy
restic forget --tag fernanda --keep-daily 14 --keep-weekly 8 --keep-monthly 12 --prune
```

**Schedule** — systemd `restic-fernanda.timer` daily (offset from the 6-h syncoid + 03:00 backups), e.g. `OnCalendar=*-*-* 05:30`, `Persistent=true`. Service sources `/root/.restic-b2.env` then runs the backup+forget above.

## Verify / restore
```bash
restic snapshots                              # list backups
restic check                                  # repo integrity (run weekly)
restic restore latest --target /mnt/restore --include ...   # DR restore
```

## Monitoring
- Wrap the systemd service so a non-zero exit alerts (ZED-style mail to root, or the NetFRAME monitor).
- `restic check` weekly (own timer) to catch B2-side corruption early.

## Notes
- **restic runs on Randy** (data is local → no NFS pull). Could alternatively run on Ares.
- **Encryption is client-side** — B2 only ever sees ciphertext.
- After this, `bulk/fernanda` = 3-2-1 complete: (1) live RAIDZ2, (2) off-box syncoid→QuarkyLab, (3) off-site restic→B2.
- Only `bulk/fernanda` in scope; media/archive are re-acquirable. Add tags/paths if that changes.

## Sources (pricing, fetched 2026-07-08)
- Backblaze B2: https://www.backblaze.com/cloud-storage/pricing
- AWS Glacier Deep Archive: https://www.usage.ai/blogs/aws/storage-cost/glacier-deep-archive-pricing/ · https://aws.amazon.com/s3/pricing/
- Wasabi: https://wasabi.com/cloud-storage-pricing
- rsync.net: https://www.rsync.net/pricing.html
