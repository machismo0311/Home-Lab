# 11 — Contradictions

**Basis:** commit `65f3681`, 2026-07-22. Read-only. Every row cites `file:line`.
Severity: CRITICAL / HIGH / MEDIUM / LOW / INFO. Class per spec §3.3.

Two of the audit spec's own §3.3 "known correction events" turned out **inverted vs. the
repo's live-verified state** — flagged as `C-HARD` below rather than applied. This is the
single most important result of Phase 1: had they been applied blindly, they would have
*introduced* errors.

---

## C-HARD — genuine disagreement, needs Kyle to adjudicate before any PR

### H1. GPU assignment — audit spec contradicts repo + live nvidia-smi  · HIGH
- **Spec §3.3 #6 asserts canonical:** RTX 8000 → Jarvis, dual RTX 6000 → QuarkyLab.
- **Repo says the opposite, uniformly and live-verified:** RTX 8000 → **QuarkyLab**
  (installed & verified 2026-07-01), 2× RTX 6000 → **Jarvis** (installed & verified 2026-07-04).
  - `topology/NetFRAME-Network-Topology.md:52,365,396`, `…tex:150,348`
  - `README.md:30,68,76,200,227`, `scripts/slurm/slurm.conf:27`, `scripts/slurm/gres.conf:4`
  - `scripts/jarvis-oncall/nodes.yaml:23,35`, `vault/00 - Homelab MOC.md:59,80,171`,
    `vault/Rack Layout.md:44,49`, `vault/Power Distribution.md:96`
- **Why the confusion:** `docs/netframe_update_2026-06-21.md:83-100` documents a deliberate
  **swap** — "QuarkyLab gets RTX 8000 (from Jarvis)", "Jarvis gets dual RTX 6000 (from
  QuarkyLab)" — planned 06-21, executed 07-01/07-04. The spec's value describes the
  **pre-swap** allocation.
- **Recommended canonical:** repo value (RTX 8000→QuarkyLab). **Adjudicate:** confirm, and
  confirm the spec's §3.3 #6 is superseded.
- **One genuinely stale copy to fix regardless:** `vault/Runbook/netframe_update_2026-06-22.md:13,22`
  still states "Jarvis → RTX 8000 48GB" (pre-swap snapshot) → also a `C-SUPERSEDED` (S-Rz below).

### H2. OPNsense version — 25.7 vs 25.1.12  · HIGH
- **~12 refs say `25.7`:** `README.md:85,183`, `topology/…md:243,375`, `…tex:363`,
  `vault/00 - Homelab MOC.md:70,74`, `vault/Networking/Network Overview.md:8,69`,
  `vault/Infrastructure/Services & VMs.md:11`, `vault/Infrastructure/Proxmox Cluster.md:124`,
  `docs/netframe-runbook.tex:216`.
- **CLAUDE.md + 3 recent runbooks say `25.1.12`:** `vault/Runbook/AAR-2026-07-20-DHCP-Kea-Outage.md:31,81`,
  `…DHCP-Kea-Monitoring-2026-07-21.md:44`, `…OPNsense-CARP-HA-Plan-2026-07-22.md:15-16`.
- **Live tiebreaker:** `AAR-2026-07-20…:163` explicitly says *"OPNsense reports 25.1.12 (docs
  say 25.7 — reconcile)"* — the box **reports 25.1.12**. `CARP-HA-Plan-2026-07-22.md:14,64,74`
  frames **25.7 as the future upgrade target**, not current state.
- **Recommended canonical:** `25.1.12` (live). The 25.7 refs are premature/aspirational.
  Spec §3.3 #3 ("25.1→25.7") is **backwards**: the docs jumped ahead, not behind.
- **Adjudicate:** confirm 25.1.12 as current (your own AAR already flagged this reconcile).

### H3. DS4246 cabling connector type  · MEDIUM
- **Repo says:** `SFF-8644 → SFF-8088` (`README.md:166`, `vault/Runbook/netframe_update_2026-06-22.md:44`).
- **Spec §3.3 #1 canonical:** `QSFP (SFF-8436) → SFF-8088`.
- No uncorrected `SFF-8088 → SFF-8088` copies exist (that part of the correction is clean).
- The disagreement is the **shelf-side connector** (SFF-8644 vs QSFP/SFF-8436). This is a
  hardware fact — **settle in Phase 2 live scan** (inspect the actual cable/HBA) or by Kyle.

---

## C-SUPERSEDED — fact corrected/live elsewhere, stale copies remain (canonical clear)

### S-Grafana. Monitoring stack node pve3 → pve4 not propagated  · HIGH
Grafana/Prometheus/Loki (LXC 103) moved **pve3 → pve4** in the 2026-07-16 de-concentration
(`CLAUDE.md`; `vault/Runbook/AAR-2026-07-16-Pve3-Outage.md:169`). Stale "pve3" remains in:
`README.md:110`, `topology/…md:262,384,453,612`, `vault/00 - Homelab MOC.md:87`. IP `.183` unchanged.

### S-Headscale. Headscale node pve3 → pve5 not propagated  · HIGH
Headscale (LXC 105) moved **pve3 → pve5** (same 2026-07-16 event; `AAR-2026-07-16…:169`).
Stale "pve3" in: `README.md:186`, `topology/…md:265,322,385`, `docs/netframe-runbook.tex:394,403`,
`vault/ADR/0004-self-hosted-headscale.md:10`. IP `.186` and v0.29.1 consistent.

### S-RandyCPU. Randy CPU still "v4 / 28c/56t" in stale copies  · HIGH
Corrected 2026-07-11 to **E5-2690 v3 / 24c / 48t** (nproc=48, measured). Stale v4:
`docs/netframe_update_2026-06-21.{md:16,tex:54}`, `docs/randy-commissioning-runbook.md:15`,
`docs/netframe-runbook.tex:148,229`, `vault/Runbook/netframe_update_2026-06-22.md:11`,
`vault/Runbook/netframe_update_2026-06-21.md:16`. (The `netframe_update_*` files are dated
point-in-time logs — annotate as historical or correct.)

### S-RandyDrives. Randy "2 spare / Unallocated" stale  · HIGH
`docs/randy-commissioning-runbook.md:27-28` still lists 2 Seagate as "Spare / Unallocated";
the vault copy (`vault/Runbook/randy-commissioning-runbook.md:27-28`) corrected it 2026-07-11
to **4 Seagate, in `datastore` RAIDZ2, no spares** (matches CLAUDE.md).

### S-Bulk. DS4246 `bulk` pool geometry pre-expansion  · HIGH
`topology/…md:424` and `vault/Infrastructure/Proxmox Cluster.md:48` say "2× 8-wide RAIDZ2,
58.2T raw / ~41.3 TiB usable". Superseded by the **2026-07-17 expansion** to **3× RAIDZ2
(8+8+6), 80.0T raw / ~55 TiB usable** (CLAUDE.md, `Runbook/DS4246-Pool-Buildout-Plan…`).

### S-VLAN. "native-vlan-id not supported on EX3400" stale  · MEDIUM-HIGH (operational)
It **is** supported (interface level, ELS) and live since 2026-06-25. Stale "not supported":
`homelab-setup.md:456`, `vault/Runbook/Network Procedures.md:87,116,129`,
`vault/Networking/Juniper EX3400-48P.md:195`. **The Juniper note self-contradicts** — lines
60/76/87/119 state the correct interface-level fix, line 195 still says "not supported".
Risk: a future operator following line 195 configures a broken trunk.

### S-Homepage. Homepage shown on pve1 LXC 104 as current  · MEDIUM
`homelab-setup.md:16` states pve1 "runs … homepage LXC 104" as current state. Homepage
**migrated to pve3 LXC 106** on 2026-06-24 (`vault/Runbook/netframe-pentest-remediation-2026-06-24.md:14,26`).
(Also wrong in the *dotfiles* `CLAUDE.md:56` — out of this repo's scope; noted for Kyle.)

### S-Rz. Jarvis GPU pre-swap snapshot — see H1 · HIGH
`vault/Runbook/netframe_update_2026-06-22.md:13,22` — "Jarvis → RTX 8000".

---

## C-SOFT — cosmetic (LOW)

### F1. Duplicate runbooks differ only in punctuation  · LOW
`runbooks/*` vs `vault/Runbook/*` copies of **VLAN-Activation-2026-06-25**,
**Homepage-Setup-2026-06-26**, **netframe_update_2026-06-21** are content-identical, differing
**only em-dash (—) vs ASCII hyphen (-)**. Mirror process normalizes punctuation. No action
needed beyond awareness (see structural note in `12-staleness.md`).

---

## Verified CLEAN (INFO — no finding)

- **QuarkyLab BIOS 2.19.0** — all `1.0.4` refs are historical narrative inside
  `docs/r730-bios-recovery-runbook.md`. No stale current-state copy.
- **LSI 9207-8e** — consistent at PCI `85:00.0`; AVAGO relocation documented. No slot conflict.
- **NVLink** — "not needed" everywhere; consistent.
- **UniFi UDR = 192.168.10.2** — correct; the `.10.2` refs are the UDR, **not** the EX3400
  (which is uniformly `.50`). The `EX3400-SSH-Auth-Failure-RCA.md` `.10.2` refs document a
  historical IP-conflict incident (needs a "historical" banner check — see `12-staleness.md`).
