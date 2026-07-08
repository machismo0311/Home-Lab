# PBS Backup Paths — VLAN 1 vs 10 G VLAN 30 (Randy dual-homed)

**Status:** 🟢 In production
**Date:** 2026-07-08
**Author:** Kyle Mason (NetFRAME homelab)
**Related:** [[Runbook/Jarvis-LLM-Platform-2026-07-05]] · [[Runbook/VLAN30-Migration-Report-2026-07-02]] · [[Infrastructure/Storage]] · [[Compute/Small Node Cluster]]

---

## 1. Summary

Randy (Proxmox Backup Server) is **dual-homed**: `192.168.10.187` on the management **VLAN 1** and `192.168.30.187` on the servers **VLAN 30** (10 GbE). The cluster's backup nodes are split across those VLANs, so **no single PBS address works well for everyone**:

- **VLAN-1-only nodes** (pve2–pve5) reach `.10.187` **directly on `vmbr0`** but can only reach `.30.187` through a broken inter-VLAN route (see §5) — bulk uploads there stall.
- **VLAN-30 nodes** (QuarkyLab, Jarvis, Randy) reach **`.30.187` directly on `vmbr0.30` at 10 Gb/s** — the fast path.

The solution is **two PBS storages pointing at the same datastore**, each restricted to the nodes that can use it, and backup jobs assigned accordingly.

---

## 2. Node → PBS reachability matrix

| Node | VLAN | Reaches `.10.187` (VLAN 1) | Reaches `.30.187` (VLAN 30) | Use storage |
|---|---|---|---|---|
| pve2–pve5 | 1 only | ✅ direct on `vmbr0` | ❌ routed via bogus gw `192.168.1.1` → bulk stalls | `randy-pbs` |
| QuarkyLab | 1 + 30 | ✅ (`.10.179`) | ✅ direct on `vmbr0.30` @10 G | `randy-pbs-10g` |
| Jarvis | 1 + 30 | ✅ (`.10.31`) | ✅ direct on `vmbr0.30` @10 G | `randy-pbs-10g` |
| Randy | is PBS | local | local | (backs up to itself) |

---

## 3. Storage configuration (`/etc/pve/storage.cfg`)

Two `pbs:` entries, **same `datastore` and `fingerprint`** (same PBS instance → chunks **dedup across both paths**), different `server` and `nodes`:

```
pbs: randy-pbs                     # VLAN 1 — all nodes (default)
	datastore datastore
	server 192.168.10.187
	content backup
	fingerprint da:61:6a:4c:49:e8:87:03:08:1d:d7:31:ab:23:58:20:47:58:e8:77:4a:52:3d:39:0c:19:52:e0:67:ee:d9:c9
	prune-backups keep-all=1
	username root@pam

pbs: randy-pbs-10g                 # VLAN 30 10 G — GPU/storage nodes only
	datastore datastore
	server 192.168.30.187
	content backup
	fingerprint da:61:6a:4c:49:e8:87:03:08:1d:d7:31:ab:23:58:20:47:58:e8:77:4a:52:3d:39:0c:19:52:e0:67:ee:d9:c9
	prune-backups keep-daily=7,keep-weekly=4
	username root@pam
	nodes QuarkyLab,Jarvis,Randy
```

Credential: `randy-pbs-10g` reuses the same PBS password —
`cp /etc/pve/priv/storage/randy-pbs.pw /etc/pve/priv/storage/randy-pbs-10g.pw`.

The `nodes` restriction is what keeps VLAN-1 nodes from ever selecting the unreachable `.30.187` path (the storage simply isn't offered to them).

---

## 4. Backup jobs (`/etc/pve/jobs.cfg`)

| Job | Guests | Node(s) | Storage | Path | Schedule |
|---|---|---|---|---|---|
| `4ed4c3e5…` | LXC 101,102,103,105,106,107 | pve3 | `randy-pbs` | VLAN 1 `.10.187` | 02:00 |
| `eb8ac4eb…` | VM 100 (OPNsense) | pve2 | `randy-pbs` | VLAN 1 `.10.187` | 03:00 |
| `fc7be16b…` | VM 104 (Wazuh) | QuarkyLab | **`randy-pbs-10g`** | **VLAN 30 10 G** | 03:00 |

Rule of thumb: **a guest on a VLAN-30 node → `randy-pbs-10g`; everything else → `randy-pbs`.**

---

## 5. Why `.30.187` fails from the pve nodes

`ip route get 192.168.30.187` on pve3 returns **`via 192.168.1.1 dev vmbr0`** — a bogus gateway (not the VLAN 30 gw `192.168.30.1`, which pve3 has no interface on). Small packets (ping, the TLS control handshake) traverse it, but the **bulk PBS data upload stalls at 0 B and the HTTP/2 connection resets after ~13 min** (`INFO: … uploaded 0 B` → `HTTP/2.0 connection failed` → `Error: connection reset`). This is the root cause of the **2026-07-02 → 07-06 backup outage** (the VLAN 30 migration had repointed the single PBS storage to `.30.187`). The dual-storage design above sidesteps it entirely: VLAN-1 nodes never touch `.30.187`.

> The stray `192.168.1.1` route on the pve nodes is worth cleaning up separately (a `192.168.1.0/24` artifact), but it is not required for backups to work.

---

## 6. Verification (2026-07-08)

- **QuarkyLab → `.30.187`:** `ip route get` = `dev vmbr0.30 src 192.168.30.179` (direct, no gateway); 1500-MTU DF ping OK; `:8007` open; link `Speed: 10000Mb/s`.
- **`randy-pbs-10g` active** on QuarkyLab (`pvesm status`).
- **VM 104 immediate backup** over the 10 G path: `Finished Backup of VM 104 (00:00:17)` — `Backup job finished successfully`; snapshot `vm/104/2026-07-08T12:25:07Z` landed (dedup incremental, 868 MiB changed data).
- **Nightly health:** LXC 101/102/103/105/106/107 have clean 07-07 & 07-08 snapshots (all `TASK OK`) on `randy-pbs`.

---

## 7. Operations

**Add a new VLAN-30-node guest to the 10 G path:** create/assign its backup job with `--storage randy-pbs-10g` (only valid on QuarkyLab/Jarvis/Randy):
```bash
pvesh create /cluster/backup --schedule "03:00" --storage randy-pbs-10g \
  --mode snapshot --vmid <ID> --compress zstd --mailnotification failure \
  --prune-backups keep-daily=7,keep-weekly=4 --comment "<name> over 10G VLAN30"
```

**Immediate 10 G backup** (run on the node hosting the guest):
```bash
vzdump <ID> --storage randy-pbs-10g --mode snapshot --compress zstd
```

**Verify a node's path:** `ip route get 192.168.30.187` should show `dev vmbr0.30` (direct) on VLAN-30 nodes; anything showing `via 192.168.1.1` must use `randy-pbs` instead.

---

## 8. Rollback

Both storages point at one datastore, so removing `randy-pbs-10g` loses nothing — snapshots remain accessible via `randy-pbs`:
```bash
# point VM 104 back to the VLAN-1 storage, then drop the 10G storage
pvesh set /cluster/backup/fc7be16b-2ad0-4651-87c0-f2fb399442c7 --storage randy-pbs
pvesm remove randy-pbs-10g
```
`storage.cfg` backups: `pve3:/root/storage.cfg.bak-*`.

---

## 9. Change log

- **2026-07-06** — PBS storage repointed `.30.187` → `.10.187` to end the cluster-wide backup outage (see [[Runbook/Jarvis-LLM-Platform-2026-07-05]] §9).
- **2026-07-08** — added `randy-pbs-10g` (`.30.187`, nodes QuarkyLab/Jarvis/Randy) and split VM 104 onto it for 10 G backups; verified.
