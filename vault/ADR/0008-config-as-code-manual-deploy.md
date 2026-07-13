# ADR-0008: Config-as-code with manual deployment

**Status:** Accepted · **Date:** 2026-07-12
**Tags:** #adr #decision #cicd #ops

## Context
The lab needed a repeatable, reviewable way to manage service and infrastructure configuration without giving up operator control. The spectrum runs from fully automated GitOps that deploys on every merge, through config-as-code with a manual apply step, to ad-hoc changes made directly on the boxes.

## Decision
Keep configuration and definitions in git with CI that lints and validates on push, but keep deployment to infrastructure a deliberate manual step over SSH, systemd, or the relevant API. No pipeline pushes changes to production automatically. Branch protection and pre-push hooks gate the repositories. See [[Runbook/CI-CD-2026-07-10]].

## Consequences
- Every change is reviewable and has history, and CI catches syntax and lint errors before they land.
- A human gate sits in front of every production change, which suits a single-operator lab and keeps the blast radius of a bad change small.
- The trade-off is that deployment is not one-click; it requires the operator to apply the change and verify it.

## Alternatives considered
- **Full GitOps and continuous deployment:** rejected for now. The automation blast radius and the operational overhead are not justified for a solo lab, and a bad auto-deploy could take out core infrastructure.
- **Ad-hoc changes on the hosts:** rejected. No history, no review, no reproducibility.
