<!--
  Public edition. Reused verbatim from the private engineering corpus except where noted.
  Source: jarvis/ecm/ARCHITECTURE.md
  Sanitization: example record labels OA-BREAKGLASS and OA-PAT genericized
  Referenced implementation files are named for provenance; they are not part of this
  public edition.
-->

> [Package index](../README.md) · Next: [Architecture decision records](adr/), the decisions behind the platform.

---

# Jarvis Engineering Change Management (ECM) - Architecture

A technical engineering governance layer (not Jira, not ITIL) between EOS and Continuous Assurance.
Every EOS recommendation automatically becomes a Change Record that must traverse a strict lifecycle
before becoming reality. Read-only: ECM never executes; it emits an execution PLAN for a human.
Working code `ecm.py`; demonstrated in `sample-change-report.md`; 20/20 acceptance in `test_ecm.py`.

## Stack position
Engineering Memory -> EOS (reasoning + prioritization) -> **ECM (this layer)** -> Continuous
Assurance (verification) -> Chief Engineer (reviews).

## Single source of truth / no duplicated logic
- Change Records are DERIVED from EOS recommendations; ECM reuses their value score, citations,
  affected systems, and rollback. It does NOT re-score value.
- Dependencies reuse the EOS DependencyEngine.
- Verification calls the existing Continuous Assurance engine (no second verifier).
- ECM adds exactly two new things: a distinct CHANGE-RISK model and the lifecycle state machine.

## State machine (canonical UPPER_SNAKE, no skipping, no shortcuts)
Linear happy path:
```
PROPOSED -> EVIDENCE_COMPLETE -> RISK_ASSESSED -> DEPENDENCIES_VERIFIED -> APPROVAL_PENDING
  -> APPROVED -> SCHEDULED -> EXECUTING -> VERIFICATION_PENDING -> ASSURANCE_PENDING
  -> CHIEF_REVIEW_PENDING -> CLOSED
```
Six alternate/terminal states and where they are reachable from:
```
REJECTED            <- PROPOSED, APPROVAL_PENDING          (terminal)
REDESIGN_REQUIRED   <- APPROVAL_PENDING                    (terminal)
BLOCKED             <- RISK_ASSESSED, DEPENDENCIES_VERIFIED, SCHEDULED  (recoverable)
FAILED              <- EXECUTING, VERIFICATION_PENDING      (terminal)
ROLLED_BACK         <- EXECUTING, VERIFICATION_PENDING, ASSURANCE_PENDING (terminal)
EXCEPTION_OPEN      <- VERIFICATION_PENDING, ASSURANCE_PENDING -> CHIEF_REVIEW_PENDING
```
Legal transitions are the ONLY entries in the `ADJ` adjacency table; `allowed()` permits only those
and refuses any skip, any move out of a terminal state, and any undefined pair (no silent coercion).
`guard()` enforces per-transition preconditions. Read-only reality: ECM auto-advances every change to
**APPROVAL_PENDING** and STOPS; APPROVED onward requires an explicit human approval token, so all
current changes wait at APPROVAL_PENDING.

## Guards (the guarantees, enforced in code)
| Transition (target) | Guard |
|---|---|
| EVIDENCE_COMPLETE | citations + linked recommendation exist (else fail closed) |
| DEPENDENCIES_VERIFIED | risk scored AND dependencies resolvable |
| BLOCKED | only when a real prerequisite/dependency is unsatisfied |
| APPROVED | explicit approval token OR justified emergency override |
| REJECTED / REDESIGN_REQUIRED | an explicit approval-engine decision |
| SCHEDULED | a maintenance window is set |
| EXECUTING | all prerequisites are CLOSED (dependencies block execution) |
| VERIFICATION_PENDING | an execution package exists |
| ASSURANCE_PENDING | verification == PASS |
| EXCEPTION_OPEN | full exception: reason + operator + timestamp + evidence + rollback + expiration |
| FAILED | an explicit failure signal |
| ROLLED_BACK | a reproducible (non-GAP) rollback plan |
| CHIEF_REVIEW_PENDING | assurance PASS OR an open approved exception |
| CLOSED | chief verdict recorded AND change was verified |

## Enhanced-contract additions
- **Malformed input fails closed:** `ChangeRecord.from_recommendation()` parks any record with a
  missing id/citations or an id absent from Memory in `FAILED`; malformed records are excluded from the
  active ledger (never silently coerced into a valid state).
- **Emergency expiration:** an emergency override is rejected unless it carries reason, operator,
  timestamp, evidence, rollback, AND an expiration.
- **Deterministic rebuild:** `rebuild()` re-projects every change record from committed source at its
  read-only auto-flow state; `ledger_hash()` is stable across managers (proven by test).
- **No uncited claims:** `uncited_claims()` gates the chief summary so every factual line carries an
  evidence locator.
- **Example records** in `examples/` demonstrate five materially different paths: normal->CLOSED (P1),
  BLOCKED (P2), emergency/EXCEPTION_OPEN (OA-EXAMPLE-A), REJECTED (OA-EXAMPLE-B), malformed->FAILED.

## Change Record (data model)
Every field the mission requires: id, title, description, origin, reason, linked
recommendations/risks/incidents/invariants, affected systems, architecture/operational/security impact
(via risk axes), rollback plan, estimated time, maintenance window, required approvals, implementation
steps, verification steps, acceptance criteria, evidence before/after, continuous-assurance result,
chief verdict, lessons, git commit references, documentation-updated, owner, status, and an append-only
transition history for forensic review.

## Change-risk engine (deterministic, explains WHY)
Ten axes - reliability, availability, blast radius, security, rollback complexity, dependencies,
maintenance window, human error, customer impact, recovery time - each scored 1-3 from the record and
summed to LOW / MEDIUM / HIGH / CRITICAL. Never a bare label: every score reports its top contributing
axes. Deterministic (pure function; verified by test). Example: CHG-P1 = LOW (11) - wall-only blast
radius, fast tested rollback, no dependencies; the WHY names reliability, blast_radius, availability.

## Approval, execution, verification
- ApprovalEngine actions: review / approve / reject / needs-evidence / needs-redesign /
  emergency-override. Emergency override REQUIRES reason + timestamp + evidence + operator + rollback,
  else it is rejected.
- ExecutionPlanner emits step-by-step steps, expected outputs, verification commands, rollback
  commands, duration, success + abort criteria, and recovery. Missing detail is a labelled GAP. It does
  not execute.
- Verifier runs Continuous Assurance, compares expected vs actual, returns PASS / FAIL / UNKNOWN. FAIL
  blocks Close and forces Rollback or exception approval.

## Metrics + executive reporting
KPIs: lead/approval/execution/verification time, rollback rate, failure rate, verification success,
evidence completeness, average risk, high-risk count, emergency count, waiting-approval,
waiting-verification. The weekly Chief-Engineer report gives risk distribution, failed/rolled-back
changes, top blocked initiatives, and evidence completeness - all read-only.

## Safety
Read-only; no production/config change. The only writes are the generated report and (optionally) a
change-ledger snapshot, neither a source of truth. Acceptance `test_ecm.py` 20/20. All lower layers
continue to validate.
