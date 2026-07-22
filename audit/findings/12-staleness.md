# 12 — Staleness

**Basis:** commit `65f3681`, 2026-07-22. Read-only. A doc is *stale* not because it is old
but because a fact in it was **superseded by a later change recorded elsewhere**.

The dominant pattern: **a small set of authoritative, recent sources (CLAUDE.md + the
2026-07 AARs/runbooks) carry the corrected values, and the "presentation" docs
(README, `topology/`, `vault/00 - Homelab MOC.md`, `docs/`) lag behind.** The corrections
cluster around three dated events.

---

## Staleness clusters (root cause → stale artifacts)

### Cluster A — 2026-07-16 pve3 de-concentration not propagated  · HIGH
After the pve3 outage, Grafana stack → **pve4** and Headscale → **pve5**
(`vault/Runbook/AAR-2026-07-16-Pve3-Outage.md:169`, CLAUDE.md). Not propagated to:
- `README.md:110,186` · `topology/NetFRAME-Network-Topology.md:262,265,322,384,385,453,612`
- `vault/00 - Homelab MOC.md:87` · `vault/ADR/0004-self-hosted-headscale.md:10`
- `docs/netframe-runbook.tex:394,403`
→ These still draw the monitoring + VPN control plane on **pve3**. (Detail: `11-contradictions.md` S-Grafana, S-Headscale.)

### Cluster B — 2026-07-11 Randy hardware correction not propagated  · HIGH
Randy CPU v4→**v3 (24c/48t)** and drive layout (4 Seagate in-pool, no spares) corrected in
`vault/Runbook/randy-commissioning-runbook.md`. `docs/` twin + several update-logs still say
v4/28c and "2 spare/Unallocated". (Detail: S-RandyCPU, S-RandyDrives.)

### Cluster C — DS4246 `bulk` 2026-07-17 expansion not propagated  · HIGH
Pool grew 2×8-wide/58.2T → **3× RAIDZ2 (8+8+6)/80.0T** on 2026-07-17. `topology/…md:424` and
`vault/Infrastructure/Proxmox Cluster.md:48` still show the smaller pre-expansion geometry.
(Detail: S-Bulk.)

### Cluster D — OPNsense 25.7 vs live 25.1.12  · HIGH
Presentation docs assert a version the box hasn't reached. (Detail: H2.)

---

## Structural staleness risk

### T1. Runbooks live in three homes; `docs/` lags `vault/`  · MEDIUM
The same runbook exists under `runbooks/`, `docs/`, and `vault/Runbook/`:

| Basename | Copies | Drift |
|---|---|---|
| `randy-commissioning-runbook.md` | `docs/` + `vault/Runbook/` | **real** (v4/v3 CPU, drive count) |
| `netframe_update_2026-06-21.md` | `docs/` + `vault/Runbook/` | cosmetic (em-dash) |
| `VLAN-Activation-2026-06-25.md` | `runbooks/` + `vault/Runbook/` | cosmetic |
| `Homepage-Setup-2026-06-26.md` | `runbooks/` + `vault/Runbook/` | cosmetic |

CLAUDE.md declares **`vault/` authoritative**. Recommendation (for Phase 4 backlog, not this
PR): make `docs/`/`runbooks/` copies either generated-from-`vault/` or replaced with a pointer,
so a correction can't land in one home and rot in another. This is *why* Randy's CPU is still
wrong in `docs/`.

---

## Dead links / dangling references (C-DANGLING)

Scanned `[[wikilink]]` and relative `.md`/image references. **None broken to a nonexistent
target** in the tracked tree at the sampled scope; the vault's internal `[[...]]` links resolve
to existing notes. (A full link-graph verification is queued for Phase 3 completeness; no
CRITICAL/HIGH dangling refs surfaced in Phase 1.)

## Aged TODO / historical-context items (C-TODO / clarity)

- **`runbooks/EX3400-SSH-Auth-Failure-RCA.md`** references the switch at `192.168.10.2`
  throughout (lines 72,90,98,118-120,223-241) — this documents a **historical** IP-conflict
  incident, but `.10.2` is now the UniFi UDR and the switch is `.50`. **MEDIUM**: add a
  dated "historical — switch has since moved to .50" banner so a griever doesn't read it as
  current topology.
- **`homelab-setup.md`** carries multiple pre-cluster/pre-migration states presented in
  present tense (homepage on pve1 LXC 104:16; "native-vlan-id not supported":456;
  `pve-supermicro … TrueNAS storage (pending)`:23 — Randy is now PBS/ZFS, not TrueNAS-pending).
  **MEDIUM**: this file reads as an early build log; flag for a "superseded — see CLAUDE.md /
  topology for current state" header rather than line-by-line edits.

## No finding
- No aged `TODO`/`FIXME` markers older than 30 days that assert a broken current state beyond
  the historical-context items above.
- BIOS/LSI/NVLink/UDR-IP all verified current (see `11-contradictions.md` CLEAN section).
