# NetFRAME engineering documentation

Part of the NetFRAME repository; see `README.md` at the repository root.

**A platform built so that it cannot quietly lie about its own state.**

This is the public engineering record of NetFRAME: the decisions, the governance, the testing
method, and six things that went wrong and what they cost. It is a selection, not an export.

## Why it exists

Operational tooling is confident. It reports green when it has no data, averages away the one
measurement that mattered, and answers questions it has no basis to answer. **Every one of those
failures looks exactly like success**, which is why they survive so long.

NetFRAME is built the other way round. Evidence carries its own provenance, `UNKNOWN` is a valid
answer, rules are enforced by something executable rather than written in a document, and nothing
reaches production or publication without a human deciding it should.

## Engineering philosophy

Five positions, each of which costs something. They are held because of what they cost.

| Position | What it costs |
|---|---|
| **Evidence before conclusions.** A status string is never evidence | Slower answers, and sometimes no answer |
| **`UNKNOWN` is a valid answer.** Never guess where evidence is missing | Reports that look less complete than a system that guesses |
| **Enforcement, not intention.** A rule without an executable witness is a wish | Every rule needs a mechanism, so fewer rules exist |
| **Read-only by default.** Higher-risk actions have no handler to call | The platform cannot fix anything by itself, by design |
| **Publish the number that hurts.** Report the failure rate, not the flattering one | The mutation figures below include the bad one |

## Five-minute tour

Read these three, in this order. It is enough to judge the engineering.

1. **[Capability map](docs/capabilities.md)** · what the platform does, grouped by capability, with the evidence for each claim. *Two minutes.*
2. **[Architecture](docs/architecture.md)** · four diagrams, each explaining a decision rather than depicting a system. *Two minutes.*
3. **[Engineering stories](docs/engineering-stories.md)** · six things that happened. Four are defects found in my own work. *One minute for the first two.*

If you read nothing else, read story 8. It publishes a mutation survival rate of **0% inside the
tested zone and 43% outside it**, and explains why quoting only the first number would have been
dishonest.

## What is here

| Document | What it answers |
|---|---|
| [Capability map](docs/capabilities.md) | What does it do, and what is deliberately absent |
| [Architecture](docs/architecture.md) | How is it put together, and which decision produced each boundary |
| [Engineering stories](docs/engineering-stories.md) | What went wrong, and what changed as a result |
| [Architecture decision records](docs/adr/) | Six of sixteen decisions, with rejected alternatives and falsification criteria |
| [Governance model](docs/governance.md) | How does a written rule become executable |
| [Governance compiler](docs/governance-compiler.md) | What checks that the rules are actually enforced |
| [Release process](docs/release-process.md) | How a change moves from proposal to closure |
| [Mutation testing](docs/mutation-testing.md) | How the tests are tested |
| [Glossary](docs/glossary.md) | What the terms mean. Read this if a document loses you |

## The publication gate

This package is not published by hand. A fail-closed verifier runs 24 checks over the candidate
tree and refuses on any failure: secrets, addressing, hostnames, internal domains, identity, paths,
hardware identifiers, private references, unresolved placeholders, broken links, missing licence or
release notes, and reproducibility. A check that cannot run **fails**, and a check that returns no
verdict fails the whole gate, because a gate that passes because it crashed is the failure mode it
exists to prevent.

It is proven by a 34-mutation campaign in which each mutation must be caught by its *expected*
check, guarded by a control requiring the unmutated baseline to pass.

The gate cannot decide what *should* be public, only whether something is safe and complete enough
to be. That judgement stays with a person, and it has already withdrawn a document from this
package: one scoring zero estate identifiers was pulled for naming an unrotated credential.

## Where to continue

- **Judging the engineering?** [The ADRs](docs/adr/) are the densest evidence, particularly
  [ADR-026](docs/adr/ADR-026-kernel-owns-admission.md), which derives a limit from measurement
  rather than choosing a round number.
- **Judging the judgement?** [Engineering stories](docs/engineering-stories.md).
- **Judging the rigour?** [Mutation testing](docs/mutation-testing.md), then
  [the governance compiler](docs/governance-compiler.md).
- **Lost in vocabulary?** [Glossary](docs/glossary.md).

## What is not here

Estate specifics: addressing, topology, host identity, operational runbooks, incident records, and
registers of current risk. Those are withheld deliberately, and deciding what to withhold is part
of the engineering rather than an afterthought.

Some documents are also withheld because publishing them while their subject is still live would be
imprudent regardless of redaction. That distinction, between what can be sanitised and what should
simply wait, is the one a pattern matcher cannot make.

---

*Documents reused from the private engineering corpus are byte-identical to their sources. Where
they carry a navigation line, it sits above the document rather than inside it, so the reused text
remains provably unmodified while a reader still has a way onward.*

<!--
  Public edition. Framing only: this document explains the package and does not
  restate it. Authored for publication; no private source existed.
  Sanitization: none required.
-->
