<!--
  Public edition. Six of fifteen engineering stories, reused from
  docs/ENGINEERING-STORIES.md. Text is unchanged except where a substitution is
  recorded below. Original numbering is preserved so the selection is visible.
  Sanitization: see the note under each affected story; none needed in this set
  beyond what is listed in the staging record.
-->

# Engineering stories

Six of fifteen things that actually happened in this codebase, each with a commit behind it.

**Four of the six are mistakes I made and then found.** That ratio is deliberate: an engineering
history with no self-inflicted defects in it is a history that was written afterwards.

Original numbering is kept, so the gaps show that this is a selection rather than the whole record.

---

## 7. A README that only worked on my machine

**Situation.** Adding real output to the README so a reader sees the product without running it.

**Problem.** A fresh-clone dry run showed `./netframe verify` **failing** on the gate I had just
written.

**Investigation.** The gate anchored on the rich estate answer. A fresh clone cannot produce it:
probe results describe a private network and are not committed, so a stranger's answer is
legitimately thin, reporting two facts `UNKNOWN` and confidence `INSUFFICIENT`.

**Decision.** Do not commit the evidence and do not soften the gate. Rewrite the README around what
a stranger *can* reproduce, and treat the difference as the point: the thin answer is the product
refusing to invent evidence it does not have. Retarget the anchors to the two commands whose output
is identical everywhere.

**Outcome.** `128446f`. A fresh clone now produces **53 PASS / 1 FAIL / 2 SKIP, identical to the
workstation.**

**Lesson.** A claim that only holds on the author's machine is the failure this whole project argues
against, and I shipped one.


---

## 8. Mutation testing, and what it found outside its own zone

**Situation.** Thirty-three mutations had been applied across the admission layer, all caught.

**Problem.** That number was being quoted as a property of the repository.

**Investigation.** Seven mutations in modules that had **never** been mutation-tested. Three
survived: `policy.py` reporting PASS when a requirement FAILS, `Evidence.strength()` returning
`MEASURED` on an empty claim set, and knowledge-graph provenance precedence inverted.

**Decision.** Publish the number in the README under **"Known not to hold"** rather than quietly
scoping the claim.

**Outcome.** Survival is 0% inside the tested zone and 43% outside it. Both numbers are in the
README.

**Lesson.** Evidence accumulates where work happens, so the measured region is exactly the region
least likely to be broken. That is survivorship bias in the evidence itself.


---

## 11. Pricing ten cycles of recommendations for a team that does not exist

**Situation.** A backlog of architecturally correct recommendations.

**Investigation.** Every one had been implicitly costed for a twenty-engineer platform. There is one
maintainer, so onboarding improvement and parallel-work enablement are worth approximately zero, and
those were the primary justifications. Measured: the package-namespace refactor I had ranked
**first** and called *"mechanical, low risk"* touches **60 of 89 modules** with a 100% blast radius.

**Decision.** Reject four of my own recommendations. Substitute a six-line duplicate-basename test
that buys most of the safety for a fortieth of the cost.

**Lesson.** "Architecturally correct" and "worth doing" are different questions, and the second one
depends on facts about the team, not the code.


---

## 12. Measuring the thing I had been asserting

**Situation.** Three reviews had described the architecture work as simplification.

**Investigation.** Total LOC 3,644 → 3,940. Cyclomatic 1,207 → 1,252. Public API 78 → 83.
**It got bigger.** What improved was ownership: decisions with **no owner went 4 to 0**, decisions
with exactly one owner went 3 to 6.

**Decision.** Publish both numbers and retract the simplification claim.

**Lesson.** My first two attempts at this metric were also wrong, one counting docstring prose as
code and one counting references as ownership. Only definition-site analysis meant anything.


---

## 13. Proving the ownership rules did not survive a second transport

**Situation.** Structural tests enforced that the transport holds no session policy. 15 of 15 drift
patches caught.

**Investigation.** I wrote a hypothetical second transport reintroducing the session map, the id
filter, direct conversation creation, a registry bypass and a TTL decision. It tripped **one**
assertion, and that one by accident. Every rule named `joi.py`, and the next milestone is a second
transport.

**Decision.** Generalise the rules to name the *owner* rather than the file. Three assertions now
catch it. Register the remaining gap as TD-070 rather than claim it closed.

**Lesson.** Enforcement scoped to the file where the problem happened expires exactly when it is
needed.


---

## 15. Typed provenance, and proving it was real

**Situation.** Every claim carries `MEASURED`, `INFERRED`, `ASSUMED` or `UNKNOWN`.

**Problem.** That is easy to write in a README and hard to prove is enforced.

**Investigation.** Four mutations designed to remove the invariants: allow an `UNKNOWN` to carry a
value, allow an `INFERRED` with no derivation, allow a value with no source, and make strength
return the strongest claim rather than the weakest. **All four were caught.**

**Outcome.** The claim survives an attack designed to remove it, which is the only reason it belongs
in the README.

**Lesson.** The difference between a design principle and a decoration is whether removing it breaks
a test.


---

---

Next: [Architecture decision records](adr/), the decisions behind the platform. · [Package index](../README.md)
