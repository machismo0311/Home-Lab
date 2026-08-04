<!--
  Public edition. Reused from the private engineering corpus.
  Source: docs/adr/ADR-027-session-ownership-lifecycle.md
  Sanitization: none required (zero estate identifiers)
-->

> [ADR index](README.md) · [Package index](../../README.md)

---

# ADR-027: The kernel owns the session lifecycle

- **Status:** Accepted. Implemented in Stabilization Phase 2, cycle 5.
- **Date:** 2026-07-31
- **Context owner:** engineering
- **Source:** NF-PRR-001 / NF-HARD-001, TD-048 and TD-053, closing TD-062 and TD-064

## Context

TD-048 and TD-053 were filed as separate findings. They are one concern seen from two sides:
**nothing owned the lifetime of a session**, so every stage of that lifetime was unowned in a
different way.

| Stage | What owned it | What went wrong |
|---|---|---|
| creation | a dict in one transport | a client could name a session into existence |
| identity | `uuid4().hex[:12]` | 48 bits, and never treated as a credential |
| reopening | `Conversation.resume` | an unknown id was adopted rather than refused |
| modification | `sessions.get` then `sessions[...] = ` | check-then-act, 38% duplicate Engines |
| invalidity | two clocks | files expired on a 12h TTL; the map caching them did not |
| eviction | nobody | 720 KiB per session, 104 sessions/s, held until restart |

Fixing any one of these leaves the others as open doors into the same room. The demonstrated
consequence was not theoretical: an attacker resumed `alice-secret-thread`, read the victim's
question back, and appended turns that became the victim's binding context.

## Decision

**One owner for the whole lifecycle, in the kernel: `engine.SessionRegistry`.**

```
creation    only the registry mints an id; a caller cannot name a session into existence
reopening   an id is honoured only if it is minted-SHAPED and names a real, unexpired session;
            anything else gets a new session and is TOLD so
modifying   exactly one Engine per id, handed out under one lock
invalidity  `Conversation.expired()` decides, and nothing has a second opinion
eviction    at admission, synchronously, least-recently-used first
```

The dependency direction is unchanged: transport to kernel to state. `joi.py` calls `open()`,
`engine.py` owns admission, `context.py` owns identity, persistence and the TTLs.

## The shape is the credential's shape

The hard part was allowing an operator's named local thread (`JOI_SESSION=my-work`) and a
server-issued thread to coexist in one store without either being reachable from the other.

A minted id is `secrets.token_urlsafe(16)`: 128 bits, exactly 22 characters, in exactly `safe_id`'s
alphabet. So it is filename-safe **by construction** rather than by being cleaned up afterwards,
and more usefully, *an id that is not 22 characters cannot have been minted*. `my-local-thread` is
not a capability, so a network client presenting it is not presenting one, and gets its own session
instead of someone else's.

This needed no new stored field and no migration. Provenance is readable from the identifier.

## Why `adopt` is a parameter and not a second door

An operator naming their own thread on their own machine is a genuinely different act from a
network client claiming an id it did not obtain. `open(sid, adopt=True)` allows the first; the CLI
is the only caller in the tree that passes it, and a test asserts the HTTP handler does not.

The default is the restrictive direction, so forgetting the parameter can only ever make a caller
**more** restricted. That is the property that makes one parameter safer than two methods.

## Alternatives rejected

**Leave the map in the transport and just bound it.** Fixes TD-048 alone and leaves creation,
identity and reopening unowned. It is also the caller-owned-protection shape this programme has
ruled on three times: it would protect the HTTP transport and not the CLI.

**Reject unknown ids with an error.** Rejected because a client whose session merely expired or was
evicted would get an error instead of a working session. Minting and *saying so* is both usable and
honest; `session_minted` in the response is the difference between refusing silently and refusing
visibly.

**A background sweeper for expiry and capacity.** Rejected: a bound that depends on cleanup running
is not a bound. Reaping and eviction happen inside `open`, on the admission path, synchronously.

**Persist a provenance flag per conversation.** Rejected once the id's shape turned out to carry the
same information without a schema change or a migration path for existing files.

## Falsification

Ten protections, removed independently:

| Removed | Result |
|---|---|
| the admission lock | S3 fails, 11 distinct Engines for one id |
| the minted-shape gate | S2 fails, cross-session access restored |
| `adopt` defaults to True | 8 fail |
| expiry reaping | S4 fails, dead sessions hold capacity |
| eviction | 4 fail |
| `load` reverted to `resume` | S4 fails, the silent reset returns |
| the existence check | 3 fail |
| `secrets` back to a truncated uuid | 16 fail |
| transport takes session policy back | S8 fails |
| MRU re-insertion | S5 fails, LRU degenerates to insertion order |

**Three of these initially bit nothing, and each exposed a test that passed for the wrong reason.**

- The concurrency test seeded the session into the registry first, so all 16 threads found an
  existing entry and never raced on *creation*. The lock could be deleted with nothing failing.
- The "named session is not reachable" test never persisted the session, so it passed because
  nothing was on disk to find, not because the shape gate refused it.
- Removing the reaper changed nothing, because the inline expiry check in `open` already covers the
  session being opened. The reaper's actual job is reclaiming capacity from *other* dead sessions,
  which no assertion covered.

All three tests were rewritten to reproduce the real condition, and all three mutations now bite.

## A defect found in this implementation, by its own tests

The first version called `Conversation.resume(key)` and then checked `expired()` on the result.
`resume` **resets** an expired thread and returns it under the same id, so that check was dead code:
the answer was always `False` by the time it ran. A returning client whose thread had expired was
handed an empty conversation with `minted=False`, reporting that continuity held while the history
was gone. That is precisely the "silently repair invalid state" this cycle was told to reject.

Fixed by reading `load()` instead, which returns the state as it actually is on disk.

## Consequences

- Measured closed: 8 of 8 duplicate Engines becomes 1 of 1; 400 admissions against a bound of 16
  hold 16 with no RSS growth; the cross-session reproduction returns a fresh session with 0 turns.
- **TD-062 is closed as a side effect and correctly so.** It was deferred out of TD-054 with the
  note that admission was this cycle's territory. The store's merge path is now defence-in-depth
  against cross-*process* writers rather than a workaround for an in-process admission defect.
- **TD-064 is closed for the reachable path.** The transport no longer touches the id. `safe_id`
  still truncates at 64 characters on the `adopt=True` path, which requires being the operator, who
  can already name any thread.
- Responses carry `session_minted`, so a client can tell continuity was broken rather than
  inferring it from a confusing answer.

## What this does not close

**TD-065.** This is capability-based, not authenticated. It stops a client claiming a session by
naming or guessing one. It cannot stop a client that has genuinely obtained a valid id, because
there is no identity in this stack to bind a session to. That is stated in the registry's own
docstring rather than implied, and it gates any exposure beyond loopback.

**TD-066.** Three local CLI paths still construct conversation state directly. Each is a
single-process session that accepts no external id, so routing them through the registry would add
indirection without adding a guarantee, but "only the registry mints a session" is true of served
sessions rather than literally true of the tree.
