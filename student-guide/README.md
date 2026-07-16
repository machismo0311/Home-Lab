# QuarkyLab User Guides (LaTeX)

Professional, step-by-step onboarding guides for the QuarkyLab GPU cluster.
Remote access is via **Cloudflare Tunnel** (`quarkylab.kylemason.org`) + per-account
SSH keys — there is **no VPN**; students and researchers install `cloudflared` and
SSH through the tunnel. (Headscale is the internal admin mesh only and does not
appear in these guides.)

## Files
| File | Audience | Purpose |
|---|---|---|
| `QuarkyLab-Student-Guide.tex` / `.pdf` | Students (`studentNN`) | Zero-assumed-knowledge walkthrough: SSH key → cloudflared → first SLURM GPU job |
| `QuarkyLab-Researcher-Guide.tex` / `.md` / `.pdf` | Researchers | Access + direct GPU/Apptainer workflow (no SLURM required) |
| `README.md` | Admin | This file |

Companion admin runbooks (vault): `Runbook/QuarkyLab-Cloudflare-Access.md` (tunnel),
`Runbook/QuarkyLab-Account-Onboarding.md` (key onboarding), `Runbook/QuarkyLab-Student-Quickstart.md`
(short on-box version at `/data/shared/QUICKSTART.md`).

## Build
```bash
latexmk -pdf QuarkyLab-Student-Guide.tex      # TeX Live (installed on Ares)
latexmk -pdf QuarkyLab-Researcher-Guide.tex
```
[Tectonic](https://tectonic-typesetting.github.io/) or [Overleaf](https://overleaf.com) also work.
**Recompile the PDF whenever the `.tex` changes — the committed PDFs are what get distributed.**

## Editing — the CONFIGURATION block
All site-specific values are `\newcommand`s at the top of each `.tex` (the
`CONFIGURATION` block). Change a value once, recompile, and it updates everywhere.
Key variables (student guide):

| Macro | Meaning | Current value |
|---|---|---|
| `\LabName` | Cluster display name | `QuarkyLab` |
| `\LabHost` | SSH alias users define in `~/.ssh/config` | `quarkylab` |
| `\AccessHost` | Cloudflare tunnel hostname | `quarkylab.kylemason.org` |
| `\ContactVia` | Where users send keys / get help | our shared Discord channel |
| `\GPUName`, `\ShardMem`, `\MaxTime`, `\HomeQuota`, `\ScratchPurge` | Limits shown in tables | — |

## Onboarding flow (admin side)
1. Student/researcher sends their **public** key on Discord.
2. On QuarkyLab (as root): `add-cluster-key.sh studentNN "<pubkey>"`
   (named researcher accounts like `kieron` need the key added manually — the helper
   only accepts `student##`/`researcher##`).
3. Tell them their username. They follow the guide; no further admin steps.

## Verified working
The student guide's exact flow (key → `add-cluster-key.sh` → tunnel SSH → `scp` →
the example `train.py`/`train.sh` sbatch job) was dry-run end-to-end 2026-07-15:
job COMPLETED, `GPU: Quadro RTX 8000 / CUDA available: True`.

## Known limitation (deliberate)
**VS Code Remote-SSH does not work for students/researchers** — the group sshd
policy sets `AllowTcpForwarding no` (see `Runbook/QuarkyLab-Account-Onboarding.md`).
Per-user exemptions are possible (precedent: `kieron`, `40-kieron-vscode.conf`);
grant case-by-case, never group-wide, and the guides tell users editing happens
on the cluster (nano) or via `scp`/`rsync`.
