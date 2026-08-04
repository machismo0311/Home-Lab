<!--
  Public edition. Six of sixteen architecture decision records.
  Sanitization: recorded per file.
-->

# Architecture decision records

> These records decide **platform software**. Decisions about the infrastructure estate are recorded separately in `vault/ADR/` at the repository root.

Six of the sixteen records held privately. They were selected for **diversity of demonstrated
reasoning** rather than individual quality: six excellent records that all demonstrate the same
thing would be one data point repeated.

Original numbers are preserved. The gaps are real, not tidied away.

| Record | What it decides | Why it is here |
|---|---|---|
| [ADR-022](ADR-022-registry-scalability.md) | Defer a registry redesign | A deliberate deferral with a named trigger point, not an open-ended "later" |
| [ADR-026](ADR-026-kernel-owns-admission.md) | One component owns admission | Derives its size limit from measured turn cost rather than choosing a round number |
| [ADR-027](ADR-027-session-ownership-lifecycle.md) | The kernel owns session lifecycle | Includes a defect found in the implementation by its own tests |
| [ADR-029](ADR-029-history-freshness-gate.md) | Two gates, two exit policies | Measures the effect rather than the mechanism, and says why |
| [ADR-030](ADR-030-incident-memory.md) | Incidents correlate only on graph evidence | The most complete record: decisions, failure modes, falsification criteria, remaining debt |
| [ADR-035](ADR-035-dependency-direction-gate.md) | Dependency direction is a gate | Enforcement whose exceptions can only expire, never accumulate |

Records not published here either carry estate detail whose redaction cost exceeds their value, or
disclose operational posture that is not appropriate to publish while it remains current.

---

Next: [Governance model](../governance.md), how a rule becomes executable. · [Package index](../../README.md)
