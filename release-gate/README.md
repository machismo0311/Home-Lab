# Publication Gate

A fail-closed verifier that decides whether a directory tree is safe and complete to publish.

It exists because publishing from a private repository is a decision made under time pressure,
usually by one person, usually late. Reviewing a diff by eye finds typos. It does not reliably find
the one address in the one fixture in the one directory nobody opened.

## Its first production run refused my own publication

![The publication gate refusing its author's publication: 19 files in scope, K17 failing on two links that escape the publication tree](docs/first-refusal.png)

This is the real output of the first time this tool was run for its actual purpose: publishing the
platform package that now sits alongside it in this repository. It refused.

`K17` was correct. Both links resolve when the file is read from the repository root and are
unresolvable inside the publication tree, so a reader treating the package as a self-contained unit
would have hit dead navigation. The migration stopped there. Nothing was committed until the links
were rewritten as inline code paths, which changed no check and weakened no rule.

Before that run, every claim on this page was a claim that the control worked. That refusal is the
first evidence, and the more useful half of it is that the author was the one refused.

The image above is reproduced with a fictional patterns file, so the vocabulary shown is not the
estate's. The verdicts, findings and counts are the ones the real run produced.

## What it checks

Twenty-four substantive checks, plus one meta-check.

| Group | Checks |
|---|---|
| Content safety | secrets and credentials, IP addresses, estate hostnames, internal domains, personal identity and SSH targets, absolute local paths, hardware identifiers |
| Publication hygiene | private-repository references, internal branch and PR references, unresolved placeholders and work markers, applied substitution |
| Completeness | required files, licence recognition, README rendering, relative links, image availability, required diagrams, release notes, repository metadata |
| Integrity | file readability, manifest integrity, allowlist coverage, documentation consistency, reproducibility |
| Meta | **K99**: every registered check reported a verdict |

K99 is the one that matters most. A gate that passes because it crashed before checking is the
failure mode this tool exists to prevent, so absence of a verdict is a failure, never a pass.

## Fail-closed, stated precisely

- A check that raises is recorded as `ERROR` and fails the gate. It is never skipped.
- A check that cannot run because its inputs are missing **fails**. Supplying no patterns file does
  not mean "skip the hostname check"; it means the gate cannot verify hostnames and therefore
  refuses.
- A missing manifest is a refusal. There is no default-allow path.
- No evidence manifest is written on failure, so a failed run cannot leave behind an artifact that
  resembles an approval.

Exit codes: `0` approved, `1` refused, `2` internal error, which is also a refusal.

## Why the estate vocabulary is not in this repository

A denylist gate necessarily contains the things it denies. Hardcoding a real estate's hostnames,
domains and addresses into the tool would mean **publishing the tool publishes the target list**.

So the shapes stay in the code, because an RFC1918 regex, a MAC regex and an email regex are
universal and disclose nothing, and the literals load from a patterns file that is not published.
The format is documented in [PUBLICATION-CONTRACT.md](docs/PUBLICATION-CONTRACT.md) and the file
is created by the operator, never committed. Not even an example is committed: an example is a
template for the real one and invites someone to fill it in and commit that. The mutation campaign
generates its own fictional vocabulary in code, so it proves the mechanism without ever handling a
real identifier or shipping a file that resembles one.

This was not the original design. The first version hardcoded the vocabulary and seeded the
mutations with real values, on the reasoning that a gate should be tested against real threats.
That reasoning was correct about testing and wrong about publication: it made the test suite the
single largest disclosure in the package. See [DESIGN.md](docs/DESIGN.md).

## How it is proven

Two suites, both runnable offline from a fresh clone.

```
$ scripts/verify-publication --self-test
  36/36 mutations caught by the expected check
  CAMPAIGN PASS

$ python3 tests/test_publication_gate.py
  46/46 assertions passed
```

**The mutation campaign** builds a clean baseline tree, applies exactly one defect, and asserts the
gate fails **and that the expected check caught it**. Asserting only "it failed" would let a
mutation pass for the wrong reason. Two control cases guard the campaign itself: the unmutated
baseline must pass, otherwise every mutation passes trivially, and a mutation that nothing catches
is an escape that fails the campaign.

**The unit suite** covers what the campaign cannot: that an exception inside a check becomes
`ERROR` rather than a skip, that a registered check returning no verdict fails the gate through
K99, that two runs produce identical verdicts, and that the one false positive this tool produced
during development stays fixed.

## Wiring it into CI

```yaml
- name: Publication gate
  run: |
    scripts/verify-publication \
      --tree ./out --manifest publication/publication-manifest.txt \
      --metadata publication/repo-metadata.json \
      --patterns publication/estate-patterns.json
```

A non-zero exit fails the job. The campaign and the unit suite also run in CI on every change to
this directory, from a workflow at the **repository root**, on the reasoning that a control
exercised only at release time is a control nobody knows is broken. The workflow lives at the root
rather than beside this code because GitHub activates workflows only from the repository root; a
workflow file nested here would be inert.

## Usage

```bash
# create your own patterns file; it is never committed. Format in docs/PUBLICATION-CONTRACT.md

scripts/verify-publication \
  --tree ./publication-candidate \
  --manifest publication/publication-manifest.txt \
  --metadata publication/repo-metadata.json \
  --patterns publication/estate-patterns.json \
  --emit-manifest published-manifest.json
```

The manifest is an allowlist: `source | destination | classification | approved_on`. A file with no
record is refused rather than skipped, and a record whose file is missing is a hard error.

## What this is not

Read [PUBLICATION-CONTRACT.md](docs/PUBLICATION-CONTRACT.md) first: it defines which checks run in
public CI and which run locally, and why the boundary is where it is.

It is not a general secret scanner, though it checks common credential shapes. It does not replace
human review; it makes human review the last step rather than the only one. It cannot know whether
a document *should* be public, only whether it is safe and complete enough to be.
[LIMITATIONS.md](docs/LIMITATIONS.md) is worth reading before trusting a green result.

## Layout

```
scripts/
  verify-publication            the executor; runs the policy, never extends it
  publication_policy.py         the policy. Single owner of what may be published
  publication_mutations.py      the mutation campaign
tests/
  test_publication_gate.py      fail-closed and determinism properties
docs/
  PUBLICATION-CONTRACT.md       the two scopes, the trust boundary, the operator sequence
  DESIGN.md                     why it is built this way
  LIMITATIONS.md                what it does not do
  first-refusal.png             the first production run, refused
```

CI for this directory is defined at the repository root, in
`.github/workflows/release-gate.yml`.

Licensed under the MIT Licence, consistent with the rest of the NetFRAME repositories.
