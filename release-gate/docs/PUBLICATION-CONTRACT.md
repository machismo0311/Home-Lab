# The publication contract

Two scopes, one trust boundary. This document is the authority on which checks run where, and
why. If the tooling and this document ever disagree, the tooling is wrong.

## Why there are two scopes

A repository and the content published from it are different objects with different questions.

"Does this repository carry a licence?" is answered by looking at the repository. It needs no
private information, so it can run anywhere, including public CI.

"Does this document contain an estate hostname?" cannot be answered without knowing what the
estate's hostnames are. That knowledge is exactly what must never be published, so the check that
needs it cannot run in a public place.

Collapsing these into one scope forces a choice between a check that runs everywhere and proves
little, or a check that proves a lot and cannot run. Separating them lets each be honest.

## The trust boundary

```
        PUBLIC SIDE                    |            PRIVATE SIDE
                                       |
  repository-envelope scope            |   publication-content scope
  runs in CI on every change           |   runs locally, before publication
                                       |
  needs: the repository                |   needs: the operator's estate vocabulary
  knows: nothing private               |   knows: hostnames, domains, addresses
                                       |
  proves: the repository is            |   proves: the content is safe to publish
          structurally complete        |
                                       |
  failure blocks: the build            |   failure blocks: publication
                                       |
  ------------------------------------ | ------------------------------------
                                       |
        the boundary is the estate vocabulary. It never crosses.
```

**The rule in one line: nothing that requires the estate vocabulary may run where the estate
vocabulary cannot go.**

Two consequences follow, and both are accepted deliberately.

Public CI cannot prove content safety. It is not trying to. A green CI badge on this repository
means the repository is structurally sound and the gate itself still works. It does **not** mean
the content has been cleared for publication, and it must never be read that way.

The strongest assurance is produced on a machine that holds private information, by a person. That
is not a weakness in the design; it is where the knowledge is.

## Scope 1: repository envelope

**Runs:** in public CI, on every change to the published paths.
**Requires:** nothing private.
**Blocks:** the build.

| Check | Verifies |
|---|---|
| K14 | Required files present: LICENSE, CHANGELOG, SECURITY, README |
| K15 | The licence is present and recognisable |
| K16 | The README opens with a heading, is substantial, has balanced fences and well-formed links |
| K20 | Release notes exist and contain a released version entry |
| K22 | Repository metadata is complete: description, topics, homepage, licence |
| K99 | Every registered check reported a verdict |

Every other check is reported `N/A` with the reason that it is a publication-content requirement
owned by the published subtrees rather than by the repository.

```bash
verify-publication --tree . --scope envelope --metadata <metadata.json>
```

## Scope 2: publication content

**Runs:** locally, on the operator's machine, before publication.
**Requires:** the operator's untracked estate-patterns file.
**Blocks:** publication.

Covers secrets, addressing, hostnames, internal domains, personal identity, filesystem paths,
hardware identifiers, private-repository references, internal branch references, unresolved
placeholders, applied substitution, manifest integrity, allowlist coverage, links, images, declared
diagrams, documentation consistency, and reproducibility.

```bash
verify-publication --tree . --scope content \
  --include platform \
  --manifest <manifest> --metadata <metadata.json> \
  --patterns <untracked estate-patterns.json> \
  --diagram-contract <diagrams.json>
```

**The patterns file is never committed.** Not the real one, and not an example either: a committed
example is a template for the real one and invites someone to fill it in and commit that. The
format is documented below; the file is created by the operator and stays untracked.

```json
{
  "hostnames":      ["..."],
  "domains":        ["..."],
  "addresses":      ["..."],
  "private_repos":  ["..."],
  "role_map":       {"<hostname>": "<ROLE-NAME>"}
}
```

If no patterns file is supplied, the hostname, domain, private-repository and substitution checks
**fail**. They do not skip. A check that cannot run is a failed check.

### Curating the patterns file

**List what is internal, not what is merely yours.** A domain entry matches both the apex and every
subdomain, so declaring a public apex domain will flag legitimate public references to it, including
the repository's own homepage metadata. Declare the internal names: the private DNS zone, and any
specific subdomain that resolves to a private address. Leave a public site out.

This distinction was found by running the content scope with a test vocabulary that listed a public
apex domain. The check was right and the vocabulary was wrong. The tool cannot make this judgement,
because "internal" is a fact about the estate rather than about the string.

## What is excluded from content scanning, and why

**`release-gate/` is not content-scanned.**

This is not an exemption granted for convenience. A denylist gate necessarily contains the things
it denies: the policy holds the patterns it rejects, the mutation campaign seeds artifacts that
look exactly like violations, and the tests assert on strings that must match. Scanning it reports
its fixtures as findings, every time, by construction. Running a check whose failure is guaranteed
and then ignoring the result is the decoration this project exists to avoid.

Its correctness is established by evidence that actually bears on it:

- the **mutation campaign**, in which every seeded defect must be caught by its *expected* check,
  guarded by a control requiring the unmutated baseline to pass;
- the **unit suite**, covering fail-closed behaviour, the scope contract, determinism, and the one
  false positive this tool produced in development;
- **verification by the gate itself** of everything it publishes, which is the property that
  matters: the tool is trusted because its output is checked, not because it passes a scan of its
  own test data.

The exclusion is expressed by invocation, `--include platform`, so the excluded tree is never read
rather than read and then discarded.

## The operator publication sequence

Publication is a five-step sequence. It is not complete until step 5, and steps do not reorder.

1. **Update the private estate-patterns file.** Any host, domain or address added to the estate
   since the last publication is added here first. A stale patterns file silently weakens every
   content check.
2. **Run the publication-content scan locally**, with that patterns file.
3. **Review the results.** Every finding is read, not counted. Alongside the mechanical result,
   perform the manual semantic review: current weaknesses, active security gaps, live operational
   status, credentials, owner actions, and architectural implications that pattern matching cannot
   understand.
4. **Obtain owner approval.** The gate decides whether content is *safe and complete*. Only a
   person decides whether it *should* be published.
5. **Publish.**

**Publishing without a successful local content scan violates this process.** There is no
mechanical control preventing it, because the publishing action is a human one. That is precisely
why it is written down here: the control is the sequence, and a sequence nobody has written cannot
be followed or audited.

A green CI badge does not satisfy step 2. CI runs the repository-envelope scope only.

## What this contract does not cover

The gate verifies a tree, not a repository history. Content removed from a tree remains in git
history, so an identifier that was ever committed publicly must be treated as disclosed and
rotated, never as deleted.

It also cannot judge whether a document *should* be public. That judgement is step 3, and it has
already withdrawn a document that scored zero estate identifiers.
