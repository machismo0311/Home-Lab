# QuarkyLab Comprehensive Infrastructure Assurance Review

Read-only, evidence-based assurance review of the NetFRAME / km-cluster home lab
(QuarkyLab and the 7-node Proxmox VE 9.2.3 cluster), conducted 2026-07-23.

**Posture:** read-only. No system was restarted, reconfigured, migrated, or modified.
Every change proposal is held for explicit operator approval (see
`sections/recommendations.tex`). No secrets are reproduced in any deliverable.

## Basis of evidence

- **Live SSH re-verification (2026-07-23, ~09:22-09:30Z)** of every reachable node:
  cluster quorum, GPU assignment, ZFS health, guest inventory, PBS backup freshness,
  and live UPS load. See `appendices/command-log.tex` and `data/evidence-register.csv`.
- **The repo's own prior audit** (`Home-Lab/audit/`, commit `65f3681`, 2026-07-22),
  treated as generated evidence and independently re-verified, not trusted blindly.
- **Static reads** of the automation, monitoring, AI-ops (`netframe-monitor`), and prior
  assessment repositories.

Two of the review brief's own "known corrections" were found to be **inverted versus
live reality** (GPU assignment and OPNsense version direction) and must not be applied.
See `sections/drift-register.tex`.

## Layout

```
main.tex              # master document (XeLaTeX)
preamble.tex          # NetFRAME house style (teal/navy, Liberation + DejaVu fonts)
sections/             # 21 review sections
appendices/           # 7 reference appendices (registers, command log)
diagrams/             # 5 Mermaid topology/dependency diagrams (.mmd)
data/                 # 8 machine-readable CSV registers (source of truth)
evidence/             # description of evidence locations + collection methods
```

## Build

Requires XeLaTeX with Liberation + DejaVu fonts (present on Ares). `latexmk` is not
installed, so run XeLaTeX twice for the table of contents:

```bash
cd docs/audits/quarkylab-comprehensive-review
xelatex main.tex && xelatex main.tex
```

Output: `main.pdf`.

## Machine-readable registers (`data/`)

| File | Contents |
|---|---|
| `evidence-register.csv` | Every evidence source, age, reliability, limitations |
| `asset-register.csv` | Physical hosts, network + power devices |
| `service-catalog.csv` | Services, endpoints, auth, exposure, backup, monitoring |
| `drift-register.csv` | Declared vs observed vs documented state |
| `risk-register.csv` | Consolidated risks with severity, controls, treatment |
| `recommendation-register.csv` | Recommendations with class, validation, rollback |
| `backup-matrix.csv` | Per-asset backup coverage, RTO/RPO, gaps |
| `alert-matrix.csv` | Alert rules, thresholds, channels, and coverage gaps |

## Headline

An unusually mature home lab running real research (DUNE), teaching (SLURM GPU
multi-tenancy), and self-hosted LLM workloads, with defense-in-depth actually applied
and a safety-first AI-ops design. The highest-priority items are storage and backup
resilience (a faulted drive in a pool with no second copy; an effective 1-1-1 backup
posture) and a small number of single points of failure (OPNsense, the single storage
node). Full detail in `sections/executive-summary.tex`.

*This review made no changes. It is a read-only assessment.*
