"""Append-only JSONL audit log.

Every diagnostic run and every executed/confirmed command is recorded to
/var/log/jarvis-oncall/audit.jsonl for after-the-fact review.
"""
import json
import os
import time

LOG_DIR = os.environ.get("ONCALL_LOG_DIR", "/var/log/jarvis-oncall")
LOG_FILE = os.path.join(LOG_DIR, "audit.jsonl")


def _ensure_dir():
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
    except OSError:
        pass


def record(event: str, **fields):
    """Write one audit line. `event` e.g. 'proposed', 'executed', 'confirmed',
    'denied', 'error'. Fields typically: user, node, tool, args, rc, output."""
    _ensure_dir()
    entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "event": event}
    entry.update(fields)
    line = json.dumps(entry, ensure_ascii=False, default=str)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        # Never let audit failure crash the bot; surface to stderr instead.
        import sys
        print(f"AUDIT WRITE FAILED: {line}", file=sys.stderr)
