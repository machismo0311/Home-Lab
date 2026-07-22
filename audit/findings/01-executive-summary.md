# 01 — Executive Summary (Phase 1)

**Basis:** commit `65f3681`, 2026-07-22 · READ-ONLY · ~34k lines / 223 files / 314 commits scanned.
Live-cluster verification (Phase 2) not yet run — nothing below is hardware-confirmed except
where a repo doc records a live reading.

## The one-paragraph version
The repo is **secrets-clean** and its **CLAUDE.md is the most accurate document in it**. The
real problem is **one-directional drift**: three dated changes (2026-07-11 Randy correction,
2026-07-16 pve3 de-concentration, 2026-07-17 DS4246 expansion) plus a premature OPNsense
version landed in CLAUDE.md and the recent AARs but **never propagated** to README, `topology/`,
`vault/00 - Homelab MOC.md`, and the `docs/` mirror. Separately, **two of the audit spec's own
"known corrections" are inverted vs. live reality** and must not be applied.

## Top findings, ranked

| # | Finding | Sev | Class | Where it's wrong |
|---|---|---|---|---|
| 1 | **GPU assignment inverted in the spec.** Live = RTX 8000→QuarkyLab, 2×RTX 6000→Jarvis (verified 07-01/07-04). Spec §3.3 says the reverse. | HIGH | C-HARD | spec (repo is right) + 1 stale log |
| 2 | **OPNsense 25.7 vs live 25.1.12.** Box reports 25.1.12; 25.7 is the *future* target. | HIGH | C-HARD | ~12 refs say 25.7 |
| 3 | **Grafana stack still shown on pve3** (moved to pve4, 2026-07-16). | HIGH | C-SUPERSEDED | README, topology×4, MOC |
| 4 | **Headscale still shown on pve3** (moved to pve5, 2026-07-16). | HIGH | C-SUPERSEDED | README, topology×3, ADR, runbook.tex |
| 5 | **Randy CPU still "v4/28c"** (corrected to v3/24c/48t, 2026-07-11). | HIGH | C-SUPERSEDED | docs×4, 2 update-logs |
| 6 | **DS4246 `bulk` still 58.2T/2-vdev** (expanded to 80T/3-vdev, 2026-07-17). | HIGH | C-SUPERSEDED | topology, Proxmox Cluster.md |
| 7 | **Randy "2 spare/unallocated" drives** (actually 4 in-pool). | HIGH | C-SUPERSEDED | docs/randy-commissioning |
| 8 | **"native-vlan-id not supported on EX3400"** — false; it's live at interface level. Juniper note self-contradicts. | MED-HIGH | C-SUPERSEDED | homelab-setup, Network Procedures×3, Juniper note |
| 9 | **DS4246 cabling** repo "SFF-8644→SFF-8088" vs spec "QSFP/SFF-8436→SFF-8088". | MED | C-HARD | verify in Phase 2 |
| 10 | **Homepage shown on pve1 LXC 104** (moved to pve3 LXC 106). | MED | C-SUPERSEDED | homelab-setup:16 (+dotfiles CLAUDE.md) |

Plus: `docs/` runbook mirror lags `vault/` (structural, MEDIUM); duplicate runbooks differ only
in punctuation (LOW); `EX3400-SSH-Auth-Failure-RCA.md` and `homelab-setup.md` need "historical"
banners (MEDIUM).

## What is NOT a problem
- **Secrets:** clean. 5 gitleaks hits are false positives (`root` / `$IDRAC_PASSWORD` shell
  vars). No rotation needed. → `13-secrets.md`.
- **CLAUDE.md:** most-current doc; needs no cuts. → `10-claude-md-review.md`.
- **BIOS / LSI slot / NVLink / UDR-IP:** verified consistent and current.

## Adjudication needed before any Phase 4 PR (spec §8 gate)
1. **GPU (H1):** confirm RTX 8000→QuarkyLab is canonical (spec §3.3 #6 superseded).
2. **OPNsense (H2):** confirm 25.1.12 is current; 25.7 refs → correct to 25.1.12.
3. **DS4246 cabling (H3):** decide by Phase 2 live inspection.

All `C-SUPERSEDED` items (#3–8, #10) have an unambiguous, doc-recorded canonical value and are
**PR-ready once adjudication of the C-HARDs unblocks the branch** — one commit per finding class
(H7), corrections flowing CLAUDE.md → the stale files.
