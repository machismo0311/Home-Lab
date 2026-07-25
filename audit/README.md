# Documentation reconciliation audits

This directory holds the findings from periodic **documentation-vs-reality audits** of this
repository: structured passes that check whether what the docs claim still matches what the
estate actually runs.

The problem being solved is one-directional drift. In an actively-changed environment, a
correction tends to land in whichever document was open at the time (a CLAUDE.md note, the
latest after-action report) and never propagates to the README, the topology reference, the
vault index, or the `docs/` mirror. Left alone, the repository slowly becomes confidently
wrong. These audits find that drift, rank it, and produce a remediation backlog that is worked
on a dedicated branch.

## How an audit runs

Each audit is **read-only discovery first**. No infrastructure is changed, and nothing is
committed to `main` during discovery. Repository writes are confined to a dated
`audit/YYYY-MM-DD-reconciliation` branch, which is reviewed and merged like any other change.
Every finding records the commit the audit was based on, so it is reproducible.

Findings are severity-ranked and classified by whether the *repository* is wrong or the
*audit's own assumptions* are wrong. That distinction matters: an audit spec can itself carry
inverted "known corrections," and applying those blindly would introduce drift rather than
remove it.

## File numbering

Findings are numbered by phase so the reading order is the audit order.

| Range | Phase | Contents |
|---|---|---|
| `00`-`0x` | Plan and summary | Plan of attack, corpus statistics, executive summary |
| `1x` | Document review | Per-document accuracy review, contradictions, staleness |
| `2x` | Live verification | Coverage matrix, live health, storage and backup, observability |
| `3x` | Analysis | Gap analysis and proposals |
| `4x` | Output | Remediation backlog (the work items an audit produces) |

## What is and is not committed

Only `findings/` is tracked. The working directories are deliberately gitignored (see
[`.gitignore`](.gitignore)):

| Path | Status | Why |
|---|---|---|
| `findings/` | tracked | Conclusions, already generalized. Safe to publish. |
| `raw/` | ignored | Raw command output captured during discovery. |
| `live/` | ignored | Live host readings. |
| `facts/` | ignored | Extracted per-host fact tables. |

Those three carry live host detail (addresses, versions, serials, service layout at a
point in time) that has no reason to be published. The conclusions drawn from them do.
This mirrors the publishing discipline described in the top-level
[README](../README.md#-security--reliability-engineering).

## Relationship to the change log

An audit produces findings; the **change log** records what was done about them. A finding is
closed when its correction lands on `main` and the remediation backlog entry is marked
complete, not when the finding is written.
