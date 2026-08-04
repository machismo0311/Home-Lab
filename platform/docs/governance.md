<!--
  Public edition. Reused verbatim from the private engineering corpus except where noted.
  Source: docs/01-architecture/GOVERNANCE-MODEL.md
  Sanitization: none required (zero estate identifiers)
  Referenced implementation files are named for provenance; they are not part of this
  public edition.
-->

> [Package index](../README.md) · Next: [Governance compiler](governance-compiler.md), which checks these rules are enforced.

---

# The NetFRAME governance model

**Adopted:** 2026-07-30 by the Architecture Review Board, governance phase
**Answers:** how does policy become executable?

---

## The answer, in one paragraph

Policy becomes executable when **the declaration itself carries a mechanically checkable
obligation**. Writing more policy does not do it; TD-013 established that a register entry, a
working matcher and a convincing demonstration can all exist while the invariant constrains
nothing. So in this model, saying "this is a CI gate" commits you to a named mechanism that must
exist and that `./netframe verify` must actually run, and saying "this is documentation only"
forbids you from claiming the build will catch a violation. The enforcement type is not a label
describing an invariant. It is a contract the invariant signs, and
`jarvis/program/validate-invariant-registry.py` collects on it every build.

---

## What was wrong

74 registers exist in this repository. Exactly one gate applies to all of them: a **column-count
check**. It verifies that rows are not ragged. Nothing else in the pipeline reads a register's
content, and until 2026-07-30 exactly one register (technical debt) had a semantic validator.

The consequences were measured, not assumed:

- 11 of 11 intents were documented and had matchers. **Zero** were executed against real state.
- 11 of 15 operational invariants declared `ENFORCED`. **Zero** were executed by `./netframe verify`.
- 2 of those named `serve.py`, a file in a **different repository** that no gate here can reach.
- 1 named a rules file that nothing gates, while verify tests a *different* rules file.
- INT-011 sat violated for a day while every artifact around it looked healthy.

The pattern: **the invariants this codebase enforced were the ones with executable assertions, and
the ones it merely recorded were the ones in CSV files.** The registers were built as memory, and
memory was mistaken for control.

---

## Task 1: the invariant registry

`governance/invariant-registry.csv`. Every entry declares **exactly one** enforcement type from a
closed set. Unspecified is not permitted, and the validator refuses both an empty value and an
invented one.

| Type | Meaning | Must also declare |
|---|---|---|
| `documentation_only` | Recorded so humans know it. Nothing detects a violation. | — |
| `human_review` | A human must consider it before a change. | `review_trigger` |
| `ci_gate` | A check in `./netframe verify` fails on violation. | `mechanism_ref` |
| `runtime_assertion` | Code asserts it while running. | `mechanism_ref` |
| `runtime_policy` | Evaluated at runtime against live state; refuses the action. | `mechanism_ref` |
| `structural` | **Proposed addition.** The capability to violate does not exist. | `mechanism_ref` |
| `cross_repository` | Enforced by a different repository. Not verifiable here. | `external_ref` |
| `external_dependency` | Enforced by a vendor, upstream or device. | `external_ref` |
| `owner_decision` | Held open pending an owner ruling. | `odr_ref` |

### The proposed ninth type

The Board's list has no home for the strongest control this programme uses. A `runtime_assertion`
is a guard clause that can be removed by deleting a line. A **structural** constraint requires
building something that is not there: the ontology's `REFUSED_RELATIONS` means a causal claim is
*unrepresentable*, not merely rejected.

Filing those under `runtime_assertion` would flatten the distinction the entire safety model rests
on, so the taxonomy is submitted for amendment rather than quietly stretched. **The Board's ruling
is requested.** One invariant currently uses it (GOV-046); if the Board declines, it reclassifies
to `runtime_assertion` and the model loses a distinction rather than breaking.

### Why `documentation_only` is honourable

The strongest temptation in a registry like this is to make weak enforcement types look shameful,
so everyone declares `ci_gate` and the column becomes fiction. **That already happened here.** A
registry's value is that it is true, not that it is impressive. The validator therefore challenges
only *strong* claims: an entry claiming weak enforcement is never questioned, while an entry
claiming a gate must prove the gate runs.

### The anti-overclaim rule

An enforcement type cannot promise a failure behaviour it has no mechanism to produce.
`documentation_only` may not claim `block_build`. `cross_repository` may not claim to block *this*
build, because its mechanism is somewhere else. That single constraint is what makes INV-019 and
INV-020 unrepresentable in their old form.

---

## Task 2: memory separated from control

The old registers mixed four things. The separation is **structural, not procedural**:

| | Control | Memory |
|---|---|---|
| Register | `governance/invariant-registry.csv` | `jarvis/data/operational-invariants.csv` |
| Holds | what must remain true | what we learned, and when |
| Enforcement column | mandatory, closed vocabulary, validated | **none, by design** |
| Can claim to be enforced | yes, and must prove it | **structurally cannot** |

A memory register with no enforcement column cannot lie about enforcement. This is the programme's
own principle applied to its governance: **an absent capability beats a guard clause.**

Every control entry declares five things, which are the five the Board named:

- **owner** — who may change it (`owner` / `engineering` / `arb` / `external`)
- **source_of_truth** — where the authoritative statement lives, exactly one place
- **enforcement mechanism** — `enforcement_type` plus `mechanism_ref`
- **verification mechanism** — `verification_type` plus `verification_ref`
- **failure behaviour** — what happens on violation

### Verification is not enforcement

Conflating them is precisely what produced TD-013. **Enforcement stops a violation; verification
proves the enforcement still runs.** INT-011 had enforcement (a matcher) and no verification
(nothing executed it), so it looked controlled while constraining nothing. They are separate
columns because they are separate failures.

**Recommendation requiring approval:** the legacy `enforcement_status` column in
`operational-invariants.csv` is now superseded and should be dropped, since its claims live in the
invariant registry. It is a destructive edit to a file with historical value, so it is proposed
rather than performed. The register is retained in full for its `learned_from` history.

---

## Task 3: the Owner Decision Record

`governance/odr/`. Template at `ODR-TEMPLATE.md`; first instance `ODR-001-execution-authority.md`.

Four categories are reserved to the owner: **execution authority**, **blast-radius acceptance**,
**autonomous behaviour**, **safety policy**. An `owner_decision` invariant must name an ODR, and
the validator fails if that ODR does not exist.

Three properties make it more than a form:

1. **Engineering prepares everything above the decision line and nothing below it.** An ODR whose
   decision section was drafted by the party it constrains is not a decision; it is a suggestion
   that has been formatted persuasively.
2. **Every ODR expires.** Standing authority that never lapses is how autonomy expands without
   anyone deciding to expand it. On expiry the authority lapses and the gate fails.
3. **Routing an engineering decision here is a defect, not a courtesy.** It trains the owner to
   rubber-stamp, and an owner who rubber-stamps is not a control.

This exposed a structural error in engineering's own recent work: **ADR-024 was written by
engineering and ends in an owner decision section**, putting the decision inside an artifact
engineering may edit. ADR-024 is retained as the analysis; ODR-001 now holds the decision.

---

## Task 4: the audit

Regenerate with `python3 jarvis/program/audit-invariants.py`. It **measures** each row against the
repository rather than reading its enforcement column, because a matrix built by trusting that
column is what the old register already produced.

**34 invariants.**

| Property | Count |
|---|---|
| Enforced by something other than documentation | 30 / 34 |
| Verified (something confirms enforcement still runs) | 12 / 34 |
| Executable (machine-enforced, not human-performed) | 10 / 34 |
| Cross-repository | 2 / 34 |
| Human-only | 21 / 34 |

**Declared enforcement differing from reality: zero.** That is a result, not an assumption — the
validator refuses a registry where they disagree, and the audit re-measures independently so it
would catch the validator itself being wrong.

The honest summary is less flattering than the zero suggests: **21 of 34 invariants are enforced
only by a human remembering them**, and only 12 have any verification at all. The registry has not
made the estate safer. It has made the gap visible and impossible to misreport, which is the
prerequisite for closing it.

### Divergences found and corrected during migration

- **11 rows** claimed `ENFORCED` with nothing executing them. Reclassified to `human_review` or
  `documentation_only` per row.
- **GOV-031** (INV-012): the register named `provisioning/alerting/netframe-rules.yml`; verify
  actually tests `p4-detection/netframe-p4-rules.yml`. The cited file was not the gated one.
- **GOV-033 / GOV-034** (INV-019 / INV-020): enforcement point in another repository. Now typed
  `cross_repository`, which structurally cannot claim to block this build.
- **INV-013 … INV-017** do not exist. The numbering gap was never explained and is not explained
  now; it is recorded so the next reader does not assume five rows were lost.

---

## Task 5: technical debt register v2

Severity alone ranked items by how bad they felt. It could not answer the question that actually
schedules work, so a governance defect and a naming inconsistency sorted identically.

Added columns: **category** (`technical` / `architectural` / `governance` / `product`),
**review_milestone**, **enforcement_impact**.

`enforcement_impact` is the column that connects the two registers: `none`,
`weakens_enforcement`, `blocks_enforcement`, `no_enforcement`, `masks_violation`. An item declaring
anything but `none` must name the affected control in its impact text, or the register captures a
scheduling fact and loses the safety fact.

Current state: 20 items — 8 architectural, 6 governance, 6 technical. **8 degrade enforcement**:
1 blocks it, 4 record an invariant that never had a mechanism, 2 weaken an existing control, and 1
masks a violation.

A **milestone**, not a date, because dates slip silently while a milestone is an event somebody is
already going to run into.

---

## The five questions

For any policy in NetFRAME:

| Question | Answered by |
|---|---|
| Who decided it? | `owner` column; for owner-reserved questions, the ODR's decision section |
| Where is it recorded? | `source_of_truth` + `source_type`, exactly one place |
| Who enforces it? | `enforcement_type` + `mechanism_ref` |
| Who verifies it? | `verification_type` + `verification_ref` |
| Who may change it? | `owner` column, and the change path that owner implies |

---

## What gates this model

The governance model is subject to its own rules. Three checks run on every `./netframe verify`:

- `invariant-registry` — the registry conforms to the vocabulary and every strong claim resolves
- `governance-model` — 60 assertions, each a row **built to break a rule**, failing if a bad row
  passes
- `invariant-enforcement` — INT-011 / GOV-011 against real state

The negative-test suite exists because a validator that has never rejected anything is
indistinguishable from one that cannot. It has already earned its place: it caught this model's own
reachability check matching `jarvis/intent-check.py` inside a **comment** in the verify script,
counting prose as execution. The detector had the exact defect it was built to detect.

**`./netframe verify` is currently RED** on `invariant-enforcement`, and stays red until the owner
decides ODR-001. Letting that gate warn instead of fail was considered and rejected: it would
restore a green build while the disagreement persisted, reproducing the condition that let TD-013
go unnoticed.
