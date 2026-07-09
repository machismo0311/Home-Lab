"""Read-only tool executors (Phase 2).

Each whitelisted read-only tool maps to a fixed set of commands (absolute paths,
no shell metacharacters) run on the target node via ssh.py. The LLM chooses the
tool + node/unit; this module decides the exact argv. Nothing here mutates
state — `restart_service` is handled by the Phase 3 confirm flow, not here.

Commands that need root use sudo=True and must be covered by the monitor
sudoers (see README / sudoers.d/jarvis-oncall-readonly.example).
"""
from registry import registry, Node
import ssh

# Chars of tool output fed back to the model. Kept modest because the local
# model runs at OLLAMA_NUM_CTX=8192 — several large tool outputs would overflow.
MAX_OUTPUT = 1800


class ToolError(Exception):
    """Validation failure — reported to the operator, never executed."""


def _clamp_lines(v, default=100, lo=1, hi=500) -> int:
    try:
        v = int(v)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, v))


def _require_node(args: dict) -> Node:
    node = registry.get(args.get("node", ""))
    if node is None:
        raise ToolError(f"unknown node '{args.get('node')}' (known: {', '.join(registry.names())})")
    if not node.reachable:
        raise ToolError(f"node '{node.name}' is not reachable by the bot (no monitor user provisioned)")
    return node


# Each builder returns a list of (argv, sudo) command specs to run in order.
def _check_service_status(node: Node, args: dict):
    unit = args.get("unit")
    if not unit:
        raise ToolError("check_service_status requires a 'unit'")
    return [(["/usr/bin/systemctl", "status", unit, "--no-pager", "--lines=20"], False)]


def _tail_logs(node: Node, args: dict):
    lines = _clamp_lines(args.get("lines"))
    unit = args.get("unit")
    argv = ["/usr/bin/journalctl", "-n", str(lines), "--no-pager"]
    if unit:
        argv += ["-u", unit]
    else:
        argv += ["-p", "warning"]  # whole-journal view: warnings and worse only
    return [(argv, False)]


def _zpool_status(node: Node, args: dict):
    if not node.zpools:
        raise ToolError(f"node '{node.name}' has no ZFS pools")
    pool = args.get("pool")
    if pool and pool not in node.zpools:
        raise ToolError(f"pool '{pool}' not on {node.name} (pools: {', '.join(node.zpools)})")
    argv = ["/usr/sbin/zpool", "status", "-v"]
    if pool:
        argv.append(pool)
    return [(argv, True)]


def _gpu_status(node: Node, args: dict):
    if not node.has_gpu:
        raise ToolError(f"node '{node.name}' has no GPU")
    return [(["/usr/bin/nvidia-smi"], False)]


def _disk_usage(node: Node, args: dict):
    return [(["/bin/df", "-h", "-x", "tmpfs", "-x", "devtmpfs"], False)]


def _vm_status(node: Node, args: dict):
    if not node.name.startswith("pve") and node.name not in ("randy", "quarkylab", "jarvis"):
        raise ToolError(f"node '{node.name}' is not a Proxmox node")
    return [(["/usr/sbin/qm", "list"], True), (["/usr/sbin/pct", "list"], True)]


_BUILDERS = {
    "check_service_status": _check_service_status,
    "tail_logs": _tail_logs,
    "zpool_status": _zpool_status,
    "gpu_status": _gpu_status,
    "disk_usage": _disk_usage,
    "vm_status": _vm_status,
}


def _fmt(argv, rc, out, err) -> str:
    cmd = " ".join(argv)
    body = (out or "").rstrip()
    if err and err.strip():
        body += ("\n" if body else "") + "[stderr] " + err.strip()
    if len(body) > MAX_OUTPUT:
        body = body[:MAX_OUTPUT] + f"\n… (truncated, rc={rc})"
    return f"$ {cmd}\n{body or '(no output)'}"


async def run_readonly(name: str, args: dict) -> tuple[bool, str]:
    """Run a read-only tool. Returns (ok, text). ok=False means a validation
    error (nothing ran); command non-zero exit is still ok=True with the rc/err
    shown, so the model can reason about it."""
    builder = _BUILDERS.get(name)
    if builder is None:
        return False, f"'{name}' is not a read-only tool"
    node = _require_node(args)
    specs = builder(node, args)
    chunks = []
    for argv, sudo in specs:
        rc, out, err = await ssh.run(node, argv, sudo=sudo)
        chunks.append(_fmt(argv, rc, out, err))
    return True, "\n\n".join(chunks)
