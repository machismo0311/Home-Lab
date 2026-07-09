"""Node registry — loads nodes.yaml and answers questions the tools need.

Keeps every tool function node-agnostic: they take a `node` name, ask the
registry for its SSH target / role / restart allowlist, and never hardcode IPs.
"""
import os
import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
_PATH = os.environ.get("ONCALL_NODES", os.path.join(_HERE, "nodes.yaml"))


class Node:
    def __init__(self, name: str, data: dict, defaults: dict):
        self.name = name
        self.ssh_host = data.get("ssh_host", "")
        self.ssh_user = data.get("ssh_user", defaults.get("ssh_user", "monitor"))
        self.ssh_key = data.get("ssh_key", defaults.get("ssh_key", ""))
        self.ssh_opts = data.get("ssh_opts", defaults.get("ssh_opts", ""))
        self.local = bool(data.get("local", False))
        self.reachable = bool(data.get("reachable", True))
        self.role = data.get("role", "")
        self.quirks = " ".join((data.get("quirks") or "").split())
        self.zpools = data.get("zpools") or []
        self.has_gpu = bool(data.get("has_gpu", False))
        self.restart_allowed = data.get("restart") or []

    def may_restart(self, unit: str) -> bool:
        return unit in self.restart_allowed


class Registry:
    def __init__(self, path: str = _PATH):
        with open(path, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        defaults = raw.get("defaults", {})
        self.nodes = {n: Node(n, d, defaults) for n, d in raw.get("nodes", {}).items()}

    def get(self, name: str) -> Node | None:
        if not name:
            return None
        return self.nodes.get(name.strip().lower())

    def names(self) -> list[str]:
        return list(self.nodes.keys())

    def reachable(self) -> list[Node]:
        return [n for n in self.nodes.values() if n.reachable]


registry = Registry()
