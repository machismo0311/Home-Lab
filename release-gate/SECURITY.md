# Security policy

Report a suspected issue privately through the address on the maintainer's profile rather than
opening a public issue.

## Scope and posture

This tool reads a directory and reports. It writes one file, the evidence manifest, and only on
success. It makes no network calls, reads no environment variables, and executes nothing from the
tree it inspects.

**A green result is not a guarantee.** It means the checks that ran found nothing. Read
[docs/LIMITATIONS.md](docs/LIMITATIONS.md) for what is not covered, including image metadata,
binary content, and anything already in git history.

The patterns file holds estate-specific vocabulary and is never committed. No example is
committed either: an example is a template for the real one. Its format is documented in
[docs/PUBLICATION-CONTRACT.md](docs/PUBLICATION-CONTRACT.md).
