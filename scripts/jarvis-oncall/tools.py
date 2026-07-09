"""Whitelisted tool schemas + classification.

The LLM may ONLY ask for one of these named functions (never a raw shell
string). Each takes a `node` argument so the same tool reaches any registered
node. Read-only tools run without confirmation; MUTATING tools go through the
Discord confirm-and-execute flow.

Phase 1 defines the schemas and classification only — execution lands in
Phase 2 (read-only) and Phase 3 (restart_service).
"""
from registry import registry

_NODE_ENUM = registry.names()


def _node_param(desc="Target node."):
    return {"type": "string", "enum": _NODE_ENUM, "description": desc}


# OpenAI-style function tools, passed straight to llm_router (which now forwards
# them to Ollama and converts them for Claude).
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "check_service_status",
            "description": "Read-only. `systemctl is-active`/`status` for a unit on a node.",
            "parameters": {
                "type": "object",
                "properties": {
                    "node": _node_param(),
                    "unit": {"type": "string", "description": "systemd unit, e.g. llm_router or pveproxy."},
                },
                "required": ["node", "unit"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tail_logs",
            "description": "Read-only. Tail recent journald logs for a unit (or the whole journal).",
            "parameters": {
                "type": "object",
                "properties": {
                    "node": _node_param(),
                    "unit": {"type": "string", "description": "Optional systemd unit to scope logs to."},
                    "lines": {"type": "integer", "description": "How many lines (default 100, max 500)."},
                },
                "required": ["node"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "zpool_status",
            "description": "Read-only. `zpool status`/`zpool list` on a node with ZFS pools (randy, quarkylab, jarvis).",
            "parameters": {
                "type": "object",
                "properties": {
                    "node": _node_param(),
                    "pool": {"type": "string", "description": "Optional pool name; omit for all pools."},
                },
                "required": ["node"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gpu_status",
            "description": "Read-only. `nvidia-smi` on a GPU node (jarvis, quarkylab).",
            "parameters": {
                "type": "object",
                "properties": {"node": _node_param()},
                "required": ["node"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "disk_usage",
            "description": "Read-only. `df -h` filesystem usage on a node.",
            "parameters": {
                "type": "object",
                "properties": {"node": _node_param()},
                "required": ["node"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "vm_status",
            "description": "Read-only. List VMs/containers on a Proxmox node (`qm list` / `pct list`).",
            "parameters": {
                "type": "object",
                "properties": {"node": _node_param()},
                "required": ["node"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "restart_service",
            "description": (
                "STATE-CHANGING (requires the operator to confirm in Discord). "
                "Restart an allowlisted systemd unit on a node. Only units in that "
                "node's restart allowlist are permitted."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "node": _node_param(),
                    "unit": {"type": "string", "description": "Allowlisted unit to restart."},
                },
                "required": ["node", "unit"],
            },
        },
    },
]

READONLY_TOOLS = {
    "check_service_status",
    "tail_logs",
    "zpool_status",
    "gpu_status",
    "disk_usage",
    "vm_status",
}
MUTATING_TOOLS = {"restart_service"}
ALL_TOOLS = READONLY_TOOLS | MUTATING_TOOLS


def is_mutating(name: str) -> bool:
    return name in MUTATING_TOOLS


def render_call(name: str, args: dict) -> str:
    """Human-readable one-liner for a proposed/executed tool call."""
    node = args.get("node", "?")
    extra = ", ".join(f"{k}={v}" for k, v in args.items() if k != "node")
    return f"{name}(node={node}{', ' + extra if extra else ''})"
