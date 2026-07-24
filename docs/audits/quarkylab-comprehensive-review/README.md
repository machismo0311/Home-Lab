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
and a safety-first AI-ops design. The highest-priority remaining item is backup
resilience: an effective 1-1-1 posture with every copy on a single node, rack, and UPS
bus, alongside a small number of single points of failure (OPNsense, the single storage
node). Full detail in `sections/executive-summary.tex`.

## Revision 2 (2026-07-23, late)

The report was revised after additional live evidence:

- **EX3400 inspected live** (the original switch limitation is lifted). This surfaced
  that the core switch was **not** the spanning-tree root: no `bridge-priority` was set,
  so a UniFi access switch had won the election by MAC. **Now remediated** (priority 4096).
- **`ZfsPoolDegraded` root-caused.** It was never a delivery failure. The collector only
  emitted a pool-level health metric, which reads ONLINE while raidz2 retains redundancy,
  so a faulted disk was invisible. **A device-level metric and `ZfsDeviceFaulted` rule are
  now deployed and verified live.**
- **Storage urgency corrected.** `bulk` is essentially empty; the DUNE research data has
  not migrated onto it, so the faulted drive is loss of redundancy rather than imminent
  data loss. The drive replacement remains pending operator hardware.
- **Corrections:** `xe-0/2/3` is up at 10G (the recorded fault was stale), and the EX2300
  lab switch **never existed** and has been removed from the inventory.

*Discovery and verification were read-only. Two corrective changes (the ZFS alerting fix
and the switch STP root) were applied by the operator after explicit approval and verified
afterwards; see `appendices/command-log.tex`.*
