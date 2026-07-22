# 00 — Audit Plan of Attack

**Audit basis:** commit `65f3681f8f9cff9cbd84420c15acad48afced814` on branch `main`
**Start:** 2026-07-22T14:56:59Z · **Auditor:** Claude Code (read-only discovery)
**Repo:** `/home/machismo/Home-Lab` (`machismo0311/Home-Lab`) — spec's `~/git/Home-Lab`, path adjusted
**History depth:** 315 commits across all branches

Mode is **READ-ONLY discovery** per the NetFRAME Audit Spec v1.0. No infrastructure
changes. Repo writes confined to a future `audit/YYYY-MM-DD-reconciliation` branch
(Phase 4); nothing committed to `main`/`master`. This file and all findings live in
`audit/findings/` (committable); `audit/raw/`, `audit/live/`, `audit/facts/` are
gitignored (H6) because they carry live host detail.

---

## 1. Corpus at a glance

| Metric | Value |
|---|---|
| Tracked files | 223 |
| Tracked lines | 33,787 |
| Markdown | 115 files / 16,255 lines (the bulk of the truth-claims) |
| Ansible (`playbooks/`) | 34 files (yml/roles/inventory/group_vars) — the spec's `ansible/` |
| Scripts (`scripts/`) | 40 files (12 py, 13 sh, + service/conf/yml) |
| LaTeX `.tex` | 7 files / 3,466 lines (sources for the PDFs) |
| PDF | 7 files — **generated artifacts**, each has a `.md` or `.tex` source |
| Obsidian vault (`vault/`) | 83 files — the primary knowledge base |

Raw inventory: `audit/raw/file-inventory.tsv` (sorted by line count).
Basis pin: `audit/raw/audit-basis.txt`.

## 2. Read strategy — full LLM read vs. mechanical extraction

**Full LLM read (semantic — claims, contradictions, staleness):**
- `CLAUDE.md` (26 KB) — standing-context file, audited hardest (§3.5). **Note: gitignored**
  (`/CLAUDE.md` rule) so it is *not* a tracked file, but it exists on disk and every
  future agent trusts it. Audited anyway; its non-tracking is itself an INFO finding.
- `README.md`, `homelab-setup.md`, `topology/NetFRAME-Network-Topology.md`
- All of `runbooks/` (8), `vault/Runbook/` and the rest of `vault/` (83)
- `docs/*.md` (21) incl. incident/pentest/commissioning docs
- `headscale/HEADSCALE.md`
- `.tex` sources (read the source, **never** the PDF binary)

**Mechanical extraction first, LLM to adjudicate (Phase 1.1 greps):**
- Every IP, host token, VLAN id, version string — across the *current tree* and *all
  history* (`git log --all -p`) to build `audit/facts/ledger.yaml` and detect
  superseded facts.
- Scripts (`scripts/`, `playbooks/`) scanned for hardcoded IPs/hosts/versions/secrets;
  read in full only where they assert infrastructure facts (e.g. `llm_router.py`,
  Ansible `inventory/`, `group_vars/`).

**Skip / do-not-read:** the 7 `.pdf` binaries (read their `.md`/`.tex` twins instead);
`.obsidian/`, `.st*` (gitignored editor/Syncthing state).

## 3. Known high-value drift targets (found during inventory)

**Duplicate runbooks — same basename in multiple homes.** Runbooks live in *three*
places (`runbooks/`, `docs/`, `vault/Runbook/`); these exact pairs will be diffed for
`C-SUPERSEDED`/`C-SOFT`/`C-HARD` in Phase 1:

| Basename | Copies |
|---|---|
| `randy-commissioning-runbook.md` | `docs/` + `vault/Runbook/` |
| `VLAN-Activation-2026-06-25.md` | `runbooks/` + `vault/Runbook/` |
| `Homepage-Setup-2026-06-26.md` | `runbooks/` + `vault/Runbook/` |
| `netframe_update_2026-06-21.md` | `docs/` + `vault/Runbook/` |

The three-home runbook layout is itself a structural drift risk to call out.

**PDF/source divergence.** Each PDF (`netframe-runbook`, `netframe_update`,
`pentest-remediation`, `laptop-recovery`, both student guides, topology) may lag its
`.md`/`.tex` source. Diff source-vs-PDF-intent noted; PDFs are re-generated, not
hand-edited, so the source is canonical.

**Known correction events to hunt uncorrected copies of** (spec §3.3): DS4246 cabling
(QSFP/SFF-8436→SFF-8088), EX3400 mgmt IP (.2→.50), OPNsense 25.1→25.7, QuarkyLab BIOS
1.0.4→2.19.0, VLAN `native-vlan-id` at interface level, GPU assignment (RTX 8000→Jarvis,
2× RTX 6000→QuarkyLab, no NVLink), LSI 9207-8e slot move, NetFRAME logo baseline.

## 4. Phase execution order & gates (per spec §8)

| # | Phase | Output | Gate |
|---|---|---|---|
| 0 | **Inventory + this plan** | `00-plan.md`, `raw/` | **← YOU ARE HERE. STOP for go-ahead.** |
| 2 | Phase 1 — git contradictions & staleness (**top priority**) | `11-contradictions.md`, `12-staleness.md`, `13-secrets.md`, `10-claude-md-review.md`, ledger | STOP for `C-HARD` adjudication |
| 3 | Phase 2 — live cluster scan (read-only SSH) | `20`,`21`,`22`,`23`,`24` | Post summaries, continue |
| 4 | Phase 3 — gap analysis | `30-gap-analysis.md` | Full report |
| 5 | Phase 4 — reconciliation PR (docs only, branch only, **no merge**) | PR + `40-remediation-backlog.md` | Open, do not merge |
| 6 | Phase 1.6 — portfolio review | `99-portfolio-review.md` | Lowest priority |

If any phase blows the context budget: checkpoint to disk, summarize, resume with
`audit/facts/ledger.yaml` as the handoff artifact.

## 5. Known limits / caveats up front

- **CLAUDE.md untracked** — audited from disk; changes to it can't go in the doc PR the
  normal way (it's gitignored by design for OPSEC). Corrections proposed as a diff only.
- **Live scan reachability (Phase 2)** — any node that fails `BatchMode` SSH is recorded
  `UNREACHABLE`, which is itself a finding; not guessed.
- **OPNsense / VM 100 (pve2)** — read-only via API/dashboard only. Never touched (H2).
- **Secret scan** covers patch *history*, not just the working tree — a deleted key still
  ships in packfiles. Any hit halts the audit for rotation (§3.4).
- **Parallel sessions** — other Claude sessions may commit as the same author; before any
  future branch/commit I `git pull --rebase` and stage only `audit/` paths, never `-A`.

---

**STATUS: Phase 0 complete. Awaiting go-ahead to begin Phase 1 (git deep scan).**
