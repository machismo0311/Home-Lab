# 31 — Proposal: prometheus-pve-exporter + alert-rule gaps (R-05 / R-06)

**Status:** PROPOSAL — design only, nothing deployed. Read-only-grounded 2026-07-22.
**Target repo for the config:** `machismo0311/netframe-monitoring-stack` (config-as-code).
**Conventions honored:** LXC not Docker; Python in venv; systemd units; localhost-only bind
(F-03); PVE token in Vaultwarden, never hardcoded; Grafana unified alerting → existing Discord.

## Grounding (live, so we don't duplicate or assume)
- `pve_*` metrics: **absent** → pve-exporter is a real gap.
- `blackbox_exporter`: **already deployed** (probes `.177:53`, `.178:53`, `https://registry.netframe.local/v2/`)
  → reuse it for cert-expiry; add TLS targets only.
- `backup_verify_*`: **present** (`overall_pass`, `report_generated_timestamp_seconds`, `run_error`)
  → backup-stale + verify-fail alerting is **already handled** by the concurrent AAR's hardening.
  **Do not add duplicate backup rules** — reference these instead.
- Already-covered rules (leave alone): InstanceDown, Pihole primary/secondary, ZfsPoolDegraded,
  GpuTempHigh/GpuMemoryHigh, DiskAlmostFull, LowMemory, UPS.

---

## Part A — Deploy prometheus-pve-exporter  (R-06)

**What it unlocks:** per-guest running state, `onboot` flag, HA state, node online, PVE-view
storage usage, backup-task info — none of which node-exporter can see.

**Placement:** the monitoring LXC 103 on **pve4** (co-located with Prometheus; scrapes the PVE
API over the mgmt network). One instance scrapes all 8 nodes via the multi-target pattern.

**PVE API token (read-only) — do once, store secret in Vaultwarden:**
```
# On any cluster node (proposal — not executed here):
pveum user add prometheus@pve
pveum aclmod / -user prometheus@pve -role PVEAuditor      # read-only, whole cluster
pveum user token add prometheus@pve monitoring --privsep 0
#   -> copy the token value into Vaultwarden entry "pve-exporter token"
```

**Exporter (venv, per conventions) in CT 103:**
```
python3 -m venv /opt/pve-exporter/venv
/opt/pve-exporter/venv/bin/pip install prometheus-pve-exporter   # pin in requirements.txt
```
`/etc/prometheus/pve.yml` (0600, token pulled from Vaultwarden at deploy, not committed):
```yaml
default:
  user: prometheus@pve
  token_name: monitoring
  token_value: "<REDACTED:from-vaultwarden>"
  verify_ssl: false        # internal step-ca certs
```
`/etc/systemd/system/pve-exporter.service`:
```ini
[Unit]
Description=Prometheus PVE exporter
After=network-online.target
[Service]
ExecStart=/opt/pve-exporter/venv/bin/pve_exporter --config.file /etc/prometheus/pve.yml \
          --web.listen-address 127.0.0.1:9221
User=prometheus
Restart=on-failure
[Install]
WantedBy=multi-user.target
```
Bind **127.0.0.1** (F-03: Prometheus is localhost-only on this box).

**Prometheus scrape job (multi-target relabel over the 8 nodes):**
```yaml
- job_name: pve
  metrics_path: /pve
  static_configs:
    - targets:   # PVE API endpoints (mgmt IPs)
        [192.168.10.193,192.168.10.204,192.168.10.201,192.168.10.202,
         192.168.10.203,192.168.10.179,192.168.10.31,192.168.10.187]
  relabel_configs:
    - source_labels: [__address__]
      target_label: __param_target
    - source_labels: [__param_target]
      target_label: instance
    - target_label: __address__
      replacement: 127.0.0.1:9221
```

**Effort:** S. **Blast radius:** low — read-only API token, localhost bind, additive scrape job.
**Rollback:** stop/disable the unit, remove the scrape job, `pveum user del prometheus@pve`.

---

## Part B — Cluster-quorum signal (tiny textfile collector)

pve-exporter's per-node reachability is a proxy; the authoritative quorum state comes from
`pvecm status`. Reuse the **existing node-exporter textfile dir + timer pattern** (same one the
ZFS collector already uses) on one cluster node:
```bash
# /usr/local/sbin/pve-quorum-textfile.sh   (proposal)
q=$(pvecm status 2>/dev/null | awk -F: '/Quorate/{gsub(/ /,"",$2);print ($2=="Yes")?1:0}')
v=$(pvecm status 2>/dev/null | awk -F: '/Total votes/{gsub(/ /,"",$2);print $2}')
printf 'pve_cluster_quorate %s\npve_cluster_votes %s\n' "${q:-0}" "${v:-0}" \
  > /var/lib/node_exporter/textfile/quorum.prom.$$ && mv ...quorum.prom.$$ .../quorum.prom
```
5-min systemd timer. **Effort:** XS. **Rollback:** remove script+timer+`.prom`.

---

## Part C — Cert-expiry via the EXISTING blackbox_exporter

No new component — blackbox already does HTTPS. Add the internal TLS endpoints as probe targets
(step-ca-issued `*.netframe.local` + the `:8006/:8007` UIs) so `probe_ssl_earliest_cert_expiry`
is collected for them. Add to the existing blackbox scrape job's target list:
```
homepage.kylemason.org, grafana.kylemason.org, chat.netframe.local,
llm.netframe.local, https://192.168.10.187:8007 (PBS), https://192.168.10.204:443 (step-ca)
```
(module `http_2xx` with TLS, or a dedicated `tls_connect` module for the bare `:8006/:8007`.)

---

## Part D — New Grafana alert rules (only the genuine gaps)

Routed to the existing `discord-alerts` contact point. `severity` label per row.

| Rule | PromQL expression | for | Sev | Catches |
|---|---|---|---|---|
| **GuestDown** | `pve_up{id=~"(qemu\|lxc)/.*"} == 0 and on(id) pve_onboot_status == 1` | 5m | high | an onboot VM/CT that should be running is down (e.g. OPNsense, Pi-hole, NPM) |
| **ClusterQuorumDegraded** | `pve_cluster_quorate == 0` **or** `pve_cluster_votes < 7` | 2m | critical | quorum lost / a node dropped the ring |
| **CertExpirySoon** | `(probe_ssl_earliest_cert_expiry - time()) < 14*24*3600` | 1h | high | step-ca / LE cert within 14 days of expiry (step-ca auto-renew silently broken) |
| **PveNodeDown** | `pve_up{id=~"node/.*"} == 0` | 5m | critical | a PVE node's API is unreachable (complements node-exporter InstanceDown with the PVE view) |
| **PbsVerifyStale** | `time() - backup_verify_report_generated_timestamp_seconds > 30*3600` | 15m | high | *reference the existing metric* — belt-and-suspenders on the AAR's fix; only add if not already ruled |
| **RebootPending (info)** | `node_reboot_required == 1` (needs the apt textfile collector) | 12h | info | fleet patch/reboot lag (currently all cluster nodes) |

**Explicitly NOT added (already covered):** backup `overall_pass==0`, ZFS degraded, node down
(node-exporter), Pi-hole, GPU temp/mem, disk full, low memory, UPS on battery.

**Effort (all rules):** S. **Blast radius:** none (alerting only). **Rollback:** revert the rules
commit in `netframe-monitoring-stack`; Grafana reloads provisioned rules.

---

## Sequencing & risk
1. **A** (pve-exporter) first — it's the metric source B/D depend on. Verify `pve_up`,
   `pve_onboot_status`, `pve_guest_info` appear in Prometheus before writing rules.
2. **C** (cert-expiry) is independent and the cheapest real win — reuses blackbox.
3. **D** rules last, once their metrics exist. Test each by temporarily lowering the threshold
   to force a fire and confirming Discord delivery (closes the loop the 2026-07-22 AAR exposed).

**Total effort:** ~half a day. **Everything is additive + reversible.** No infra is mutated by
this document — deployment is Kyle's call from the backlog.
