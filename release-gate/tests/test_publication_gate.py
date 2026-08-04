#!/usr/bin/env python3
"""Unit tests for the NetFRAME Public Release Gate.

The mutation campaign proves the gate catches unsafe *content*. These tests prove the
properties the campaign cannot: that the gate fails closed on its own failures, that it
refuses to report success when a check did not run, that it is deterministic, and that
the one false positive it produced stays fixed.

Runs without pytest so it works on a bare interpreter, in CI, and on a fresh clone.
"""

from __future__ import annotations

import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.abspath(os.path.join(HERE, "..", "scripts"))
sys.path.insert(0, SCRIPTS)


def _load(name, filename):
    path = os.path.join(SCRIPTS, filename)
    loader = importlib.machinery.SourceFileLoader(name, path)
    spec = importlib.util.spec_from_loader(name, loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


vp = _load("netframe_publication_gate", "verify-publication")
mut = _load("publication_mutations", "publication_mutations.py")
import publication_policy as policy  # noqa: E402

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, bool(cond), detail))


def baseline(tmp):
    root = os.path.join(tmp, "tree")
    os.makedirs(root, exist_ok=True)
    manifest, metadata, patterns, contract = mut.build_baseline(root)
    return root, manifest, metadata, patterns, contract


def quiet(fn, *a, **kw):
    """CLI entry points print by design; tests assert on exit codes, not on stdout."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        return fn(*a, **kw)


def run(root, manifest, metadata, patterns=None, contract_path=None):
    contract = None
    if contract_path:
        contract = json.load(open(contract_path, encoding="utf-8"))
    _, results = vp.run_gate(root, manifest, metadata, patterns, "all", None, contract)
    failed = {r.check for r in results if r.required and r.verdict != vp.PASS}
    return results, failed


# ---------------------------------------------------------------------------------------
# Fail-closed properties
# ---------------------------------------------------------------------------------------

def test_clean_tree_passes():
    with tempfile.TemporaryDirectory() as tmp:
        root, m, d, ptn, ctr = baseline(tmp)
        _, failed = run(root, m, d, ptn, ctr)
        check("clean baseline publishes", not failed, str(sorted(failed)))


def test_missing_manifest_refuses():
    """No allowlist means no publication. Default deny, not default allow."""
    with tempfile.TemporaryDirectory() as tmp:
        root, _, d, ptn, ctr = baseline(tmp)
        _, failed = run(root, None, d, ptn, ctr)
        check("missing manifest refuses publication", "K01" in failed and "K02" in failed,
              str(sorted(failed)))


def test_unreadable_manifest_refuses():
    with tempfile.TemporaryDirectory() as tmp:
        root, _, d, ptn, ctr = baseline(tmp)
        _, failed = run(root, os.path.join(tmp, "nonexistent-manifest.txt"), d, ptn, ctr)
        check("unreadable manifest refuses publication", "K01" in failed, str(sorted(failed)))


def test_missing_metadata_refuses():
    with tempfile.TemporaryDirectory() as tmp:
        root, m, _, ptn, ctr = baseline(tmp)
        _, failed = run(root, m, None, ptn, ctr)
        check("missing repo metadata refuses publication", "K22" in failed, str(sorted(failed)))


def test_check_raising_is_error_not_skip():
    """A check that throws must be recorded as ERROR and fail the gate, never skipped."""
    with tempfile.TemporaryDirectory() as tmp:
        root, m, d, ptn, ctr = baseline(tmp)
        original = vp.check_addresses

        def exploding(_tree):
            raise RuntimeError("induced failure")

        vp.check_addresses = exploding
        try:
            results, failed = run(root, m, d, ptn, ctr)
        finally:
            vp.check_addresses = original
        k04 = [r for r in results if r.check == "K04"]
        check("raising check becomes ERROR", bool(k04) and k04[0].verdict == vp.ERROR,
              k04[0].verdict if k04 else "absent")
        check("raising check fails the gate", "K04" in failed, str(sorted(failed)))


def test_no_silent_pass_when_a_check_vanishes():
    """K99: if a registered check does not report, the gate must refuse rather than pass."""
    with tempfile.TemporaryDirectory() as tmp:
        root, m, d, ptn, ctr = baseline(tmp)
        original = vp.registered_checks

        def truncated(tree, manifest, metadata, rt, ep=None, contract=None):
            full = original(tree, manifest, metadata, rt, ep, contract)
            # simulate a check silently disappearing after registration
            kept = [c for c in full if c[0] != "K04"]
            return kept + [("K04", "content", lambda: None)]  # registered, returns no verdict

        vp.registered_checks = truncated
        try:
            results, failed = run(root, m, d, ptn, ctr)
        finally:
            vp.registered_checks = original
        check("vanished verdict fails the gate", bool(failed), str(sorted(failed)))


def test_missing_tree_raises_not_passes():
    try:
        vp.run_gate("/nonexistent/path/for/gate/test", None, None)
        check("missing tree refuses", False, "run_gate returned normally")
    except Exception:
        check("missing tree refuses", True)


# ---------------------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------------------

def test_determinism_same_bytes_twice():
    with tempfile.TemporaryDirectory() as tmp:
        root, m, d, ptn, ctr = baseline(tmp)
        r1, _ = run(root, m, d, ptn, ctr)
        r2, _ = run(root, m, d, ptn, ctr)
        s1 = [(r.check, r.verdict, len(r.findings)) for r in r1]
        s2 = [(r.check, r.verdict, len(r.findings)) for r in r2]
        check("two runs produce identical verdicts", s1 == s2)


def test_tree_digest_stable():
    with tempfile.TemporaryDirectory() as tmp:
        root, _, _, ptn, ctr = baseline(tmp)
        a = vp.tree_digest(vp.Tree(root))
        b = vp.tree_digest(vp.Tree(root))
        check("tree digest is reproducible", a == b, f"{a[:12]} vs {b[:12]}")


def test_findings_are_ordered():
    """Deterministic output requires a stable file order."""
    with tempfile.TemporaryDirectory() as tmp:
        root, _, _, ptn, ctr = baseline(tmp)
        t = vp.Tree(root)
        check("tree file order is sorted", t.files == sorted(t.files))


# ---------------------------------------------------------------------------------------
# Regression: the false positive the gate produced on its first run
# ---------------------------------------------------------------------------------------

def test_relative_doc_link_is_not_a_branch_reference():
    """`docs/architecture.md` is a relative link, not a branch. The first draft of K11
    flagged it, which would have taught readers that red is negotiable."""
    for legitimate in ("see docs/architecture.md", "[arch](docs/architecture.md)",
                       "images/pipeline.svg", "scripts/verify-publication"):
        hits = list(policy.INTERNAL_REFS.finditer(legitimate))
        check(f"K11 ignores {legitimate!r}", not hits, str([h.group(0) for h in hits]))


def test_real_branch_reference_still_caught():
    for hostile in ("merged from feat/example-branch", "refs/heads/wip/thing",
                    "origin/spike/foo", "PR #42"):
        hits = list(policy.INTERNAL_REFS.finditer(hostile))
        check(f"K11 catches {hostile!r}", bool(hits))


def test_documentation_addresses_allowed():
    """RFC 5737 documentation ranges and loopback must not be flagged, or authors will
    have no way to write an example."""
    for ok in ("127.0.0.1", "192.0.2.1", "203.0.113.1", "0.0.0.0"):
        f = list(policy.address_findings("K04", "x.md", f"listen on {ok}"))
        check(f"K04 allows {ok}", not f)


def test_estate_addresses_still_caught():
    for bad in ("192.168.99.99", "10.0.0.5", "172.16.4.9", "198.18.0.1"):
        f = list(policy.address_findings("K04", "x.md", f"host at {bad}"))
        check(f"K04 catches {bad}", bool(f))


def test_version_strings_not_treated_as_addresses():
    f = list(policy.address_findings("K04", "x.md", "Proxmox VE 9.2.3 and kernel 6.14.11"))
    check("K04 ignores version strings", not f, str([x.excerpt for x in f]))


# ---------------------------------------------------------------------------------------
# Manifest semantics
# ---------------------------------------------------------------------------------------

def test_manifest_rejects_unknown_classification():
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "m.txt")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("a.md | a.md | MAYBE | 2026-08-03\n")
        man = vp.Manifest(p)
        check("manifest rejects unknown classification", bool(man.errors), str(man.errors))


def test_manifest_requires_approval_date():
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "m.txt")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("a.md | a.md | AS-IS | \n")
        man = vp.Manifest(p)
        check("manifest requires an approval date", bool(man.errors), str(man.errors))


def test_manifest_ignores_comments_and_blanks():
    with tempfile.TemporaryDirectory() as tmp:
        p = os.path.join(tmp, "m.txt")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write("# comment\n\na.md | a.md | AS-IS | 2026-08-03\n")
        man = vp.Manifest(p)
        check("manifest parses cleanly", not man.errors and len(man.records) == 1,
              f"{man.errors} {len(man.records)}")


# ---------------------------------------------------------------------------------------
# Emitted evidence
# ---------------------------------------------------------------------------------------

def test_emitted_manifest_records_hashes():
    with tempfile.TemporaryDirectory() as tmp:
        root, m, d, ptn, ctr = baseline(tmp)
        out = os.path.join(tmp, "published-manifest.json")
        rc = quiet(vp.main, ["--tree", root, "--manifest", m, "--metadata", d, "--patterns", ptn,
                             "--diagram-contract", ctr, "--emit-manifest", out, "--json"])
        ok = rc == vp.EXIT_OK and os.path.isfile(out)
        payload = json.load(open(out, encoding="utf-8")) if ok else {}
        check("gate emits a published manifest on pass",
              ok and "tree_digest" in payload and len(payload.get("files", {})) > 0)


def test_no_manifest_emitted_on_failure():
    with tempfile.TemporaryDirectory() as tmp:
        root, m, d, ptn, ctr = baseline(tmp)
        with open(os.path.join(root, "docs/architecture.md"), "a", encoding="utf-8") as fh:
            fh.write("\nnode at 192.168.99.5\n")
        out = os.path.join(tmp, "should-not-exist.json")
        rc = quiet(vp.main, ["--tree", root, "--manifest", m, "--metadata", d, "--patterns", ptn,
                             "--diagram-contract", ctr, "--emit-manifest", out, "--json"])
        check("no evidence emitted when the gate fails",
              rc == vp.EXIT_FAILED and not os.path.exists(out))


def test_exit_codes():
    with tempfile.TemporaryDirectory() as tmp:
        root, m, d, ptn, ctr = baseline(tmp)
        rc_ok = quiet(vp.main, ["--tree", root, "--manifest", m, "--metadata", d, "--patterns", ptn,
                                "--diagram-contract", ctr, "--json"])
        check("exit 0 on pass", rc_ok == vp.EXIT_OK, str(rc_ok))
        rc_missing = quiet(vp.main, [])
        check("exit 2 when no tree given", rc_missing == vp.EXIT_INTERNAL, str(rc_missing))


# ---------------------------------------------------------------------------------------
# Scope contract: an inapplicable check must be REPORTED as N/A, never silently dropped
# ---------------------------------------------------------------------------------------

def test_scope_marks_inapplicable_checks_na_not_absent():
    with tempfile.TemporaryDirectory() as tmp:
        root, m, d, ptn, ctr = baseline(tmp)
        contract = json.load(open(ctr, encoding="utf-8"))
        _, results = vp.run_gate(root, m, d, ptn, "content", None, contract)
        ids = {r.check for r in results}
        na = {r.check for r in results if r.verdict == vp.NA}
        check("envelope checks reported as N/A under content scope",
              {"K14", "K15", "K16", "K20", "K22"} <= na, str(sorted(na)))
        check("no registered check vanished", "K14" in ids and "K99" in ids)
        for r in results:
            if r.verdict == vp.NA:
                check(f"N/A {r.check} states a reason", bool(r.note))


def test_na_does_not_count_as_failure():
    with tempfile.TemporaryDirectory() as tmp:
        root, m, d, ptn, ctr = baseline(tmp)
        contract = json.load(open(ctr, encoding="utf-8"))
        _, results = vp.run_gate(root, m, d, ptn, "content", None, contract)
        failed = [r for r in results if r.required and r.verdict not in (vp.PASS, vp.NA)]
        check("content scope passes on a clean baseline", not failed, str([r.check for r in failed]))


def test_include_restricts_the_scanned_tree():
    """Excluded paths must never be read, so they cannot produce a finding to discard."""
    with tempfile.TemporaryDirectory() as tmp:
        root, m, d, ptn, ctr = baseline(tmp)
        os.makedirs(os.path.join(root, "estate"), exist_ok=True)
        with open(os.path.join(root, "estate", "leak.md"), "w", encoding="utf-8") as fh:
            fh.write("host at 192.168.10.5\n")
        t_all = vp.Tree(root)
        t_inc = vp.Tree(root, ["docs"])
        check("unrestricted tree sees the excluded file",
              any(f.startswith("estate/") for f in t_all.files))
        check("include filter excludes it from the file set",
              not any(f.startswith("estate/") for f in t_inc.files))


def test_diagram_contract_requires_declaration():
    """K19 fails closed when no contract is supplied: it cannot verify what was not declared."""
    with tempfile.TemporaryDirectory() as tmp:
        root, m, d, ptn, ctr = baseline(tmp)
        _, results = vp.run_gate(root, m, d, ptn, "content", None, None)
        k19 = [r for r in results if r.check == "K19"]
        check("K19 fails without a contract", bool(k19) and k19[0].verdict == vp.FAIL,
              k19[0].verdict if k19 else "absent")


def main() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        try:
            t()
        except Exception as exc:  # noqa: BLE001
            RESULTS.append((t.__name__, False, f"raised {type(exc).__name__}: {exc}"))
    failed = [r for r in RESULTS if not r[1]]
    for name, ok, detail in RESULTS:
        if not ok:
            print(f"FAIL {name}  {detail}")
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} assertions passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
