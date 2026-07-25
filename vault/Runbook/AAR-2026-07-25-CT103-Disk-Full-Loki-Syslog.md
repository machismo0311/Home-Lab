# AAR 2026-07-25 — CT103 monitoring disk-full → Loki ingestion halt → NetworkSyslogSilent

## Summary
The Grafana `NetworkSyslogSilent` dead-man alert fired to `#monitoring` (Discord). Root cause was **not** the OPNsense/EX3400 syslog source — it was the **CT103 monitoring container's rootfs filling to 97%** (20 GB disk). With no room to write its WAL/chunks, **Loki's ingester rejected all promtail pushes** (`POST /loki/api/v1/push (500) "Ingester is shutting down"`), so `{job="network-syslog"}` went silent in Loki and the 15-min dead-man query returned no data (earlier it also timed out → the `context deadline exceeded` in the alert). No data was lost.

## Impact
- Network syslog (OPNsense + EX3400) not ingested into Loki for the duration; log-based alerting/queries blind for that window.
- Prometheus/Grafana metrics unaffected (separate TSDB).
- No production service impact outside the monitoring stack.

## Root cause
- CT103 rootfs (20 GB) at **97% used**. The hog was **`/var/lib/containerd` = 12 GB** — Docker runs in **containerd-image-store mode** (namespace `moby`), so image layers live under `/var/lib/containerd`, not `/var/lib/docker` (which read only 466 MB and misled the first `du` passes). The 12 GB was **orphaned image layers** (`texlive/texlive`, `alpine`, + their overlay snapshots) accumulated from repeated stack rebuilds.
- **Contributing blind spot:** the monitoring container's own rootfs was **never a Prometheus scrape target**, so the existing `DiskAlmostFull` rule could not warn before Loki starved.

## Timeline (2026-07-24 → 07-25)
1. `NetworkSyslogSilent` fires (Discord). Investigation shows Loki `/ready` = ingester not ready; disk 97%.
2. Grew **CT103 rootfs 20 → 40 GB** (`pct resize 103 rootfs +20G`, online, non-destructive; pve4 pool had ~794 GB free).
3. Restarted Loki → ingester recovered → **ingestion resumed (`network-syslog` = 1643 lines/15m, normal ~1600)**.
4. Root-caused the space to `/var/lib/containerd`; ran `docker image prune -a -f` → **reclaimed ~8 GB** (disk 18 → 9.8 GB used, ~27–32%). All 8 containers stayed up.
5. Added **CT103 as a Prometheus target** (`192.168.10.183:9100` → instance `netframe-monitor`) so `DiskAlmostFull` / `InstanceDown` / `LowMemory` now cover the monitoring host. Committed to `netframe-monitoring-stack`.
6. Reconciled **`gpu` + `snmp-ex3400`** scrape jobs (live-only drift) into the repo.

## Resolution
- Disk: CT103 rootfs now 40 GB, ~27–32% used.
- Loki healthy; syslog ingestion normal.
- Self-monitoring in place → future disk creep alerts to Discord **before** it can silence syslog.

## Lessons / gotchas
- **`sed -i` breaks Docker single-file bind mounts.** It swaps the file inode; the container stays pinned to the old inode, so a SIGHUP reload loaded stale config. Fix required a Prometheus container restart to re-resolve the mount. **For future `prometheus.yml` edits: edit in place (preserve inode) or restart the container after.**
- **The monitoring host was a monitoring blind spot** — it did not scrape itself. Now fixed.
- **Docker containerd image store**: layers live under `/var/lib/containerd` (moby namespace), not `/var/lib/docker`. `du /var/lib/docker` misleads; the space shows as `df`-used but not where you expect.

## Follow-ups
- [ ] Consider Loki/Prometheus retention caps + Docker `json-file` log-size limits to prevent slow refill of the 40 GB.
- [ ] Config-as-code hygiene: `gpu`/`snmp-ex3400` drift now reconciled; the manual-deploy workflow keeps re-introducing live-only drift — periodically diff live `/opt/grafana/prometheus.yml` vs `netframe-monitoring-stack/ct103/prometheus.yml`.
- [ ] The 20→40 GB resize is a **live change** captured here; note it in the CT103 build/runbook.

## Changes committed
- `netframe-monitoring-stack` (branch `fix/zfs-device-level-alert`):
  - `1f7700e` — scrape CT103 node-exporter as `netframe-monitor` (self-monitor rootfs for `DiskAlmostFull`).
  - `7a9095e` — reconcile deployed `gpu` + `snmp-ex3400` scrape jobs into repo.
- CT103 rootfs backup of prometheus.yml: `/opt/grafana/prometheus.yml.bak-add-lxc103`.
