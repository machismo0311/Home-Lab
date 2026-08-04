<!--
  Public edition. Reused from the private engineering corpus.
  Source: docs/adr/ADR-035-dependency-direction-gate.md
  Sanitization: none required (zero estate identifiers)
-->

> [ADR index](README.md) · [Package index](../../README.md)

---

# ADR-035: Dependency direction is a gate, not a document

- **Status:** Accepted.
- **Date:** 2026-08-01
- **Builds on:** the 2026-08-01 scaling architecture review (`docs/95-review-board/`),
  `jarvis/LAYERED-ARCHITECTURE.md`, TD-082.
- **Numbering note:** the same review recommends three further decisions, not yet written, for
  which the numbers 032 (one evidence record), 033 (per-host collection fan-out) and 034
  (topology as data) are reserved. This one is written first because it is the mechanism that
  keeps the other three true after they are made. The doc-integrity gate refuses a citation of a
  record that is not tracked, and it is right to: until those decisions are made, they are
  numbers, not records, and this note names them as such.

## Context

`jarvis/LAYERED-ARCHITECTURE.md` states the discipline in one sentence: *"A layer may consume only
the layer below."* The architecture review measured the import graph against that sentence and
found:

- **five upward imports** across three package pairs (`evidence -> joi`, `investigations -> joi`,
  `collection -> oie`), two of them **pinned by source-text tests**, so the violation was
  enforced as an invariant;
- **five dependency cycles**, defused only by lazy imports, which is a load-bearing accident;
- a **strongly-connected component of six packages plus the composition root**, inside which no
  build, release, or ownership order exists;
- and the mechanism that hid all of it: `jarvis/joi/` and `jarvis/oie/` import each other by bare
  module name over a mutated `sys.path`, invisible to any packaging-aware tool. Importing
  `jarvis.evidence.schema` alone prepends the OIE directory to the process-global module path.

Every other invariant in this programme has a gate. The layering had none, which is why it could
drift for five cycles while 55 gates stayed green. The review's conclusion was that this gate
outranks every feature: it is the only change that makes the other recommended ADRs durable
rather than aspirational.

## Decision 1: a total order, not a layer table

`check-dependency-direction.py` assigns every package a **rank** in a single total order, and
every cross-package production import must point from a higher rank to a strictly lower one.

Rejected: a layer table with several packages per layer, matching `LAYERED-ARCHITECTURE.md`'s
seven layers. Same-layer imports would then be unconstrained, same-layer cycles possible, and the
gate would need a second mechanism (SCC detection) to catch them. A total order needs no cycle
detector: **a graph whose edges all point down a total order cannot contain a cycle.** Cycle
prevention falls out of direction enforcement.

The order itself:

```
0 ontology   1 phrasing   2 evidence   3 collectors   4 resolver   5 collection
6 oie        7 investigations          8 investigate  9 joi
10 memory/program            11 eos    12 assurance   13 ecm/chief
```

A package absent from the table **fails the gate**. New code declares its place in the
architecture before it may import anything.

## Decision 2: the existing violations are pinned, and pins can only expire

The five upward imports are frozen in the gate, each with the reason it is tolerated and the debt
item that owns it (TD-082). Three properties make a pin different from an exception:

1. **It is exact.** Package pair plus file. A sixth upward import between the same packages in a
   different file fails.
2. **It expires loudly.** If the code stops matching a pin, the gate fails with `STALE PIN` until
   the pin is deleted. The baseline can only shrink; a dead exception is a hole the next
   violation hides in.
3. **It carries its own resolution.** Every pin's justification records the same root cause: a
   shared vocabulary (provenance constants, the closed intent set, the read-only guarantee)
   living *above* its consumers. The fix in each case is moving the owned thing down, never
   adding a second copy and never widening the pin.

## Decision 3: bare imports are resolved the way the runtime resolves them

A naive basename-to-owner map invents edges. `import render` inside `jarvis/oie/oie.py` resolves
to OIE's **own** `render.py`, not `jarvis/investigations/render.py`, because the importing
package's directory is first on `sys.path`. The review's first coupling scan made exactly that
mistake and reported a phantom `oie -> investigations` edge.

The gate therefore resolves a bare name **own-package-first**, then by unique other owner. A bare
name owned by several *other* packages is reported as `AMBIGUOUS` and fails: which module wins
then depends on runtime path order, which is itself the defect (`jarvis/joi/rendering.py` exists
solely because this already went wrong once).

## Decision 4: production code only

Tests monkeypatch across packages by design (`test_transport.py` reassigns `probes._run`), and
pinning that noise would bury the signal. The gate guards the production dependency graph;
`test_*.py` files are excluded.

Known blind spot, recorded rather than half-checked: `importlib` path-loads
(`spec_from_file_location`). The five sites that exist (`program`, `eos`, `assurance` loading
`oie/provenance.py`; `ecm`/`chief` loading `eos`/`assurance`) all point downward in the rank
order, and a regex over path strings would be guessing. If a path-load ever needs gating, that is
a rank comparison over the loaded path, not a new mechanism.

## Falsification

Four mutations, all caught by name:

| Mutation | Result |
|---|---|
| new upward package import (`ontology -> evidence`) | `UPWARD import ... rank 0 -> rank 2` |
| new upward **bare** import (`collectors` imports `guard`) | caught, resolved to `joi` correctly |
| a pinned violation actually fixed | `STALE PIN ... remove the pin so the baseline shrinks` |
| a new package with no declared rank | `package 'scratchpkg' has no declared rank` |

And the primary proof: run with the pin list emptied, the gate reports **exactly the five sites
the architecture review found**, no more and no fewer. The gate measures the same reality the
review measured.

## Amendment, 2026-08-01: the gate covers architecture fitness, not direction alone

The Architecture Stabilization milestone added public API surfaces to `jarvis/joi` and `jarvis/oie`
and needed them enforced. Rather than add a second gate that would walk the same tree with the same
rules, this one was widened. It now reports as **`architecture-fitness`** and checks five
properties: dependency direction, layering, cycle impossibility, public API boundaries, and package
ownership. The filename is unchanged deliberately, so this record and the code it describes keep
the same name.

**Public API boundaries.** Every name in each package's `__all__` must resolve, and the published
object must be the SAME object the package's own modules use. The second half is the one that
matters and is invisible without a test: these packages import each other by bare name over a
mutated `sys.path`, so `import kg` and `import jarvis.oie.kg` load one file twice under two names.
Measured before the facades were written, `kg.Graph is jarvis.oie.kg.Graph` was **False** and
`isinstance` was false across the boundary. A facade written the obvious way (`from .kg import
Graph`) publishes the second copy and hands callers objects the engine cannot recognise. The
facades therefore resolve through the same bare names the internals use, and the gate asserts it.

**Package ownership.** Module basenames owned by more than one package are counted against a
ceiling of six. Six exist today (`catalog`, `engine`, `hostcpu`, `hostmemory`, `hoststorage`,
`render`); a seventh fails. `jarvis/joi/rendering.py` exists only because of this class of
collision, being a rename of what would have been `joi/render.py`. Ceilinged rather than failed
because removing the six is package-boundary work, owned by TD-086.

Two debt items were registered by this amendment rather than fixed by it: **TD-085** (the packages
import each other by bare name, which is why the facades must too) and **TD-086** (duplicate
basenames). Both are Collection Unification work; declaring a boundary and rewriting every import
behind it are different milestones, and doing the second inside the first would have made an
additive change into a risky one.

- The SCC cannot grow. New edges point down; the frozen five are the only exceptions and each
  names its owner.
- Fixing TD-082 is now **rewarded** by the gate (a stale pin forces the pin's deletion) instead
  of silently unnoticed.
- The two source-text tests that pin V2 and V3 (`test_evidence.py:929`,
  `test_investigations.py:560`) remain until their violations are resolved; when TD-082 moves the
  shared vocabularies down, those tests change in the same commit as the pins they mirror.
- `ontology`'s Ce=0 is now enforced, not observed.

## What this does not do

It does not fix the five violations, restructure `oie`, or unify the two evidence models. Those
are the reserved evidence-record decision (number 032) and the TD-082 extraction work, in that
order per the review's roadmap. This ADR only guarantees the problem stops compounding while
that work is scheduled.
