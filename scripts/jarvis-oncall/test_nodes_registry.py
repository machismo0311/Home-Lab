#!/usr/bin/env python3
"""Offline fixtures for the node registry. No SSH, no cluster access, no mutation.

Why this exists. On 2026-09-12 the QuarkyLab entry declared `zpools: [datastore]` while the node's
only pool is `workspace`. Nothing caught it because the one code path people exercise - asking for
pool status without naming a pool - falls through to an unscoped `zpool status -v` and works
regardless of what the registry claims. The declaration was wrong for roughly two months and the
bot looked fine the whole time.

Explicit targeting was broken in BOTH directions, which is the part worth locking down:
  pool="workspace"  -> rejected by the registry, so the real pool could not be asked for
  pool="datastore"  -> accepted by the registry, then failed at zpool with "no such pool"
and the same list is rendered into the on-call model's node description, so the bot would state
the wrong pool name to an operator mid-incident with no hedge.

These are named tests. They were top-level statements with a module-level `fails` list and a
trailing sys.exit(1), which meant the first failure aborted the run: reintroducing the QuarkyLab
defect reported one failure and a traceback, hiding the others. Each invariant is now its own
test, so a bad declaration reports every check it breaks.

Run: python3 test_nodes_registry.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import executors  # noqa: E402
import registry  # noqa: E402


def chk(name, cond):
    """Assert one invariant.

    Kept as a helper so every check label below is preserved verbatim from the original
    script. It raises instead of appending to a module-level list, so a violated invariant
    is a named failing test rather than a bare exit code.
    """
    assert cond, name


REG = registry.Registry(os.path.join(os.path.dirname(os.path.abspath(__file__)), "nodes.yaml"))

# `zpool status` is the only verb this tool may ever reach. Anything here would mutate a pool.
MUTATING = {"destroy", "export", "import", "labelclear", "detach", "remove", "replace",
            "offline", "online", "set", "scrub", "clear", "add", "attach", "split", "upgrade"}


def _status_argv(node, pool=None):
    """The argv `_zpool_status` BUILDS for this node. Nothing is executed."""
    return executors._zpool_status(node, {"pool": pool} if pool else {})[0][0]


# ---- the declaration this test was written for --------------------------------------
# One test per check on purpose: reintroducing the 2026-09-12 defect must report every
# invariant it breaks, not just the first one.

def test_quarkylab_declares_exactly_one_pool():
    q = REG.get("quarkylab")
    chk("quarkylab declares exactly one pool", len(q.zpools) == 1)


def test_quarkylab_pool_is_workspace():
    q = REG.get("quarkylab")
    chk("quarkylab's pool is 'workspace'", q.zpools == ["workspace"])


def test_quarkylab_does_not_declare_datastore():
    q = REG.get("quarkylab")
    chk("quarkylab no longer declares 'datastore'", "datastore" not in q.zpools)


# ---- the node that legitimately DOES have a pool called datastore --------------------

def test_randy_still_declares_datastore():
    chk("randy still declares 'datastore' (it really has one)", REG.get("randy").zpools == ["datastore"])


def test_jarvis_still_declares_tank_and_scratch():
    chk("jarvis still declares tank+scratch", REG.get("jarvis").zpools == ["tank", "scratch"])


# ---- explicit targeting works for the real pool, in both directions ------------------

def test_explicit_pool_yields_a_scoped_status_command():
    q = REG.get("quarkylab")
    argv, use_sudo = executors._zpool_status(q, {"pool": "workspace"})[0]
    chk("explicit workspace yields `zpool status -v workspace`",
        argv == ["/usr/sbin/zpool", "status", "-v", "workspace"])
    chk("the query runs through sudo (the pinned read-only grant)", use_sudo is True)


def test_a_pool_the_node_does_not_have_is_rejected():
    q = REG.get("quarkylab")
    try:
        executors._zpool_status(q, {"pool": "datastore"})
        chk("a pool quarkylab does not have is rejected", False)
    except executors.ToolError:
        chk("a pool quarkylab does not have is rejected", True)


# ---- the unscoped fallback still works, and is NOT the only thing that works ---------

def test_unscoped_query_still_works():
    chk("unscoped query still yields `zpool status -v`",
        _status_argv(REG.get("quarkylab")) == ["/usr/sbin/zpool", "status", "-v"])


# ---- no mutation path is reachable through this tool --------------------------------

def test_no_mutating_verb_is_reachable():
    for node_name in REG.nodes:
        n = REG.get(node_name)
        if not n.zpools:
            continue
        for arg in (None, n.zpools[0]):
            if set(_status_argv(n, arg)) & MUTATING:
                chk(f"{node_name}: no mutating verb reachable", False)
                break
        else:
            chk(f"{node_name}: only `zpool status -v [pool]` is reachable", True)


# ---- every declared pool name is well-formed (cheap guard against another typo) -------

def test_declared_pool_names_are_plain_identifiers():
    for node_name in REG.nodes:
        for pool in REG.get(node_name).zpools:
            chk(f"{node_name}: pool name {pool!r} is a plain identifier",
                pool.isascii() and pool.replace("_", "").replace("-", "").isalnum())


if __name__ == "__main__":
    fns = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    failed = 0
    for name, fn in fns:
        try:
            fn()
            print("  PASS  %s" % name)
        except AssertionError as exc:
            failed += 1
            print("  FAIL  %s: %s" % (name, exc))
    print("NODE REGISTRY: %d/%d passed" % (len(fns) - failed, len(fns)))
    sys.exit(1 if failed else 0)
