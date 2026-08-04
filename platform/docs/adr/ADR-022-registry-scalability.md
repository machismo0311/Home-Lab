<!--
  Public edition. Reused from the private engineering corpus.
  Source: docs/adr/ADR-022-registry-scalability.md
  Sanitization: none required (zero estate identifiers)
-->

> [ADR index](README.md) · [Package index](../../README.md)

---

# ADR-022: Registry scalability, and the limits of the routing key

- **Status:** Accepted as a **recorded deferral**. No solution is adopted.
- **Date:** 2026-07-30
- **Context owner:** operator
- **ARB reference:** the board commissioned this as "ADR-001 Registry Scalability". It is filed at
  022 to keep `docs/adr/` chronological; ADR-003 and ADR-018 through ADR-021 predate it, and
  inserting a 2026-07-30 decision at 001 would make the sequence misleading forever.
- **Source:** NF-DM-007 §2.1, finding B1

## Context

The Investigation Registry resolves an operator question to exactly one investigation using the key
`(intent, asset_kind)`. Ambiguity raises rather than being resolved, which is the correct behaviour
and is not in question here.

**The key space is too small to hold the platform's stated growth target, and this is arithmetic
rather than judgement.**

JOI owns 13 PRIMARY intents. Only some are investigation-shaped; the rest are register and
provenance lookups that JOI already answers without an investigation:

| Investigation-shaped | Not investigation-shaped |
|---|---|
| `health.explain`, `storage.concerns`, `change.kubernetes`, `alert.stale`, `blast.radius` | `risk.today`, `approval.pending`, `recommendation.explain`, `recommendation.best`, `capability.maturity`, `deployment.provenance`, `change.since`, `estate.status` |
| **5** | 8 |

The ontology defines 20 asset kinds, of which roughly 10 are realistic investigation targets today
(`node`, `vm`, `ct`, `disk`, `pool`, `cluster`, `service`, `switch`, `ups`, `nic`).

**Realistic ceiling: 5 x 10 = 50 unique keys. Absolute ceiling using all 20 kinds: 100.**

The stated growth target is 100 investigations. They do not fit. And the distribution is not
uniform: investigations cluster heavily on `node`, so collisions begin far earlier than the ceiling
implies.

### Expected trigger point

**Roughly the fifth investigation**, not the fiftieth.

Host CPU already occupies `(health.explain, node)`. Host Memory, Storage Latency, Network Path and
Kubernetes Health would each claim the same key. The second `node`-targeting investigation under
`health.explain` triggers `AmbiguousInvestigationError` and the registry stops answering.

The board's decision to retain `host.cpu` rather than broaden it to `host.performance` (NF-DM-004
§10.2) means this trigger is reached during P5 rather than avoided.

## Decision

**Record the limitation. Adopt no solution.**

The registry keeps `(intent, asset_kind)`. Collisions continue to raise
`AmbiguousInvestigationError` naming every candidate. Nothing is added to break ties.

## Why deferred

Three reasons, in order of weight.

**The evidence to choose does not exist.** The three candidate approaches trade off against each
other differently depending on how much investigations genuinely overlap, and no end-to-end
investigation has been built. The board's own position on `host.performance` applies: evidence-driven
architecture over speculative consolidation.

**A tie-breaker adopted now would foreclose the better answer.** Adding a discriminator field makes
the registry resolve all seven colliding investigations and simultaneously means the platform never
has to answer whether those seven should have been one. The field would then be set by whoever adds
the eighth investigation, and by the fifteenth it is the real routing vocabulary with no owner.

**The failure is loud, not silent.** A collision raises and names its candidates. That is the one
property that makes deferral safe: the platform cannot quietly return the wrong investigation while
this decision is outstanding. Were the failure silent, this ADR would be a defect rather than a
deferral.

## Possible future approaches

Recorded without preference, so that whoever decides has the alternatives rather than the first idea.

| # | Approach | Buys | Costs |
|---|---|---|---|
| **A** | **Mint more JOI intents** (`health.cpu`, `health.memory`) | Immediate headroom; no new mechanism | JOI's vocabulary stops describing what an operator *asked* and starts describing what the platform *investigates*. Requires an operator to diagnose the problem in order to phrase the question. NF-DM-004 §4.2 rejected this as the primary answer |
| **B** | **Broaden investigations** so the count never approaches the ceiling | Removes the problem rather than routing around it; matches the evidence that Host CPU could not answer its own question without disk I/O | A broad investigation is harder to reason about, and the board deferred this pending measured overlap |
| **C** | **Add a third key dimension** (scope, subsystem) | Mechanical, immediate, resolves all collisions | Converts a modelling question into a configuration field. Configuration fields do not get reviewed. NF-DM-004 §4.3 argued against it at 10 investigations; the argument weakens at 100 |
| **D** | **Two-stage routing**: registry returns a candidate set, a second declared stage narrows | Keeps the registry's exactly-one guarantee at the final step | Introduces a new component and a new ownership question. Not evaluated |

**A and B are diagnoses of different defects, not competing mechanisms.** NF-DM-004 §4.3 frames the
choice: a collision means either two investigations answer the same question (fix by B) or operators
genuinely ask two distinguishable questions (fix by A). C and D avoid asking which.

## Decision trigger

Reopen this ADR when **any** of these becomes true:

1. A second investigation is proposed that targets `node` under `health.explain`. **Most likely, and
   expected during P5.**
2. The measured collector overlap from the P5 vertical slice is available, which is the evidence the
   board asked for.
3. Investigation count reaches 10, at which point the 50-key realistic ceiling is 20% consumed by a
   distribution that clusters.

## Consequences

- The registry is safe to build against today and will refuse to answer rather than answer wrongly.
- P5 must produce the collector-overlap measurement. NF-DM-006 §6 makes it mechanical: once
  `required_collectors` names catalog entries, overlap between two investigations is a set
  intersection rather than a judgement.
- Anyone adding a second `node` investigation before this is decided will be blocked by design, and
  should arrive here rather than adding a field.
