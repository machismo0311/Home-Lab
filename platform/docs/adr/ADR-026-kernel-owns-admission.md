<!--
  Public edition. Reused from the private engineering corpus.
  Source: docs/adr/ADR-026-kernel-owns-admission.md
  Sanitization: none required (zero estate identifiers)
-->

> [ADR index](README.md) · [Package index](../../README.md)

---

# ADR-026: The kernel owns admission

- **Status:** Accepted. Implemented in Stabilization Phase 2, cycle 4.
- **Date:** 2026-07-31
- **Context owner:** engineering
- **Source:** NF-PRR-001 / NF-HARD-001, TD-047

## Context

`Engine.ask` accepted a question of any length. `intent.resolve` is superlinear in length, measured
on this tree:

```
chars     500    1000    2000    4000    8000   16000   52000
resolve   57ms    27ms    50ms    95ms   313ms  1031ms     12s
```

So an unbounded question was unbounded CPU, inside a transport with no turn deadline.

One cap existed, in `joi.py`:

```python
question = str(body.get("question") or "").strip()[:1000]
```

It has both of the defects this programme has already ruled on twice.

1. **It is in a caller.** A protection implemented in a caller protects that caller and nothing
   else. The CLI path in the same file called `ask()` with no cap at all, and a second transport
   would either re-implement the cap or inherit the denial of service.
2. **It truncates silently.** A question cut to 1000 characters is a *different question*, and the
   engine then answered that different question at full confidence with nothing in the answer, the
   transparency block or the store recording that anything had been dropped. For a platform whose
   whole claim is that a conclusion can be traced to its evidence, answering a question the operator
   did not ask is a worse failure than refusing the one they did.

## Decision

**The kernel owns admission.** `engine.admit(question) -> (text, refusal_or_None)` is the boundary,
`MAX_QUESTION_CHARS = 2000` is the bound, and every question the kernel will parse passes through
it. The transport no longer has an opinion about how long a question may be.

Three properties, each chosen against a specific failure:

- **Refuse, never truncate.** Truncation is the failure mode this boundary exists to remove, so it
  is not available as an implementation of it. The refusal states the measured length, the limit,
  and explicitly that nothing was cut.
- **Refuse, never raise.** `ask` returns an Answer and every transport renders one. An exception
  would have to be caught and translated per transport, which is the duplicated, drifting admission
  logic this replaces. A refusal is already a complete answer, and the refusal path was built for
  exactly this: *"a new cause is data, not a new code path."*
- **A legal question is returned by identity.** Admission validates; it does not strip, normalise,
  case-fold or re-encode. What the caller sent is what the parser sees and what the answer echoes.

## There are two ways into the parser, not one

The obvious entry is the caller's question. The second is `_prior`, which re-resolves a question
read back **out of the store** so a meta turn can explain the previous primary turn. It was live: a
40,000-character question written to disk once cost 574ms of parser time on *every* later meta turn
in that conversation, with no caller involved.

Both entries are in `engine.py`, so admitting both is one owner doing its own job rather than a
check scattered across packages. A file written before this bound existed, or edited by hand, is
not trusted more than a caller.

A refused question is also **not recorded**. Recording it would put the oversized string into the
store and feed it back through `_prior` on the next meta turn, which is the same unbounded work
arriving by a longer route.

## Why a length bound is sufficient

A length bound only bounds work if cost is a function of length. Two measured properties say it is,
and both are asserted by tests rather than assumed:

- **No catastrophic backtracking is reachable.** None of the 108 compiled intent patterns contains
  a nested quantifier. A structural test asserts this stays true as patterns are added.
- **Plain English is the worst case.** At a fixed 2000 characters, no adversarial shape tried cost
  more than ordinary English: single-character runs, alias near-misses, punctuation storms, nested
  parentheses, quantifier bait, astral-plane text, combining marks. Every one came in at or below.

If either stops holding, a length bound stops being sufficient and this decision needs revisiting.
That is why both are tests and not comments.

## Why 2000

Derived, not chosen. A full cold turn costs 67ms at 1000 characters, 92ms at 2000, 150ms at 4000,
against a stated turn budget of p95 < 250ms. 2000 keeps the worst legal turn at roughly a third of
the budget and leaves the parser four times' headroom before it alone would breach it. It is also
twice what the transport used to truncate at, so nothing that worked before stops working: this
loosens the effective limit while making the boundary explicit.

## The transport's byte cap is a different concern, and must not contradict this one

`joi.py` still bounds the request body, because bounding how many bytes are read off a socket is a
transport's own business and is not the same question as how long a question may be. But the two
must not disagree, so `MAX_BODY_BYTES` is now **derived** from `MAX_QUESTION_CHARS`: the largest
legal question is 2000 characters, worst case all astral-plane, which JSON-escape to 12 bytes each,
so a body carrying the largest legal question reaches about 24,000 bytes. The old cap was 8192 --
**below that line**, which meant a 2000-character non-ASCII question was rejected by the transport
before the kernel ever saw it, and the kernel's limit was not the real limit for anyone not writing
in ASCII. A test recomputes the worst case from the kernel's bound and fails if the cap stops
covering it.

Raising the cap does not widen admission. The kernel now refuses oversized questions outright,
where before this transport quietly truncated them and answered the truncation.

## Falsification

Eight protections, each removed independently, each biting only its own invariant:

| Removed | Result |
|---|---|
| the bound itself | 10 assertions fail |
| `ask` no longer admits | 9 fail |
| `_prior` no longer admits | 1 fails, the store entry |
| admission strips whitespace | 1 fails |
| admission NFC-normalises | 1 fails |
| admission case-folds | 2 fail |
| truncate instead of refuse | 8 fail |
| `[:1000]` restored in the transport | 1 fails |
| body cap back to 8192 | 1 fails |
| `RecursionError` uncaught | 1 fails |

Two of these initially bit **nothing**, and both were the same mistake: the assertion was a source
grep that matched the *comment explaining the fix*, so deleting the fix left the test passing. Both
are now structural -- the truncation scan strips comments and string literals before matching, and
the exception assertion reads the `except` clause out of the AST.

## Consequences

- One place decides whether a question is acceptable, and it is the place that parses it.
- A new transport inherits admission by calling `ask`. It cannot forget to, and it cannot disagree.
- An operator who asks something too long is told so, told the limit, and told nothing was cut.
- The transport gained a `RecursionError` handler on its body parse. `json.loads` on 100,000 nested
  arrays raises it, `RecursionError` is not a `ValueError`, and it was escaping the handler
  uncaught. Found while testing the "deeply nested structures" case against the admission boundary.

## What this does not close

Admission bounds the work a request can cause once it arrives. It does not bound the resources a
request can hold by never finishing (**TD-063**, no socket read deadline), and it does not make the
session id distinct (**TD-064**, `[:64]` is still a silent truncation one line away, of an
identifier rather than of a question). Both are registered rather than folded in.
