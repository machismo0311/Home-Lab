# 10 — CLAUDE.md Integrity Review (§3.5)

**File:** `Home-Lab/CLAUDE.md` — 171 lines / ~26 KB / ~6.7k est. tokens.
**Basis:** commit `65f3681`, 2026-07-22.

## Headline: CLAUDE.md is the *most current* document in the repo

Unusually for an audit, CLAUDE.md is **ahead of** the rest of the tree, not behind it. Every
one of Phase 1's `C-SUPERSEDED` clusters is **already correct in CLAUDE.md** and stale
*elsewhere*:

| Fact | CLAUDE.md | Rest of repo |
|---|---|---|
| Randy CPU | v3 / 24c/48t ✅ | `docs/`, update-logs still v4/28c |
| Grafana stack node | pve4 ✅ | README/topology/MOC still pve3 |
| Headscale node | pve5 ✅ | README/topology/ADR still pve3 |
| DS4246 `bulk` | 3× RAIDZ2 / 80T ✅ | topology/Proxmox Cluster still 58.2T |
| OPNsense | 25.1.12 (live) ✅ | README/topology/MOC say 25.7 |
| GPU assignment | RTX8000→QuarkyLab ✅ | one stale update-log snapshot |

**Implication for Phase 4:** the reconciliation PR should propagate **CLAUDE.md's values
outward** into README / `topology/` / `vault/` — do **not** edit CLAUDE.md down to match them.

## Internal integrity
- **No internal contradictions found.** Node/IP/service/VLAN/storage tables are self-consistent
  and agree with the 2026-07 AARs and runbooks.
- **No hard rule appears wrong or superseded** — the safety notes (QuarkyLab/Jarvis kernel pins,
  pve2/OPNsense read-only caution, PBS storage on `.10.187`, JBOD-reset re-runs, VLAN30
  dual-homing, DNS-HA) all match the runbook evidence.

## Proposed changes — **none to the file's content**
1. **No cuts / no corrections to `Home-Lab/CLAUDE.md`.** It is operational context and the
   reconciliation source of truth. (This also keeps it out of the doc PR — see next.)
2. **Note: `Home-Lab/CLAUDE.md` is gitignored** (`/CLAUDE.md` rule, OPSEC by design) — it is
   *not* a tracked file, so any change to it can't ride the normal Phase 4 doc PR. Left as-is.

## Out-of-repo observation (for Kyle, not this PR)
- The **dotfiles** `CLAUDE.md` (`/home/machismo/CLAUDE.md:56`) says *"homepage is LXC 104"* —
  **stale**; homepage is pve3 **LXC 106** since 2026-06-24. That file lives in the
  `machismo0311/dotfiles` repo, outside this audit's scope, but worth a one-line fix there.

## Promotion candidates (runbook → CLAUDE.md)
- None urgent. CLAUDE.md already absorbs the high-value gotchas. The only open reconcile it
  itself references (OPNsense "docs say 25.7") is captured in `AAR-2026-07-20…:163` and will be
  closed by the Phase 4 PR propagating `25.1.12`.
