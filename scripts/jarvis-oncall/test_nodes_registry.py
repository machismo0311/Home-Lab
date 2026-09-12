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

Run: python3 test_nodes_registry.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import executors  # noqa: E402
import registry  # noqa: E402

fails = []


def chk(name, cond):
    print(("PASS  " if cond else "FAIL  ") + name)
    if not cond:
        fails.append(name)


REG = registry.Registry(os.path.join(os.path.dirname(os.path.abspath(__file__)), "nodes.yaml"))

# ---- the declaration this test was written for --------------------------------------
q = REG.get("quarkylab")
chk("quarkylab declares exactly one pool", len(q.zpools) == 1)
chk("quarkylab's pool is 'workspace'", q.zpools == ["workspace"])
chk("quarkylab no longer declares 'datastore'", "datastore" not in q.zpools)

# ---- the node that legitimately DOES have a pool called datastore --------------------
chk("randy still declares 'datastore' (it really has one)", REG.get("randy").zpools == ["datastore"])
chk("jarvis still declares tank+scratch", REG.get("jarvis").zpools == ["tank", "scratch"])

# ---- explicit targeting works for the real pool, in both directions ------------------
cmds = executors._zpool_status(q, {"pool": "workspace"})
argv, use_sudo = cmds[0]
chk("explicit workspace yields `zpool status -v workspace`",
    argv == ["/usr/sbin/zpool", "status", "-v", "workspace"])
chk("the query runs through sudo (the pinned read-only grant)", use_sudo is True)

try:
    executors._zpool_status(q, {"pool": "datastore"})
    chk("a pool quarkylab does not have is rejected", False)
except executors.ToolError:
    chk("a pool quarkylab does not have is rejected", True)

# ---- the unscoped fallback still works, and is NOT the only thing that works ---------
argv_none = executors._zpool_status(q, {})[0][0]
chk("unscoped query still yields `zpool status -v`",
    argv_none == ["/usr/sbin/zpool", "status", "-v"])

# ---- no mutation path is reachable through this tool --------------------------------
MUTATING = {"destroy", "export", "import", "labelclear", "detach", "remove", "replace",
            "offline", "online", "set", "scrub", "clear", "add", "attach", "split", "upgrade"}
for node_name in REG.nodes:
    n = REG.get(node_name)
    if not n.zpools:
        continue
    for arg in (None, n.zpools[0]):
        a = executors._zpool_status(n, {"pool": arg} if arg else {})[0][0]
        if set(a) & MUTATING:
            chk(f"{node_name}: no mutating verb reachable", False)
            break
    else:
        chk(f"{node_name}: only `zpool status -v [pool]` is reachable", True)

# ---- every declared pool name is well-formed (cheap guard against another typo) -------
for node_name in REG.nodes:
    for pool in REG.get(node_name).zpools:
        chk(f"{node_name}: pool name {pool!r} is a plain identifier",
            pool.isascii() and pool.replace("_", "").replace("-", "").isalnum())

print("----")
print("NODE REGISTRY: " + ("FAIL " + str(fails) if fails else "PASS"))
sys.exit(1 if fails else 0)
