<!--
  Public edition. Reused verbatim from the private engineering corpus except where noted.
  Source: docs/01-architecture/GOVERNANCE-COMPILER.md
  Sanitization: none required (zero estate identifiers)
  Referenced implementation files are named for provenance; they are not part of this
  public edition.
-->

> [Package index](../README.md) · Next: [Release process](release-process.md), how a change reaches production.

---

# The governance compiler: semantic integrity

**Date:** 2026-07-30 · **Status:** implemented and gating · **Gate state: GREEN since 2026-07-31**
**History, kept rather than tidied away.** This document originally read as though the gate were
green while it had never been: `GOV-029` and `GOV-031` were `ci_gate` invariants with no executable
witness, so `compile-governance.py` exited non-zero on every run from the day it shipped. That was
TD-027, and it was a red build line rather than a warning. Both are now witnessed without a shell
emitter (see below) and the compiler reports **11/11 executable invariants witnessed, 11 with a
falsifying witness**.
**Answers:** how do we prove an artifact still *means* what governance says it means?

---

## 1. Semantic integrity, defined

Five distinct properties, ordered by strength. Each is a different question, and the previous
validators answered only the first three.

| Level | Question | How it is checked | Previously? |
|---|---|---|---|
| **Existence** | Is there a file at this path? | `os.path.exists` | yes |
| **Identity** | Is it *the* artifact we meant, and would a clone have it? | `git ls-files` | **no** — filesystem only |
| **Implementation** | Does it contain code the pipeline runs? | name appears in `verify` | yes |
| **Behaviour** | Did the relevant assertion actually execute, and pass? | witness ledger | **no** |
| **Semantics** | Would it *fail* if the invariant were violated? | falsifying witness | **no** |

**Semantic integrity** in this repository is the conjunction of all five for every invariant whose
enforcement type is executable.

### Why the old validators stopped at three

`validate-invariant-registry.py` asked: does `mechanism_ref` resolve to a file, and does the verify
script mention it. Both questions are about *existence* and *implementation*. Neither can
distinguish a suite that asserts the invariant from a suite that asserts something else — which is
how `GOV-040`, `GOV-041` and `GOV-044` came to cite `test_investigations.py`, a definition-identity
suite that asserts none of them, and pass every gate.

The identity failure was larger and had gone unseen entirely: **34 files, including the whole
investigation engine, were untracked.** `os.path.exists` was satisfied by files that existed only
on one laptop. Every enforcement claim resting on them would have evaporated on `git clone`.

---

## 2. Executable references

**Old binding:** invariant → filename. Proves existence.
**New binding:** assertion → invariant id, declared at the point of assertion. Proves behaviour.

```python
witness.check("GOV-041", "ast_rule",
              "no investigation module imports a language model client", not _llm_reach)
```

The chain is now mechanically provable for 8 of 10 executable invariants:

    invariant id → witness declaration (AST) → executed assertion (ledger) → pass/fail → CI gate

### The source-of-truth rule (added 2026-07-31)

A witness proves an invariant is checked. It says nothing about whether the AUTHORITY the
invariant cites is in the repository. All six `ci_gate` invariants named
`docs/01-architecture/PULL-REQUEST-CONTRACT.md` as their `source_of_truth` while that file was
untracked, so the document behind every one of them existed on one laptop. The registry validator
checks that `mechanism_ref` resolves and runs, and never asked the same question of the column
naming who decided.

`check_sources_of_truth` now refuses a `source_of_truth` that is path-shaped and either absent,
untracked, absolute, or reachable only through `..`. Cross-repository rows carry prose rather than
a path (`netframe-dashboard (serve.py)`) and are deliberately exempt: a row whose whole point is
that its subject is elsewhere cannot be failed for saying so.

### What cannot be proven automatically, and exactly why

- **`GOV-029` and `GOV-031`, RESOLVED 2026-07-31.** Both are shell-level gates
  implemented inline in `netframe` and in `promtool`, not in Python, so the AST collector could not
  see them. The fix needed no shell emitter and no new mechanism. `GOV-029`'s witness **extracts the
  gate's own regex out of `netframe`** and applies it with `grep -E` to a credential assembled at
  runtime, so there is no second copy of the pattern: weaken the gate and the witness weakens with
  it and stops detecting the planted credential. `GOV-031`'s witness asserts the invariant rather
  than the tool - alert definitions exist in the promtool-tested rules and in no Grafana dashboard -
  which is checkable by reading both places. See `jarvis/program/test_gate_witnesses.py`.

  The lesson generalises: a shell gate does not need a shell witness. It needs a Python assertion
  about the same *property*, bound to the same source of truth.
- **The connection between a witness's condition and the property it names.** A witness whose
  condition is computed but causally unrelated — `_x = len(str(KINDS)) > 0` — passes. Only mutation
  testing (break the implementation, require the witness to fail) closes this, and that needs a
  mutation target per invariant. Recorded as **TD-028**. The cheap half is implemented: a
  **constant** condition is refused structurally, so `witness.check(..., True)` fails the build.

---

## 3. The witness abstraction

A witness is executable evidence, declared where the evidence is produced.

| Kind | Meaning | Falsifying |
|---|---|:-:|
| `assertion` | a check that passes while the invariant holds | no |
| `negative` | a check that **fails** when the invariant is violated | **yes** |
| `property` | holds over enumerated or generated inputs, not one example | **yes** |
| `ast_rule` | a structural constraint on the code itself | **yes** |
| `runtime` | asserted in the production path | no |
| `graph` | a constraint over the knowledge graph | no |
| `ontology` | a closed-set or refused-relation constraint | no |

**Only falsifying kinds prove semantics.** A passing assertion proves something ran and returned
True; it does not prove the check is *about* the invariant. This is the programme's own D5
falsification standard turned on its own tests: an invariant witnessed only by `assertion` gets a
warning naming exactly that gap.

Current state: **18 witnesses, 14 falsifying, across 8 invariants.** `GOV-042` carries the one
outstanding warning — witnessed by assertion only.

`witness.py` has **no side effects** unless `NETFRAME_WITNESS_LOG` is set. Adding a witness to a
suite cannot change what that suite does, which is what makes witnesses cheap enough to add.

---

## 4. No string matching

The registry names **no file** for executable invariants. Nothing in the binding is a path.

- Rename a file → the witness moves with it. Binding intact.
- Split a module → both halves keep their witnesses. Binding intact.
- Move an assertion to another suite → the compiler finds it wherever it is.

The only name left is the invariant id, and every attack on it is now loud: renaming or deleting
`GOV-043` orphans its witnesses, and a witness naming an invariant that is not in the registry is a
build failure. **Identity replaced location**, which is the property the previous model lacked.

Witness ids are collected by **parsing**, never grepping. A witness id inside a comment is prose,
and the prior audit was defeated exactly once by counting prose as execution.

---

## 5. The traceability layer

    ADR → invariant → witness → executed assertion → verification → CI

| Edge | Independently verified by |
|---|---|
| ADR → invariant | explicit id reference in the ADR text, word-boundary matched |
| invariant → witness | AST scan for `witness.check("ID", ...)` |
| witness → executed assertion | the ledger: the witness ran in a real interpreter |
| assertion → verification | the recorded `ok` value |
| verification → CI | the compiler is a gate in `./netframe verify` |
| invariant → owner | ODR cross-check: an ODR naming an invariant forces `owner=owner` |

All six edges are in the knowledge graph: 18 `witness` nodes, `witnessed_by` and `asserted_in`
edges, each carrying its kind and whether it falsifies.

---

## 6. Attacks

Every attack that previously succeeded silently, re-run against the compiler in an isolated copy.

| Attack | Before | Now | Detected by |
|---|:-:|:-:|---|
| Delete a witnessed invariant | silent | **caught** | witnesses orphaned |
| Rename an invariant id | silent | **caught** | witnesses orphaned |
| Downgrade executable → documentation | silent | **caught** | witnesses contradict the declared type |
| Move owner authority | silent | **caught** | ODR names it; owner must be `owner` |
| Remove verification | silent | **caught** | verification is derived, not a column |
| Delete the witnesses from the suite | — | **caught** | executable invariant with no witness |
| Witness condition replaced with `True` | — | **caught** | constant condition refused |
| A witness fails while its suite exits 0 | — | **caught** | ledger records `ok=false` |

**8 of 8.** All five previously-silent attacks are now loud.

### The one that still succeeds

A witness whose condition is **computed but causally unconnected** to the property:

```python
_looks_computed = len(str(O.ASSET_KINDS)) > 0
witness.check("GOV-029", "negative", "secret scanning refuses a planted credential", _looks_computed)
```

Verified: this is accepted, and GOV-029 is reported as witnessed with a falsifying witness. **This
is not fixable by inspection.** Distinguishing a real check from an elaborate fake is equivalent to
deciding what code means. Only mutation testing closes it — break the implementation, require the
witness to fail — and that is TD-028, unimplemented pending Board direction.

What the design does achieve: the attack now requires *deliberate deceit written into a tracked
file under review*. Every accidental erosion — refactor, rename, downgrade, drift — is caught. The
threat model moved from "silent decay" to "someone lied on purpose in the diff".

---

## 7. Repository impact

| Dimension | Assessment |
|---|---|
| **Engineering complexity** | Low. Two modules, ~340 lines total. `witness.py` is 90 lines and has one public function. |
| **Maintenance cost** | Low, and *decreasing*: a witness lives beside the assertion it describes, so it is maintained by the person editing that assertion, not by someone updating a register they do not own. |
| **Runtime overhead** | None in production. `witness.check` appends a dict; the ledger is written only when the compiler asks. |
| **CI overhead** | **+0.6 s.** The compiler takes 2.2 s; the three suites it runs take 1.6 s standalone and `verify` already runs them. The marginal cost is the AST scan and the subprocess launches. |
| **False positive risk** | Low but real. The compiler fails when a suite exits non-zero, so an unrelated failure in a witnessing suite also fails the compiler — correct but potentially confusing. The `constant condition` rule could in principle reject a legitimate witness whose condition is a module-level boolean constant; none exists today. |
| **Future extensibility** | The ledger is a JSON-lines contract, so any language or shell gate can emit witnesses without changing the compiler. That is the path for TD-027. |

**Not optimised for elegance.** The design accepts a slower CI gate, a second scan of the tree, and
the awkwardness of witness declarations inside test bodies, in exchange for making silent semantic
erosion impossible. Every trade went that direction.

---

## What changed in the repository

1. `jarvis/program/witness.py` — new, the abstraction.
2. `jarvis/program/compile-governance.py` — new, the compiler; wired into `./netframe verify`.
3. Witnesses added at real assertion sites in `test_hostcpu.py`, `test_ontology.py`,
   `test_nodehealth.py` — the places the assertions actually live, correcting the three false
   citations from the previous audit.
4. **34 previously untracked files committed**, including the entire investigation engine. They
   were running in `verify` and existed in no repository. This was found by the compiler on its
   first run and is the most consequential single fix in this phase.
5. `jarvis/build-knowledge-graph.py` — witness nodes and edges.
