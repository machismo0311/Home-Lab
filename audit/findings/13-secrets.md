# 13 — Secrets & Hygiene

**Basis:** commit `65f3681`, full patch history (all branches, 304–314 commits).
**Result: CLEAN — no committed secrets, no rotation required.**

All candidate hits were inspected with credentials **masked** (H3); nothing below reproduces a
secret value.

## Method
1. Regex sweep of `git log --all -p` for private keys / `api_key|secret|password|token` /
   `sk-ant-` / AWS / Slack / GitHub-token patterns.
2. `gitleaks detect` (full history, `--redact`) — 304 commits, 1.83 MB scanned.

## Findings — all dismissed with evidence

| Source | Hit | Verdict |
|---|---|---|
| gitleaks | 5× `curl-auth-user` in `vault/Compute/Dell R730 - ML Node.md` (L97,98,130,156) | **FALSE POSITIVE** — structural check shows `-u root` (curl prompts for password, no literal) or `-u root:$IDRAC_PASSWORD` / `-u "$IDRAC_USER:$IDRAC_PASSWORD"` (**shell variables**, not literals). No credential is committed. |
| regex | `GF_SECURITY_ADMIN_PASSWORD=changeme` | Placeholder; the lines were **removed** in a later commit (`-` in diff). |
| regex | `Default password: calvin` | Dell factory default (public); corrected in-place to "rotate → Vaultwarden". |
| regex | `{{ vault_pbs_token_secret }}`, `PBSAPIToken={{ … }}` | Ansible **vault-templated** vars — no literal value. |
| regex | `sk-ant-[A-Za-z0-9_-]{8}`, `xox[baprs]-…`, `gh[pousr]_…` | These are the **detection regexes** inside the repo's own secret-scanner config, not secrets. |
| regex | `# token: username@pam!Token ID`, `# secret: secret` | Commented-out example placeholders. |
| regex | `DISCORD_TOKEN=` (empty), `os.environ.get("DISCORD_TOKEN","")` | Read-from-env; no literal token. |

## Hygiene note (not a leak)
- Several runbooks discuss `export RESTIC_PASSWORD='…'` leaving a backup password in the shell
  **environment/history** on the live host. That is an **operational hardening** observation the
  docs already raise — it is not a value committed to the repo. Track under the remediation
  backlog (Phase 4), not as a secret-exposure.

## Bottom line
No `BEGIN … PRIVATE KEY`, no live API keys, tokens, or password literals in any commit on any
branch. The repo is safe to keep public from a secrets standpoint. **No history rewrite or key
rotation is indicated.**
