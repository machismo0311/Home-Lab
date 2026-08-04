# Limitations

What this tool does not do. Read this before trusting a green result.

## Required human review

Because the gate cannot decide what *should* be public, a green result is necessary and not
sufficient. Every candidate is additionally read by a person against this checklist. It is
deliberately a checklist and not another validator: the judgement it requires is exactly the
judgement pattern matching cannot perform.

> Review every candidate for current weaknesses, active security gaps, live operational status,
> credentials, owner actions, and sensitive architectural implications that pattern matching
> cannot understand.

This exists because it caught something. A certification document scored **zero estate
identifiers** and was nonetheless withdrawn from publication: it contained a live status table
naming an unrotated credential and the file holding it, alongside untested restores and degraded
redundancy. No pattern in this tool would have found it, because nothing in it matches a pattern.

## It cannot decide what should be public

The gate answers "is this safe and complete enough to publish." It has no opinion on whether a
document *ought* to be published. A perfectly sanitised incident report describing an unremediated
weakness will pass every check and still be a bad thing to publish. That judgement is the human
approval step, and the gate deliberately does not try to automate it.

## Denylists are incomplete by construction

The content checks catch shapes that were anticipated. An identifier in a shape nobody thought of
passes. This is why the allowlist exists: the primary control is that only approved files are
exported at all, and the pattern checks are a second line, not the first.

Concretely, the gate does not currently detect: identifiers encoded in base64 or hex, addresses
written in words, hostnames embedded inside longer tokens, identifiers inside binary files, or
anything inside an image.

## Known gaps

| Gap | Consequence | Status |
|---|---|---|
| Image metadata is not parsed | EXIF, including GPS, is not inspected. K11 covers the requirement in principle but no EXIF reader is wired in | **Open.** Strip metadata before adding images |
| Binary files are skipped entirely | Anything not decodable as UTF-8 is excluded from content checks | Accepted. Binaries should be reviewed by hand |
| External links are not fetched | A broken `https://` link is not detected | Accepted, deliberately: fetching would break determinism and the no-network property |
| Secret detection is shape-based only | A credential that does not match a known shape is not found | Accepted. Pair with a dedicated secret scanner in CI |
| Anchors are not resolved | A link to `page.md#missing-heading` passes if `page.md` exists | **Open.** Low severity |
| No entropy analysis | High-entropy strings are not flagged as probable secrets | Accepted. Produces false positives on hashes and test fixtures |
| Licence check is shallow | K15 looks for a recognisable marker string, not a licence. A two-line stub beginning with a known licence name passes as valid | **Open.** Found when this package's own placeholder LICENSE passed the check. Not fixed: narrowing it risks rejecting legitimate variants, so it is recorded rather than patched |

## It verifies a tree, not a repository

The gate inspects a directory. It does not read git history, so a file removed from the working
tree but present in a previous commit is invisible to it. **Removal from a tree is not removal from
history.** If an identifier was ever committed to a public repository, treat it as disclosed and
rotate it rather than trusting a later deletion.

## Running it against its own source is a category error

This tool's test corpus deliberately contains examples of the patterns it rejects, so pointing the
gate at its own repository reports failures by design. Those findings are the fixtures, not
defects.

The safety property that does apply to this repository is narrower and was verified separately: it
contains no *real* estate identifier, checked by scanning the package with a private patterns file
containing the genuine vocabulary. That scan returns zero.

## The patterns file is a single point of failure

If the patterns file is wrong, incomplete, or stale, the hostname, domain, address and repository
checks are correspondingly wrong. The gate fails closed when the file is absent, which covers the
obvious mistake, but it cannot detect a file that is present and *insufficient*. Keeping it current
is a human responsibility with no mechanical backstop.
