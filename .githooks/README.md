# Git hooks

Tracked hooks for this repo. Enable them once per clone:

```bash
./scripts/install-hooks.sh      # sets core.hooksPath -> .githooks
```

## `pre-commit` — secret & recon scanner

Runs on every commit and **blocks** it if staged additions contain:

- private-key blocks, Anthropic/OpenAI/AWS/Slack/GitHub tokens
- the Dell default iDRAC password (`calvin`)
- known-leaked Dell service tags
- TLS/SSH fingerprints and MAC addresses
- hardcoded `password`/`secret`/`token` assignments
- home-city PII and known third-party identifiers

It scans **only staged additions**, not existing history. Placeholders are
allowed (`<...>`, `$VAR`, `XX:XX:XX:XX:XX:XX`, `AA:BB:CC:DD:EE:*`, `REDACTED`,
`see Vaultwarden`, `*.env.example`).

Bypass a false positive for a single commit:

```bash
git commit --no-verify
```

This is a lightweight, zero-dependency backstop — not a replacement for a full
scanner. For deeper coverage you can add [`gitleaks`](https://github.com/gitleaks/gitleaks)
or [`detect-secrets`](https://github.com/Yelp/detect-secrets) later.
