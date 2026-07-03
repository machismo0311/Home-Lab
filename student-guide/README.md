# QuarkyLab Student User Guide (LaTeX)

Professional, step-by-step onboarding guide for students using the QuarkyLab GPU
cluster — from generating an SSH key and joining the Headscale VPN, through
submitting their first SLURM GPU job, plus a tools list and a SLURM/career primer.

## Files
| File | Purpose |
|---|---|
| `QuarkyLab-Student-Guide.tex` | Source (edit this) |
| `QuarkyLab-Student-Guide.pdf` | Compiled guide to hand to students |
| `README.md` | This file |

## Build
Recommended — [Tectonic](https://tectonic-typesetting.github.io/) (self-contained, no TeX install):
```bash
tectonic QuarkyLab-Student-Guide.tex
```
Or with a normal TeX Live install:
```bash
latexmk -pdf QuarkyLab-Student-Guide.tex
```
Or paste the `.tex` into [Overleaf](https://overleaf.com) and download the PDF.

## Editing — the CONFIGURATION block
All site-specific values are `\newcommand`s at the top of the `.tex` (the
`CONFIGURATION` block). Change a value once, recompile, and it updates everywhere
(prose, code examples, quick-reference card). Key variables:

| Macro | Meaning | Current value |
|---|---|---|
| `\LabName` | Cluster display name | `QuarkyLab` |
| `\LabHost` | SSH target over the VPN | `quarkylab` |
| `\HeadscaleURL` | Headscale login server | `https://headscale.kylemason.org` |
| `\AdminEmail` | Where students send their public key | `masonkr@gmail.com` |
| `\GPUName`, `\ShardMem`, `\MaxTime`, `\HomeQuota`, `\ScratchPurge` | Limits shown in tables | — |

## ⚠ Confirm before distributing to students
These were set to best-guess defaults — verify they match the live setup:
1. **`\HeadscaleURL`** — the public Headscale login-server URL students' Tailscale
   clients point at. (`headscale.kylemason.org` is assumed; the internal server is
   pve3 LXC 105 / `192.168.10.186`.)
2. **`\LabHost`** — QuarkyLab's address over Headscale: a MagicDNS name (assumed
   `quarkylab`) or its `100.64.0.x` overlay IP. **Note:** QuarkyLab is currently on
   commercial Tailscale; Headscale enrollment (Phase 2, with Fernanda's Mac) is
   pending, so confirm the name/IP once it's on Headscale.
3. **`\AdminEmail`** — the address students email their SSH public key to.
4. Onboarding still requires the admin to run `add-cluster-key.sh <studentNN> "<pubkey>"`
   on QuarkyLab after receiving each student's key.
