<!--
  Public edition. Reused from the private engineering corpus.
  Source: docs/adr/ADR-029-history-freshness-gate.md
  Sanitization: none required (zero estate identifiers)
-->

> [ADR index](README.md) · [Package index](../../README.md)

---

# ADR-029: History freshness is gated in two places, with two different exit policies

- **Status:** Accepted. Phase II, P0.
- **Date:** 2026-08-01
- **Source:** the Phase II roadmap finding that collection had silently stopped for three days.

## Context

On 2026-08-01, `jarvis/oie/data/history.jsonl` held 616 observations across 18 distinct runs, every
one on 2026-07-29, several within minutes of each other. The collection timer had been authored on
2026-07-29 and never installed.

**Nothing was broken and nothing raised.** `predict` returned findings. The weekly report said
`INSUFFICIENT HISTORY` and was correct to. `chief` refused to invent a trend. Every component
degraded honestly on its own, and no component's job was to notice that the clock had stopped.

The failure mode is silence.

## The problem this decision solves

`history.jsonl` is **deliberately tracked**, because it is the engineering memory and is the only
record that makes "what regressed?" answerable across machines. That creates a tension:

- A gate that fails CI when history is stale would go **permanently red** as committed data ages,
  on every clone, forever. That teaches everyone to ignore the build, which is the failure this
  repository argues against more than any other.
- A gate that never fails leaves the original silence exactly as it was.

## Decision

**Two gates, two owners, two exit policies.**

| | `./netframe oie freshness` | `verify`'s `history-freshness` |
|---|---|---|
| Question | may **this deployment** reason from its history? | is the **repository's** committed history readable? |
| Owner | the operator | CI |
| Fails on | `STALE`, `GAPPED`, `THIN`, `ABSENT`, `CORRUPT` | `CORRUPT` only |
| Reports | full verdict with repair | everything else as `SKIP`, loudly, with the state named |

The distinction is **who can repair the failure**.

A corrupt tracked file is a repository defect: it arrived through a commit and a commit can fix it,
so CI fails. Stale, gapped or thin history is a fact about a *deployment*, recorded in data. No
commit repairs it, and for a gap **nothing** repairs it, because the observations were never taken.
Failing the build forever on an unrepairable historical fact is not rigour, it is noise.

`SKIP` is not silence here. The line names the state and points at the operator gate:

```
SKIP  history-freshness (STALE - deployment state, not a repository defect; run ./netframe oie freshness)
```

## Why the gate measures the effect, not the mechanism

It would be possible to check whether the systemd timer exists and is enabled. The gate does not,
for two reasons.

1. **A timer that exists, is enabled, and silently fails to run would pass that check.** History age
   is the effect, and the effect is what makes a report unsafe.
2. It would be environment-dependent. CI has no user session and correctly has no timer, so the
   check would fail everywhere it is not relevant.

The timer appears in the **repair text**, which is where a mechanism belongs.

## Consequences

- `freshness.assess(path, now)` is a pure function of its two arguments, so tests never touch the
  wall clock or the operator's real history.
- It **reads only**. It never repairs, never writes, and never runs the collector. A module that
  fixed its own input could not be trusted to report on it.
- It returns `UNKNOWN` rather than `OK` when it cannot tell, because "no news" being read as good
  news is the exact defect it exists to prevent.
- Six facts are now available to every operational report: observation count, observation age, last
  collection, observed cadence, expected cadence, and freshness confidence.

## A dependency this exposed

The operator gate was **worthless when first wired**: `./netframe oie freshness` exited 0 while
`jarvis/oie/oie.py freshness` exited 1. The dispatcher ran the child and fell through to
`exit $rc` with `rc` still at its initial 0.

That is **TD-058**, already registered. Its dispatcher half is closed here, because a freshness gate
whose exit code is discarded one frame above it does not gate anything. The three pass-through verbs
now propagate. TD-058's remaining scope, the seven distinct exit codes `investigate.py` defines, is
untouched.

## Falsification

Seven mutations, each removing or weakening a protection, all caught:

| Mutation | Result |
|---|---|
| staleness check removed | 7 assertions fail |
| gap check removed | 4 fail |
| thin-history check removed | 5 fail |
| missing file reports OK | 3 fail |
| corrupt rows silently skipped | 3 fail |
| `trend_safe` granted on every verdict | 4 fail |
| staleness threshold widened to a year | 7 fail |

The last one matters most: it is the shape a well-meaning change takes when someone is tired of the
warning.
