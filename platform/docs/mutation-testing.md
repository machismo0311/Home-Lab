<!--
  Public edition. Authored for publication; no single private source document existed.
  Assembled from: the publication gate's mutation campaign, and two engineering stories
  recording mutation results against the platform's admission and provenance layers.
  Sanitization: none required. All figures are from synthetic mutations against code,
  not from estate measurement.
-->

# Mutation testing, as practised here

Coverage says a line ran. It does not say an assertion would have noticed if that line were
wrong. Mutation testing closes the difference: change the code so it is deliberately incorrect,
and require a test to fail. A mutation that survives is a hole in the suite, located precisely.

This is not a framework. It is a habit with four rules.

## The four rules

**1. Assert the expected check catches it, not merely that something failed.**

A mutation that fails the suite for the wrong reason is not evidence. If a seeded address is
caught by a link checker rather than by the address check, the address check is still unproven and
the campaign has lied. Every mutation therefore declares which check must catch it, and catching by
any other check is recorded as a miss.

This is the same defect class as a test that asserts the right thing about the wrong input, which
is a failure mode with no symptom: the test passes, coverage is green, and the assertion never
touched the case that mattered.

**2. Guard the campaign with a passing baseline.**

If the unmutated baseline does not pass, every mutation "fails" trivially and the campaign proves
nothing while reporting complete success. The baseline is therefore a control case, and its failure
fails the campaign.

**3. An escape is a campaign failure, not a statistic.**

A surviving mutation is not a score to be improved next quarter. It is a specific, located hole,
and the campaign is red until it is closed or explicitly accepted with a reason.

**4. Publish the number from outside the tested zone.**

This is the rule that costs something, and it is the only one that produces honest evidence.

## Why the second number matters more

A campaign was run across an admission layer: thirty-three mutations, all caught. That number was
then quoted as a property of the codebase.

Extending the campaign to seven mutations in modules that had **never** been mutation-tested,
three survived. One allowed a policy component to report a pass when a requirement failed. One
allowed an evidence value to be reported as measured when the claim set was empty. One inverted a
provenance precedence rule.

The survival rate is **0% inside the tested zone and 43% outside it**, and both numbers are
published together because only the pair is honest.

The lesson generalises beyond this codebase. Evidence accumulates where work happens, so the
region with the most testing is the region least likely to be broken, and a number drawn from it
describes the attention rather than the code. **That is survivorship bias in the evidence itself.**
Any single mutation figure quoted without its scope should be read as a claim about where someone
has been looking.

## Mutations as proof that a principle is enforced

A design principle written in a README costs nothing and proves nothing. The test is whether
removing it breaks something.

Four mutations were written against a typed-provenance invariant, each designed to remove it: allow
an `UNKNOWN` claim to carry a value, allow an `INFERRED` claim with no derivation, allow a value
with no source, and make the strength calculation return the strongest claim rather than the
weakest. All four were caught.

That result is why the claim appears in documentation at all. The difference between a design
principle and a decoration is whether removing it breaks a test.

## The current campaign

The publication gate is verified this way. Thirty-four mutations, each seeding exactly one defect
into a clean baseline tree, each asserted against its expected check, with a passing-baseline
control and any escape failing the campaign.

The gate's own result is 34 of 34 caught with zero escapes. Applying rule 4 honestly: that figure
describes the gate's checks, which is the region under test. It says nothing about code the
campaign does not reach, and it should not be read as if it did.

## What this does not give you

Mutation testing proves a suite notices a specific class of wrongness. It does not prove
correctness, it does not find defects the mutations were never written to simulate, and a high
catch rate on a small mutation set is weaker evidence than a lower rate on a broad one. The count
is meaningless without knowing what was mutated and where.

---

Next: [Governance compiler](governance-compiler.md), what checks the rules are enforced. · [Package index](../README.md)
