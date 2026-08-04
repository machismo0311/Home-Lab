# Changelog

## 1.0.0

First public release.

- 24 substantive checks plus the K99 no-silent-pass meta-check.
- Fail-closed semantics: a raising check is `ERROR`, a missing input is a refusal, and no
  evidence manifest is written on failure.
- Estate vocabulary externalised to a patterns file so the tool does not carry a target list.
- 34-mutation campaign, each mutation asserted against its expected check, with a passing
  baseline control.
- 35 unit assertions covering fail-closed and determinism properties.
- MIT licensed, consistent with the other NetFRAME repositories.
