# Case Study: Making an AI-Ops Assistant Trustworthy

**Date:** 2026-07-15
**System:** NetFRAME homelab - an LLM-assisted infrastructure operations platform ("Jarvis")
running local models against a 7-node Proxmox cluster.
**Summary:** A single engineering session that began as a small networking task and became a
deliberate program to make an AI operations assistant *trustworthy* rather than merely more
capable. This is the public, sanitized write-up; internal addressing, credentials, and
attack-surface specifics are omitted.

---

## The thesis

The whole program reduces to one principle:

> **The model proposes and phrases. Code decides what is allowed, how well-supported a
> recommendation is, and how much confidence it warrants. Everything is recorded.**

An LLM is genuinely useful for reading telemetry and writing a readable finding. It is not
trustworthy for deciding whether an action is safe, or for grading its own confidence. So
those jobs were moved out of the model and into deterministic, testable code.

---

## How one small task cascaded

The session started by publishing an internal web console behind a hostname. That required
DNS, and configuring DNS surfaced a latent gap that had quietly broken several services for
every client on the network. Fixing the gap restored access to the secrets manager, which
had itself stopped working for the same reason - a nasty dependency loop where the tool you
need to fix the problem is unreachable *because* of the problem.

A routine health check then revealed a service that looked healthy by every local signal
but was completely broken for its actual users: a process had been reconfigured to listen
only on loopback, so it answered fine locally while every other host got connection
refused. The service stayed "active," local probes returned 200, nothing alerted - and the
web UI that depended on it had been dead for a day.

That outage crystallized the real problem and set the agenda for everything that followed.

---

## The failure classes found

Each of these is a *category* of failure, not a one-off bug:

1. **Health is not correctness.** A service can be "active," answer locally, log nothing
   wrong, and still be entirely broken for its users. Monitoring that only checks local
   liveness is blind to this. **Fix:** probe every published service the way a real
   consumer reaches it - through the reverse proxy, over the real network path - never via
   localhost.

2. **"It changed" is not "it's wrong."** A drift detector that compares production to a
   *blessed snapshot of production* can only tell you something changed since you last
   approved it. It cannot tell you production disagrees with intent - and worse, it will
   happily bless a broken value as the new normal. **Fix:** conformance checking against
   *declared intent* held in version control, separate from change detection.

3. **The model graded its own homework.** The assistant was asked to state a confidence
   level for its own recommendations. A confident wrong recommendation is worse than an
   unsure one, and self-assessed confidence is exactly the thing an LLM is bad at. **Fix:**
   compute confidence deterministically from evidence provenance; the model only writes the
   wording.

4. **Evaluation enforced a safety rule that production did not.** A test harness blocked the
   assistant from recommending known-dangerous actions. Nothing on the live path did - so
   roughly one run in five, a dangerous recommendation reached the operator unscreened.
   **Fix:** a deterministic policy screen on the live path, made universal across every
   channel the assistant can speak through.

---

## The guardrails

Deterministic protections, each enforcing a boundary a model or a tired human could
otherwise cross silently. Every one is code, unit-tested, and reviewed in version control.

### A single policy engine
One shared implementation screens every LLM-generated recommendation before an operator
sees it. It blocks a fixed set of prohibited action classes - destructive storage
operations, power-cycling a fragile service, firewall/DNS mutations, destructive
virtualization actions, hardware replacement without evidence, and unauthorized
remediation. Design properties that took real iteration to get right:

- **Blocks are never silent.** The reader sees a visible notice naming the rule and the
  reason; the original wording is preserved in a tamper-evident audit log, not shown.
- **Negation is respected.** "Do *not* power-cycle this" is correct advice, not a violation
  - and getting that wrong (scanning a whole line for a negation word) briefly opened a
  bypass big enough to drive the exact prohibited action through. Fixed by scoping negation
  to the phrase it governs.
- **Evidence-gated where appropriate.** Replacing a genuinely failed drive is legitimate
  advice; replacing a healthy one off a benign sensor reading is the false positive the
  rule exists to catch. The gate is deterministic, never the model's opinion.
- **Universal.** The same engine covers every report the assistant writes *and* the
  interactive chat bot, which can also execute actions. One boundary, no weaker door.

### A single evidence engine
Two numbers are computed for every material finding, and they are deliberately kept as
**two separate axes that never collapse into one score**:

- **Evidence quality** - how strong is the information base? (independent corroborating
  sources, time coverage, trend duration, whether the impact is graph-confirmed).
- **Confidence** - how likely is *this specific action* correct? Uses floors and ceilings
  so that a *deterministic fact* can yield high confidence on thin evidence, while
  *conflicting signals* cap confidence no matter how much data there is.

The cases where the two axes diverge are the whole point:

| Situation | Evidence | Confidence |
|---|---|---|
| A benign sensor reading misread as a dying drive | LOW | LOW |
| A real problem, but the *recommended fix* is the known-wrong one | **HIGH** | **LOW** |
| A single deterministic fact (a process bound to the wrong interface) | MEDIUM | **HIGH** |

Confidence attaches to the recommended *action*, not the observation - because "the service
is down" can be very well evidenced while "rebuild it from scratch" is a bad fix to a real
problem. Every score ships with a mandatory plain-language explanation, its data freshness,
and the provenance of each contributing factor. It is **annotation only**: a low score
informs the operator, it never hides a finding.

### Everything else
- **Network locks** restricting unauthenticated internal services to their known consumers,
  applied *before* the service starts so there's never an open window at boot.
- **Configuration conformance** reported as three independent dimensions - declared config,
  running state, and network enforcement - so a failure says *which* layer is wrong and
  therefore what to do (edit the file vs. restart the process vs. reassert the firewall),
  emitting only booleans and non-secret comparisons, never file contents.
- **Admission control** so the monitoring never becomes the workload it monitors:
  resource-hungry verification probes defer to real users and heavy jobs, and report
  "skipped - insufficient conditions" rather than a false failure.
- **A CI merge gate** where "no checks reported" is treated as UNKNOWN and *cannot* merge -
  only an explicit named-check pass merges, with the decision recorded on the pull request.
- **An AI-surface inventory** listing every component that calls a model, generates
  operator-visible text, or can execute - with its coverage status cross-checked against
  the source, so a component can't claim a protection its code doesn't have.

---

## The best evidence the guardrails are real

The most convincing outcome wasn't a green dashboard - it was the tooling **catching its
own regressions before they shipped**, repeatedly:

- Adversarial tests found two cases where a screening rule silently let prohibited text
  through, and one where narrowing one rule quietly weakened another. All fixed and pinned
  by tests.
- The test harness caught an integration that would have crashed every scenario, twice -
  and the second fix added a test that derives the requirement from source so it can't
  happen a third time.
- The highest-authority weekly report tried to recommend an unevidenced hardware
  replacement on its very first run behind the new screen. The screen blocked it, live.
- A safety claim from an earlier review ("the gates are stable across three runs") turned
  out to be luck: at the real underlying error rate, three clean runs is a coin flip. The
  deterministic screen is what actually made it safe.

A system that reliably catches its own mistakes is worth more than one that appears not to
make any.

---

## Method notes (how the work was run)

Every change followed the same discipline, and it mattered:

- **One change at a time.** Extend a single path, validate, ship, verify live, then the next.
- **Fixtures and tests first.** The acceptance criteria for the evidence scorer were frozen
  as fixtures *before* the scorer was written, then the scorer was calibrated to them.
- **A baseline before and after.** Behavioral evaluation was captured before each change and
  compared after, so a regression was caught by measurement, not by luck.
- **Deploy is deliberate.** No automated deploy to physical infrastructure; a human ships
  via a reviewed path, and every artifact on disk is checked against the source of truth.
- **Design review before privileged changes.** The one step that touched node privileges
  was designed, reviewed, and approved on paper before anything was installed - and the
  review caught an inert permission entry before it shipped.

---

## The one-line summary

Every AI-generated recommendation an operator can see now passes through one policy engine
(is it allowed?), one evidence engine (how well-supported, how sure?), and one audit trail
(recorded) - with the model reduced to what it is actually good at: wording.

The goal was never a more powerful automation system. It was a more *trustworthy* one.
