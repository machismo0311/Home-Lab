#!/usr/bin/env python3
"""Generate the NETFRAME topology diagram (Mermaid) from a source-of-truth inventory.

Single source of truth: ``topology/inventory.yml``.
Run this script and commit the regenerated ``topology/topology.mmd``.
CI (``.github/workflows/diagram.yml``) re-runs it and fails the build if the
committed diagram has drifted from the inventory — so the picture can never lie
about the network.

    python3 topology/gen_diagram.py            # regenerate topology.mmd
    python3 topology/gen_diagram.py --check     # exit 1 if the committed file is stale
"""
from __future__ import annotations

import argparse
import pathlib
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML is required — install with: pip install pyyaml")

HERE = pathlib.Path(__file__).resolve().parent
INVENTORY = HERE / "inventory.yml"
OUTPUT = HERE / "topology.mmd"

# Mermaid classDef styling per node role.
ROLE_STYLE = {
    "edge": "fill:#cc4400,color:#fff",
    "firewall": "fill:#163016,color:#eee",
    "switch": "fill:#1a1a2e,color:#eee",
    "node": "fill:#20143a,color:#eee",
    "standalone": "fill:#2b2b2b,color:#cccccc",
}


def _esc(text: str) -> str:
    """Mermaid node labels are wrapped in double quotes, so swap any inner quotes."""
    return text.replace('"', "'")


def render(inventory: dict) -> str:
    lines: list[str] = ["flowchart TB"]

    for node in inventory["nodes"]:
        label = _esc(node["label"])
        if node.get("note"):
            label += "<br/>" + _esc(node["note"])
        lines.append(f'    {node["id"]}["{label}"]')

    lines.append("")

    for link in inventory["links"]:
        src, dst = link[0], link[1]
        edge_label = link[2] if len(link) > 2 else None
        if edge_label:
            lines.append(f"    {src} -->|{edge_label}| {dst}")
        else:
            lines.append(f"    {src} --> {dst}")

    lines.append("")

    roles: dict[str, list[str]] = {}
    for node in inventory["nodes"]:
        roles.setdefault(node["role"], []).append(node["id"])

    for role, style in ROLE_STYLE.items():
        if role in roles:
            lines.append(f"    classDef {role} {style}")
    for role, ids in roles.items():
        if role in ROLE_STYLE:
            lines.append(f'    class {",".join(ids)} {role}')

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify topology.mmd is up to date with inventory.yml; exit 1 if not",
    )
    args = parser.parse_args()

    inventory = yaml.safe_load(INVENTORY.read_text())
    generated = render(inventory)

    if args.check:
        current = OUTPUT.read_text() if OUTPUT.exists() else ""
        if current != generated:
            print(
                "topology.mmd is out of date with inventory.yml.\n"
                "Run: python3 topology/gen_diagram.py",
                file=sys.stderr,
            )
            return 1
        print("topology.mmd is in sync with inventory.yml ✓")
        return 0

    OUTPUT.write_text(generated)
    print(f"wrote {OUTPUT.relative_to(HERE.parent)} ({len(inventory['nodes'])} nodes, "
          f"{len(inventory['links'])} links)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
