"""Thin SSH runner: execute a fixed argv on a node as the low-priv monitor user.

No shell strings are ever built from LLM output — callers pass an argv list and
we hand it to `ssh` (or run it locally on Jarvis). This is the ONLY place the
bot shells out to nodes; Phases 2/3 build argv lists from whitelisted tools and
call run(). Kept in Phase 1 so the later phases are a small step.
"""
import asyncio
import shlex

from registry import Node


async def run(node: Node, argv: list[str], *, sudo: bool = False, timeout: int = 30):
    """Run argv on `node`. Returns (rc, stdout, stderr).

    - Local node (Jarvis): exec directly.
    - Remote: ssh monitor@host with the node's key/opts.
    - sudo=True prefixes the *remote* argv with sudo -n (used only by mutating
      tools, whose exact command must be covered by /etc/sudoers.d/jarvis-oncall).
    """
    if node.local:
        cmd = (["sudo", "-n"] + argv) if sudo else argv
    else:
        remote = (["sudo", "-n"] + argv) if sudo else argv
        remote_str = " ".join(shlex.quote(a) for a in remote)
        cmd = (
            ["ssh"]
            + shlex.split(node.ssh_opts)
            + (["-i", node.ssh_key] if node.ssh_key else [])
            + [f"{node.ssh_user}@{node.ssh_host}", remote_str]
        )

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return 124, "", f"timed out after {timeout}s"
    return proc.returncode, out.decode(errors="replace"), err.decode(errors="replace")
