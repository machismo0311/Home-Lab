"""NetFRAME Public Release Gate: the policy.

SINGLE OWNER. This module is the only place that defines what may be published.
`verify-publication` executes this policy; it does not extend, relax, or reinterpret it.
Nothing else in the repository may define a publication rule.

Design rules, in the platform's own idiom:

  Fail closed.      Absence of a verdict is a failure, never a pass.
  Deterministic.    No clock, no randomness, no network, no environment lookups.
                    The same tree must produce the same verdicts and the same bytes.
  Evidence first.   A finding names the file, the line, and the matched text.
  No shortcuts.     A check that cannot run is a FAILED check, not a skipped one.

Every check declares an id, a title, and whether it is REQUIRED. A REQUIRED check that
reports ERROR fails the gate. There is deliberately no severity below "fails the gate"
for a REQUIRED check: a gate you can satisfy without changing the condition is decoration.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Iterable

# --------------------------------------------------------------------------------------
# Verdict model
# --------------------------------------------------------------------------------------

PASS = "PASS"
FAIL = "FAIL"
ERROR = "ERROR"  # the check itself could not complete: treated as FAIL, reported distinctly
NA = "N/A"       # out of contract for this scope. Never a silent skip: always reported with a reason

# Two scopes, because a repository and the content published from it are different objects.
# ENVELOPE checks the repository itself: does it carry a licence, a changelog, a readable
# front page. CONTENT checks what is being published: is it safe, complete and consistent.
# A check belongs to exactly one scope, declared here, so nothing is excluded by filtering
# output after the fact.
SCOPE_ENVELOPE = "envelope"
SCOPE_CONTENT = "content"

SCOPE_REASON = {
    SCOPE_ENVELOPE: "repository-level requirement; owned by the repository root, not by published content",
    SCOPE_CONTENT: "publication-content requirement; owned by the published subtrees, not by the repository",
}


@dataclass(frozen=True)
class Finding:
    check: str
    path: str
    line: int
    excerpt: str
    detail: str

    def render(self) -> str:
        loc = f"{self.path}:{self.line}" if self.line else self.path
        return f"    {loc}  {self.detail}  [{self.excerpt}]"


@dataclass
class CheckResult:
    check: str
    title: str
    required: bool
    verdict: str
    findings: list[Finding] = field(default_factory=list)
    note: str = ""
    scope: str = SCOPE_CONTENT

    @property
    def ok(self) -> bool:
        return self.verdict == PASS


# --------------------------------------------------------------------------------------
# Redaction vocabulary. Shared with the substitution pass so the two cannot drift.
# --------------------------------------------------------------------------------------

# Estate vocabulary is NOT hardcoded here. See docs/PUBLICATION-CONTRACT.md for the format:
# a denylist gate necessarily contains what it denies, so shipping a real estate's
# hostnames inside the tool would publish the target list. Shapes stay in code; literals
# load from a patterns file that is not published. Absent a patterns file, the gate fails
# closed rather than silently skipping the checks it cannot perform.

class EstatePatterns:
    """Estate-specific literals, loaded from JSON. Never hardcoded."""

    def __init__(self, hostnames=None, domains=None, addresses=None,
                 private_repos=None, role_map=None):
        self.hostnames = sorted(hostnames or [])
        self.domains = sorted(domains or [])
        self.addresses = sorted(addresses or [])
        self.private_repos = sorted(private_repos or [])
        self.role_map = dict(role_map or {})

    @classmethod
    def load(cls, path: str) -> "EstatePatterns":
        with open(path, "r", encoding="utf-8") as fh:
            d = json.load(fh)
        return cls(d.get("hostnames"), d.get("domains"), d.get("addresses"),
                   d.get("private_repos"), d.get("role_map"))

    def _alt(self, items):
        return "|".join(re.escape(i) for i in items if i)

    def hostname_re(self):
        return _rx(r"\b(?:%s)\b" % self._alt(self.hostnames)) if self.hostnames else None

    def domain_re(self):
        if not self.domains:
            return None
        return _rx(r"\b[a-z0-9-]+\.(?:%s)\b|\b(?:%s)\b"
                   % (self._alt(self.domains), self._alt(self.domains)))

    def address_re(self):
        return re.compile(r"\b(?:%s)\b" % self._alt(self.addresses)) if self.addresses else None

    def private_repo_re(self):
        return _rx(r"\b(?:%s)\b" % self._alt(self.private_repos)) if self.private_repos else None

    def role_re_pairs(self):
        return [(_rx(r"\b%s\b" % re.escape(k)), v) for k, v in sorted(self.role_map.items())]


# Addresses that are legitimate in public documentation.
ADDRESS_ALLOWLIST = {
    "127.0.0.1",
    "0.0.0.0",
    "255.255.255.255",
    "8.8.8.8",
    "1.1.1.1",
    "192.0.2.1",  # TEST-NET-1, RFC 5737
    "198.51.100.1",  # TEST-NET-2
    "203.0.113.1",  # TEST-NET-3
}

# Files whose content is exempt from prose-level checks (binary-ish or generated).
BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".pdf", ".ico", ".woff", ".woff2",
    ".zip", ".gz", ".tar", ".cast",
}

SKIP_DIRS = {".git", "__pycache__", ".ruff_cache", "node_modules", ".pytest_cache"}


# --------------------------------------------------------------------------------------
# Pattern policy. Each entry: (check id, compiled pattern, human detail)
# --------------------------------------------------------------------------------------

def _rx(p: str) -> re.Pattern[str]:
    return re.compile(p, re.IGNORECASE)


# K04 addressing
RFC1918 = re.compile(
    r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|192\.168\.\d{1,3}\.\d{1,3}"
    r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b"
)
ANY_IPV4 = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")



# K07 identity
EMAIL = _rx(r"\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b")
EMAIL_ALLOWED = _rx(r"\b(?:example|noreply|user|someone)@")
SSH_TARGET = _rx(r"\broot@(?:\d{1,3}\.){3}\d{1,3}\b|\bssh\s+root@")

# K08 filesystem paths
ABS_PATHS = _rx(r"(?:/home/[a-z0-9._-]+|/root/\.?[a-z]|/datastore\b|/mnt/(?:bulk|tank)\b)")

# K09 hardware identity
MAC = re.compile(r"\b(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}\b")
SERIAL = _rx(r"\bsvc\s+[A-Z0-9]{7}\b|\bservice\s+tag[: ]+[A-Z0-9]{7}\b")

# K03 secrets
SECRETS = [
    (_rx(r"\bgh[pousr]_[A-Za-z0-9]{16,}"), "GitHub token"),
    (_rx(r"\bAKIA[0-9A-Z]{16}\b"), "AWS access key id"),
    (_rx(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA |PGP )?PRIVATE KEY-----"), "private key block"),
    (_rx(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"), "Slack token"),
    (_rx(r"https://discord(?:app)?\.com/api/webhooks/\S+"), "Discord webhook"),
    (_rx(r"\bBearer\s+[A-Za-z0-9._~+/-]{20,}"), "bearer token"),
    (_rx(r"(?:password|passwd|api[_-]?key|secret)\s*[:=]\s*[\"']?(?!<|\{\{|\$|REDACTED|xxx|\*)[A-Za-z0-9._/+-]{8,}"),
     "hardcoded credential"),
]


# K11 internal branch / PR references
#
# The first draft matched any `<word>/<word>` token, which flagged the relative link
# `docs/architecture.md` in a clean baseline tree. A branch name and a relative path are
# lexically identical, so the rule must key off git *context* rather than off shape, or it
# becomes a rule people learn to ignore. That false positive was fixed, not accepted.
INTERNAL_REFS = _rx(
    r"\brefs/heads/[a-z0-9._/-]+"
    r"|\borigin/(?!master\b|main\b)[a-z0-9._/-]+"
    r"|\b(?:branch|merged\s+from|cherry-picked\s+from|rebased\s+onto|checkout)\s+"
    r"[`\"']?(?:tooling|docs|feat|fix|wip|spike|chore|registry|hotfix)/[a-z0-9._-]+"
    r"|\bPR\s*#\d+\b|\b(?:Home-Lab|internal)\s*#\d+\b"
)

# K12 unresolved placeholders and work markers
PLACEHOLDER = re.compile(r"<[A-Z][A-Z0-9 _-]{2,}>|\bREDACTED\b|\bXXX\b")
WORK_MARKER = re.compile(r"\b(?:TODO|FIXME|HACK|TBD)\b")


@dataclass(frozen=True)
class PatternRule:
    check: str
    title: str
    patterns: list[tuple[re.Pattern[str], str]]
    required: bool = True
    scope: str = SCOPE_CONTENT


PATTERN_RULES: list[PatternRule] = [
    PatternRule("K03", "No secrets or credentials", SECRETS),
    PatternRule("K08", "No absolute local paths", [(ABS_PATHS, "absolute local path")]),
    PatternRule("K09", "No hardware identifiers", [(MAC, "MAC address"), (SERIAL, "service tag")]),
    PatternRule("K11", "No internal branch or PR references", [(INTERNAL_REFS, "internal ref")]),
]


def is_text_file(name: str) -> bool:
    return not any(name.lower().endswith(s) for s in BINARY_SUFFIXES)


def address_findings(check: str, path: str, text: str) -> Iterable[Finding]:
    """K04. RFC1918 always fails. Public IPv4 fails unless explicitly allowlisted."""
    for i, line in enumerate(text.splitlines(), 1):
        for m in ANY_IPV4.finditer(line):
            ip = m.group(0)
            if ip in ADDRESS_ALLOWLIST:
                continue
            octets = ip.split(".")
            if any(not o.isdigit() or int(o) > 255 for o in octets):
                continue  # not an address (version string, etc.)
            kind = "RFC1918 address" if RFC1918.fullmatch(ip) else "public IP address"
            yield Finding(check, path, i, ip, kind)


def identity_findings(check: str, path: str, text: str) -> Iterable[Finding]:
    """K07. Emails and SSH targets, minus documented example forms."""
    for i, line in enumerate(text.splitlines(), 1):
        for m in EMAIL.finditer(line):
            if EMAIL_ALLOWED.search(m.group(0)):
                continue
            yield Finding(check, path, i, m.group(0), "email address")
        for m in SSH_TARGET.finditer(line):
            yield Finding(check, path, i, m.group(0), "SSH target")


def placeholder_findings(check: str, path: str, text: str) -> Iterable[Finding]:
    """K12. An unresolved placeholder means the substitution pass did not finish."""
    for i, line in enumerate(text.splitlines(), 1):
        for m in PLACEHOLDER.finditer(line):
            yield Finding(check, path, i, m.group(0), "unresolved placeholder")
        for m in WORK_MARKER.finditer(line):
            yield Finding(check, path, i, m.group(0), "work marker")


# --------------------------------------------------------------------------------------
# Structural requirements
# --------------------------------------------------------------------------------------

REQUIRED_FILES = [
    "README.md",
    "LICENSE",
    "CHANGELOG.md",
    "SECURITY.md",
]

# K19 diagram contract. Deliberately NOT a diagram framework: it declares the diagram-bearing
# files that must exist and how many fenced Mermaid blocks each must contain, and it validates
# those blocks structurally. It does not render, and it does not discover diagrams on its own.
#
# The earlier version hardcoded "images/pipeline.svg", which no published artifact ever
# contained. A requirement nothing satisfies is a check that can only be ignored, so it was
# replaced rather than satisfied with a placeholder file.
DEFAULT_DIAGRAM_CONTRACT: dict[str, int] = {}

# Fenced blocks must open with one of these. Keeps validation narrow and offline.
MERMAID_DIAGRAM_TYPES = (
    "graph", "flowchart", "sequenceDiagram", "stateDiagram", "stateDiagram-v2",
    "classDiagram", "erDiagram", "journey", "gantt", "pie", "mindmap", "timeline",
    "gitGraph", "quadrantChart", "requirementDiagram", "C4Context",
)

# A recognised licence must contain one of these markers.
LICENSE_MARKERS = ("Apache License", "MIT License", "BSD", "Mozilla Public License", "GNU")

# Repository metadata that must be complete before publication.
REQUIRED_METADATA_FIELDS = ("description", "topics", "homepage", "license")
MIN_TOPICS = 5
MAX_DESCRIPTION = 350
