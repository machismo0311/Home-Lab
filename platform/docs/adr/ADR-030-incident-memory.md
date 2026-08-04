<!--
  Public edition. Reused from the private engineering corpus.
  Source: docs/adr/ADR-030-incident-memory.md
  Sanitization: estate hostnames mapped to role names (5 occurrences across 4 lines).
  One further hostname appears as an example token illustrating that a hostname is
  shape-indistinguishable from an ordinary word; it was renamed to another lowercase
  word rather than to a role name, because a role name is self-evidently an entity and
  would have destroyed the point being made.
-->

> [ADR index](README.md) · [Package index](../../README.md)

---

# ADR-030: Incident Memory is derived from history, and correlates only on graph evidence

- **Status:** Accepted. Phase II.
- **Date:** 2026-08-01
- **Builds on:** ADR-029 (freshness gating), TD-054 (append-only durability), the Phase II roadmap
  finding that history had silently stopped, and engineering story 9 ("three components that all
  thought empty meant healthy").

## Context

`history.jsonl` records observations. Each is true and each is alone. A node reboot, a corosync
warning, a UPS event and a SMART line are four rows, and an operator at 03:00 has to notice they are
one thing. Nothing did that noticing.

## Decision 1: incidents are derived, never stored

**There is no incident store.** `correlate(observations, graph)` is a pure function, and an
incident's identity is `sha256(sorted(subjects) + first_seen)`.

Rejected: an `incidents.jsonl` alongside `history.jsonl`. Two stores means two sources of truth that
can disagree, and the one that disagrees is always the derived one. A pure function cannot drift
from its input.

The consequence that matters for the mission: *"has this happened before?"* is answerable across
months because `history.jsonl` is append-only and tracked, so the past is not rewritten and
recurrence is a lookup rather than a guess.

## Decision 2: correlation requires graph evidence, never simultaneity

Two observations join one incident only when:

1. they measured the **same** estate entity, or
2. the **knowledge graph already holds an edge** between entities they measured.

Time is a *filter*, never a *reason*: observations outside `WINDOW_HOURS` are not candidates, but
being inside the window has never once caused a grouping.

**Coincidence is not correlation.** Two unrelated failures in the same run produce two incidents,
and the mutation that makes simultaneity sufficient is caught by test.

## Decision 3: subjects are measured, not parsed

Affected systems come from the structured `value` of an observation, which is what the probe
measured. The prose `detail` is **never read**.

A probe reporting `{"coverage": {"NODE-A": "inactive"}}` measured `NODE-A`. A probe whose sentence
merely mentions `NODE-A` measured something else, and treating that as evidence would be
string-matching dressed as provenance. The mutation that feeds `detail` into the extractor breaks
**16 assertions**.

### Extraction is candidates; the graph decides
`_could_be_entity` admits candidates cheaply, because a bare lowercase token is indistinguishable
from a hostname by shape alone: `count`, `stale` and `alpha` are the same shape. Resolution against
the graph decides. Only a **prefixed** path (`ct/`, `vm/`, `pool/`, …) is self-evidently an entity,
which is why only those are reported when unresolved. An earlier version reported `degraded`,
`pending` and `spread_seconds` as affected systems: vocabulary wearing an entity's clothes.

## Decision 4: correlate against the seed, not the accumulated set

An incident's `seed` is the subject set it opened with and never changes.

Measured before this rule: **one incident absorbed 77 observations across 23 subjects.** Once an
incident contains `NODE-A`, every probe touching `NODE-A` joins, then everything those probes touch,
until one incident owns the estate. Testing against the seed bounds that growth.

This is the brief's *"split the incident rather than forcing unrelated observations together"*,
implemented as a bound on transitivity rather than as a post-hoc splitter.

## Decision 5: an OK observation may contradict but never open

`OK` observations are recorded as **contradicting evidence** on an incident they relate to, and
never create one. Any contradiction drops confidence to `LOW`, and the hypothesis says the grouping
is provisional while the recommended action tells the operator not to act until the conflict is
explained.

## Lifecycle

```
   observation (FAIL/UNKNOWN)
        |
        v
   +---------+  related to an OPEN incident's SEED, within window?
   | resolve |------------------ no ------------------> new incident (records WHY NOT)
   +---------+                                                |
        | yes                                                 |
        v                                                     v
   absorb: += evidence, last_seen, subjects            +--------------+
        |                                              |     OPEN     |
        v                                              +--------------+
   OK observation for same subjects?                          |
        | yes                                                 | identical subject set
        v                                                     | seen earlier
   contradicting evidence, confidence -> LOW                  v
                                                       +--------------+
                                                       |  RECURRING   |--> recurrence_of
                                                       +--------------+
```

`RESOLVED` is defined by `resolution_criteria` (every probe in the incident reports OK for a full
cycle) but is **not yet computed**, because that requires history the collector has not gathered.
See "remaining debt".

## Decision table

| Condition | Outcome | Recorded as |
|---|---|---|
| shares a measured entity with a seed | absorb | `both observations measured X` |
| graph edge between seed and subject | absorb | `X -hard-> Y in the knowledge graph` |
| no shared entity, no edge | new incident | `why_not_grouped` entry naming both sets |
| outside `WINDOW_HOURS` | new incident | `outside the correlation window` |
| status `OK`, related | contradicting evidence | confidence → `LOW` |
| status `OK`, unrelated | discarded | opens nothing |
| subject resolves to no node, prefixed | reported | `unresolved_subjects` |
| subject resolves to no node, bare | discarded | (indistinguishable from vocabulary) |
| identical subject set seen earlier | `RECURRING` | `recurrence_of` |

## Failure modes

| Mode | Behaviour | Why acceptable |
|---|---|---|
| history absent or corrupt | `main()` prints the freshness verdict and exits 1 | ADR-029 owns that question |
| corrupt rows mid-file | skipped here, **counted** by `freshness.py` | one owner per question |
| graph missing an entity | subject unresolved, incident still forms | never guessed at |
| graph itself stale | correlation reflects a stale topology | `kg build` runs with `oie run` |
| every probe measures one host | broad incidents | bounded by seed matching |

## What this does not do

- **No store, no timer, no automation, no alerting, no network writes.** Read-only, derived on read.
- **No root-cause claim.** `root_cause_hypothesis` is a hypothesis with contradicting evidence
  beside it, and `provenance` is `INFERRED` in the sense `claim.py` means.
- **No severity model beyond the worst observation status.** Business impact is not modelled.

## Falsification

Ten mutations, all caught. Four initially **survived**, which is the part worth recording:

| Mutation | First run | After sharpening |
|---|---|---|
| coincidence treated as correlation | caught | caught |
| relation always true | caught | caught |
| `detail` read as evidence | caught (16) | caught (16) |
| recurrence never marked | caught | caught |
| window ignored | caught | caught |
| **OK may open an incident** | **survived** | caught |
| **contradiction stops lowering confidence** | **survived** | caught |
| **correlate on accumulated subjects** | **survived** | caught |
| **unresolved subjects dropped** | **survived** | caught (both paths) |

Each survivor was a protection nothing tested. Two were my mutations targeting the wrong line or my
fixture failing to distinguish the cases; both were corrected rather than accepted. 60 assertions.

## Remaining debt

Registered rather than hidden: `RESOLVED` state computation, business-impact severity, and the
absence of probe-to-estate edges in the knowledge graph, which forces subject extraction to do work
the graph should be doing.
