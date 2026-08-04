"""Mutation campaign for the NetFRAME Public Release Gate.

The premise, taken from the platform's own engineering stories: a gate you can satisfy
without changing the condition is decoration, and a gate's value is entirely in whether
green means something. So the gate is attacked rather than demonstrated.

Each mutation builds a clean, publishable baseline tree, applies exactly one defect, and
asserts that the gate FAILS **and that the expected check is the one that catches it**.
Asserting only "it failed" would let a mutation pass for the wrong reason, which is the
same class of defect as a test that asserts the right thing about the wrong input.

Two control cases guard the campaign itself:
  * the unmutated baseline must PASS, otherwise every mutation "passes" trivially;
  * a mutation that no check catches is an ESCAPE and fails the campaign.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import importlib.machinery  # noqa: E402
import importlib.util  # noqa: E402


def _load_gate():
    """The gate has no .py suffix, so it needs an explicit source loader. When the campaign
    is invoked through `verify-publication --self-test` the module is already loaded as
    __main__, and reusing it keeps a single owner of the policy at runtime."""
    main_mod = sys.modules.get("__main__")
    if main_mod is not None and hasattr(main_mod, "run_gate"):
        return main_mod
    path = os.path.join(HERE, "verify-publication")
    loader = importlib.machinery.SourceFileLoader("netframe_publication_gate", path)
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise ImportError(f"cannot load the gate from {path}")
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


vp = _load_gate()


# --------------------------------------------------------------------------------------
# Baseline: the smallest tree that legitimately passes every check.
# --------------------------------------------------------------------------------------

BASELINE_FILES: dict[str, str] = {
    "README.md": """# NetFRAME, a governed operations platform

Operational tooling that refuses to lie. It investigates, explains, and declines to answer
where the evidence does not support a conclusion. This baseline exists so the release gate
has something legitimate to compare a mutation against.

![Question to answer pipeline](images/pipeline.svg)

See [the architecture](docs/architecture.md) and [the changelog](CHANGELOG.md).

```text
./demo/run-demo
```
""",
    "docs/architecture.md": """# Architecture

A question enters through one transport and reaches one kernel. The kernel decides what is
admitted, a closed intent set decides what it means, retrieval gathers claims that carry
provenance, and a guard discards generated text the evidence does not support.
""",
    "CHANGELOG.md": """# Changelog

## 0.1.0

First public showcase release.
""",
    "LICENSE": """Apache License
Version 2.0, January 2004

Licensed under the Apache License, Version 2.0.
""",
    "SECURITY.md": """# Security policy

Report suspected issues privately. This edition documents software properties only and
deliberately withholds estate specifics.
""",
    "images/pipeline.svg": """<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>
""",
    "docs/diagram.md": """# Diagram

```mermaid
graph LR
    A --> B
```
""",
}

# The diagram contract the baseline declares. K19 verifies exactly this and nothing else.
BASELINE_CONTRACT = {"docs/diagram.md": 1}

# Deliberately fictional. Used only to exercise the mechanism: shape matching does not care
# whether a hostname is real, which is precisely why real values were never necessary.
FICTIONAL_PATTERNS = {
    "hostnames": ["alpha-node", "beta-node", "gamma-node",
                  "example-storage", "example-gpu", "example-cluster"],
    "domains": ["corp.example", "internal.example"],
    "addresses": ["198.18.0.1"],
    "private_repos": ["example-private-repo", "example-org/example-internal"],
    "role_map": {"alpha-node": "NODE-A", "beta-node": "NODE-B", "gamma-node": "NODE-C",
                 "example-storage": "STORAGE-HOST", "example-gpu": "GPU-HOST-A",
                 "example-cluster": "the cluster"},
}

BASELINE_METADATA = {
    "description": "A governed, evidence-first operations platform with an offline demo.",
    "topics": ["platform-engineering", "sre", "observability", "provenance", "governance"],
    "homepage": "https://example.com",
    "license": "Apache-2.0",
}


def build_baseline(root: str) -> tuple[str, str]:
    for rel, content in BASELINE_FILES.items():
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(content)

    manifest_path = os.path.join(root, "..", "publication-manifest.txt")
    manifest_path = os.path.abspath(manifest_path)
    with open(manifest_path, "w", encoding="utf-8") as fh:
        fh.write("# baseline manifest\n")
        for rel in sorted(BASELINE_FILES):
            fh.write(f"source/{rel} | {rel} | AS-IS | 2026-08-03\n")

    # The fictional vocabulary is generated here rather than committed as a file. A committed
    # patterns file, even a fictional one, is a template for the real one and invites someone to
    # fill it in and commit that. The campaign needs the values, not the artifact.
    patterns_path = os.path.abspath(os.path.join(root, "..", "estate-patterns.json"))
    with open(patterns_path, "w", encoding="utf-8") as fh:
        json.dump(FICTIONAL_PATTERNS, fh, indent=2, sort_keys=True)

    metadata_path = os.path.abspath(os.path.join(root, "..", "repo-metadata.json"))
    with open(metadata_path, "w", encoding="utf-8") as fh:
        json.dump(BASELINE_METADATA, fh, indent=2, sort_keys=True)

    contract_path = os.path.abspath(os.path.join(root, "..", "diagram-contract.json"))
    with open(contract_path, "w", encoding="utf-8") as fh:
        json.dump(BASELINE_CONTRACT, fh, indent=2, sort_keys=True)

    return manifest_path, metadata_path, patterns_path, contract_path


# --------------------------------------------------------------------------------------
# Mutations. (id, description, expected check, mutate fn)
# --------------------------------------------------------------------------------------

def _append(root, rel, text):
    with open(os.path.join(root, rel), "a", encoding="utf-8") as fh:
        fh.write(text)


def _write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


MUTATIONS = [
    ("M01", "residential WAN public IP in prose", "K04",
     lambda r, m, d, c: _append(r, "docs/architecture.md", "\nEdge address 198.18.0.1 in use.\n")),

    ("M02", "RFC1918 address in prose", "K04",
     lambda r, m, d, c: _append(r, "docs/architecture.md", "\nThe node answers on 192.168.99.99.\n")),

    ("M03", "bare estate hostname in a comment", "K05",
     lambda r, m, d, c: _append(r, "docs/architecture.md", "\nObserved on alpha-node during the incident.\n")),

    ("M04", "un-substituted role identifier", "K13",
     lambda r, m, d, c: _append(r, "docs/architecture.md", "\nThe example-gpu node schedules research.\n")),

    ("M05", "internal domain reference", "K06",
     lambda r, m, d, c: _append(r, "docs/architecture.md", "\nPulls from registry.corp.example daily.\n")),

    ("M06", "SSH target with root and an address", "K07",
     lambda r, m, d, c: _append(r, "docs/architecture.md", "\nRun ssh root@192.168.99.31 to collect.\n")),

    ("M07", "personal email address", "K07",
     lambda r, m, d, c: _append(r, "SECURITY.md", "\nContact operator@fictional-corp.test for reports.\n")),

    ("M08", "absolute home path", "K08",
     lambda r, m, d, c: _append(r, "docs/architecture.md", "\nConfig at /home/exampleuser/.kube/config.\n")),

    ("M09", "MAC address in a table", "K09",
     lambda r, m, d, c: _append(r, "docs/architecture.md", "\n| nic | AA:BB:CC:DD:EE:FF |\n")),

    ("M10", "GitHub token committed", "K03",
     lambda r, m, d, c: _append(r, "docs/architecture.md",
                             "\nexport TOKEN=ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789\n")),

    ("M11", "private key block committed", "K03",
     lambda r, m, d, c: _write(r, "docs/key.md",
                            "# Key\n\n-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n")),

    ("M12", "private repository reference", "K10",
     lambda r, m, d, c: _append(r, "README.md", "\nSee example-private-repo for detail.\n")),

    ("M13", "internal branch reference", "K11",
     lambda r, m, d, c: _append(r, "docs/architecture.md", "\nMerged from feat/example-branch.\n")),

    ("M14", "unresolved placeholder left by the substitution pass", "K12",
     lambda r, m, d, c: _append(r, "docs/architecture.md", "\nOwner is <OWNER NAME> pending.\n")),

    ("M15", "work marker left in a shipped document", "K12",
     lambda r, m, d, c: _append(r, "docs/architecture.md", "\nTODO tighten this section.\n")),

    ("M16", "file present but absent from the manifest", "K02",
     lambda r, m, d, c: _write(r, "docs/stowaway.md", "# Stowaway\n\nNever approved.\n")),

    ("M17", "manifest record whose file was deleted", "K02",
     lambda r, m, d, c: os.remove(os.path.join(r, "docs/architecture.md"))),

    ("M18", "malformed manifest record", "K01",
     lambda r, m, d, c: open(m, "a", encoding="utf-8").write("broken | record | AS-IS\n")),

    ("M19", "unknown manifest classification", "K01",
     lambda r, m, d, c: open(m, "a", encoding="utf-8").write(
         "source/x.md | x.md | MAYBE | 2026-08-03\n")),

    ("M20", "missing LICENSE", "K14",
     lambda r, m, d, c: os.remove(os.path.join(r, "LICENSE"))),

    ("M21", "unrecognised LICENSE text", "K15",
     lambda r, m, d, c: _write(r, "LICENSE", "All rights reserved. Do not copy.\n")),

    ("M22", "missing release notes", "K14",
     lambda r, m, d, c: os.remove(os.path.join(r, "CHANGELOG.md"))),

    ("M23", "changelog with no released version", "K20",
     lambda r, m, d, c: _write(r, "CHANGELOG.md", "# Changelog\n\nUnreleased work only.\n")),

    ("M24", "declared diagram file missing", "K19",
     lambda r, m, d, c: os.remove(os.path.join(r, "docs/diagram.md"))),

    ("M35", "declared Mermaid block count does not match", "K19",
     lambda r, m, d, c: _write(r, "docs/diagram.md", "# Diagram\n\nno blocks here\n")),

    ("M36", "unrecognised Mermaid diagram type", "K19",
     lambda r, m, d, c: _write(r, "docs/diagram.md",
                               "# Diagram\n\n```mermaid\nnotADiagramType X --> Y\n```\n")),

    ("M25", "referenced image is empty", "K18",
     lambda r, m, d, c: _write(r, "images/pipeline.svg", "")),

    ("M26", "broken relative link", "K17",
     lambda r, m, d, c: _append(r, "README.md", "\nSee [the missing page](docs/nope.md).\n")),

    ("M27", "README first line is not a heading", "K16",
     lambda r, m, d, c: _write(r, "README.md",
                            "Intro paragraph with no heading.\n\n" + BASELINE_FILES["README.md"])),

    ("M28", "unbalanced fenced code block", "K16",
     lambda r, m, d, c: _append(r, "README.md", "\n```text\nunterminated\n")),

    ("M29", "incomplete repository metadata", "K22",
     lambda r, m, d, c: json.dump({"description": "", "topics": [], "homepage": "", "license": ""},
                               open(d, "w", encoding="utf-8"))),

    ("M30", "too few repository topics", "K22",
     lambda r, m, d, c: json.dump({**BASELINE_METADATA, "topics": ["sre"]},
                               open(d, "w", encoding="utf-8"))),

    ("M31", "em dash in repository description", "K22",
     lambda r, m, d, c: json.dump({**BASELINE_METADATA,
                                "description": "A platform — governed and evidence-first."},
                               open(d, "w", encoding="utf-8"))),

    ("M32", "duplicate document title across two files", "K23",
     lambda r, m, d, c: _write(r, "docs/architecture-copy.md", "# Architecture\n\nDuplicate owner.\n")),

    ("M33", "hardcoded credential assignment", "K03",
     lambda r, m, d, c: _append(r, "docs/architecture.md", "\npassword = SuperSecret123\n")),

    ("M34", "Discord webhook URL", "K03",
     lambda r, m, d, c: _append(r, "docs/architecture.md",
                             "\nhttps://discord.com/api/webhooks/1234567890/abcdefghijklmnop\n")),
]


def _run(tree_root, manifest, metadata, patterns, contract_path=None):
    contract = None
    if contract_path:
        with open(contract_path, encoding="utf-8") as fh:
            contract = json.load(fh)
    _, results = vp.run_gate(tree_root, manifest, metadata, patterns,
                             "all", None, contract)
    failed = {r.check for r in results if r.required and r.verdict != vp.PASS}
    return results, failed


def run_campaign() -> int:
    print("NetFRAME Public Release Gate: mutation campaign")
    print(f"  {len(MUTATIONS)} mutations, each must be caught by its expected check\n")

    escapes, wrong_check, control_failures = [], [], []

    # Control 1: the unmutated baseline must pass.
    with tempfile.TemporaryDirectory() as tmp:
        root = os.path.join(tmp, "tree")
        os.makedirs(root)
        manifest, metadata, patterns, contract = build_baseline(root)
        results, failed = _run(root, manifest, metadata, patterns, contract)
        if failed:
            control_failures.append(sorted(failed))
            print("  CONTROL FAIL  baseline tree does not pass:")
            for r in results:
                if r.required and r.verdict != vp.PASS:
                    print(f"      {r.check} {r.title} {r.note}")
                    for f in r.findings[:5]:
                        print(f.render())
        else:
            print(f"  CONTROL PASS  baseline publishes cleanly ({len(results)} checks)\n")

    for mid, desc, expected, mutate in MUTATIONS:
        with tempfile.TemporaryDirectory() as tmp:
            root = os.path.join(tmp, "tree")
            os.makedirs(root)
            manifest, metadata, patterns, contract = build_baseline(root)
            try:
                mutate(root, manifest, metadata, contract)
            except Exception as exc:  # noqa: BLE001
                print(f"  ERROR  {mid} could not be applied: {exc}")
                escapes.append(mid)
                continue
            _, failed = _run(root, manifest, metadata, patterns, contract)
            if not failed:
                print(f"  ESCAPE {mid}  {desc}  (expected {expected}, nothing caught it)")
                escapes.append(mid)
            elif expected not in failed:
                print(f"  WRONG  {mid}  {desc}  (expected {expected}, caught by {sorted(failed)})")
                wrong_check.append(mid)
            else:
                print(f"  caught {mid}  {desc}  -> {expected}")

    print()
    total = len(MUTATIONS)
    caught = total - len(escapes) - len(wrong_check)
    print(f"  {caught}/{total} mutations caught by the expected check")
    if control_failures:
        print(f"  CONTROL FAILURE: baseline did not pass ({control_failures})")
    if escapes:
        print(f"  ESCAPES: {escapes}")
    if wrong_check:
        print(f"  CAUGHT BY THE WRONG CHECK: {wrong_check}")

    ok = not escapes and not wrong_check and not control_failures
    print("\n  CAMPAIGN PASS" if ok else "\n  CAMPAIGN FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(run_campaign())
