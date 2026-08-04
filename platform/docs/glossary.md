<!--
  Public edition. Authored for publication; no private source document existed.
  Scope: only terms that actually appear in the published documents. Terms used
  privately but not published here are deliberately omitted.
  Sanitization: none required.
-->

# Glossary

Only the terms that appear in these public documents. If a term is not here, it is not used here.

## Names

**NetFRAME** is the platform: the software, its governance, and the documentation around it.

**Jarvis** in these engineering documents refers to the **NetFRAME software subsystem** that
performs operational reasoning: collection, evidence handling, change management, and the operator
interface. Module paths such as `jarvis/ecm/` and `jarvis/program/` are the real source layout of
that subsystem and are given for provenance. The name denotes software throughout these documents.

## Records and identifiers

**ADR**, architecture decision record. One decision, its context, the alternatives rejected, and
how it can be verified. Immutable once accepted: a later decision supersedes rather than edits.

**ODR**, owner decision record. A decision an engineer may not make alone, most often one that
grants authority or accepts risk. Separated from ADRs so that "who decided" is never ambiguous.

**TD-nnn**, a technical debt item. A deferred piece of work recorded with the trigger that would
make it urgent, so deferral is a decision rather than drift.

**GOV-nnn**, **INV-nnn**, an invariant. A property the system is required to hold, registered with
the mechanism that enforces it.

Identifiers appear in the published text because they are the real references used at the time.
Records they point to are mostly not published, so treat them as provenance rather than as links.

## Concepts

**Invariant**, a property that must always hold, paired with the thing that would notice if it
stopped holding. An invariant with no enforcement point is an intention, not an invariant.

**Witness**, the executable evidence that an invariant is actually enforced. Distinguishes "we
wrote a rule" from "the rule fails the build when violated", which is the distinction most
governance documents lose.

**Provenance**, the recorded origin of a claim. Every claim carries one of four classes:

| Class | Meaning |
|---|---|
| `MEASURED` | Observed directly, with the observation retained |
| `INFERRED` | Derived from other claims, with the derivation recorded |
| `ASSUMED` | Taken on faith, and marked as such |
| `UNKNOWN` | Not established. A valid answer, not a failure |

**Claim strength** is the **weakest** class among the claims supporting an answer, never the
strongest. An answer resting on one measured fact and one unknown is unknown-strength, because the
alternative lets a single confident measurement launder everything next to it.

**Mutation testing**, deliberately breaking code to confirm a test notices. A surviving mutation
is a located hole in the suite. See [mutation-testing.md](mutation-testing.md).

## Subsystems

**ECM**, engineering change management. The lifecycle a proposed change traverses before it
becomes real, with states that cannot be skipped and no closure without verification. See
[release-process.md](release-process.md).

**EOS**, the engineering operating system: the layer that turns observations into ranked
recommendations, which then enter ECM as change records.

**JOI**, the operator interface. The path by which a person asks the platform a question and
receives an answer carrying its evidence, or a refusal stating why no answer is available.

---

Back to the [capability map](capabilities.md). · [Package index](../README.md)
