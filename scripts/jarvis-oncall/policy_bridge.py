"""Bridge to the shared NetFRAME policy engine and hash-chained audit ledger.

This module contains NO policy rules. It imports the single shared engine from
/opt/netframe-monitor (NF-AIOPS-004: one safety boundary, one policy engine, one
audit trail) so the Discord bot cannot drift from the reports and the console.

Two responsibilities:

  screen_llm(text)          - enforce the prohibited-recommendation policy on any
                              MODEL-GENERATED prose before it is sent to Discord.
                              The bot's own deterministic messages (the confirm
                              prompt, tool banners) are NOT screened: they are code,
                              not model output, and the confirm prompt legitimately
                              names the exact command the gateway is proposing.

  audit_mutation(event, **) - mirror every mutation-lifecycle event (await_confirm,
                              confirmed, cancelled, denied, executed_mutation) into
                              the hash-chained, Loki-mirrored ledger with the
                              APPROVER'S identity, alongside the bot's local JSONL.

Degradation: if the shared engine is unavailable (netframe-monitor not installed),
LLM prose is still delivered but stamped UNSCREENED - loud, never silent - and the
failure itself is recorded locally. The bot must not die because the monitor moved.
"""
import os
import sys

NETFRAME_BASE = os.environ.get("NETFRAME_BASE", "/opt/netframe-monitor")
if NETFRAME_BASE not in sys.path:
    sys.path.insert(0, NETFRAME_BASE)

import audit as local_audit  # noqa: E402 - after the sys.path setup; the bot's own JSONL


def screen_llm(text: str) -> str:
    """Deterministic policy screen for model-generated prose. Returns the text an
    operator may see; blocked lines are replaced by visible notices and the
    originals land in the hash-chained ledger (source='discord')."""
    if not text:
        return text
    try:
        import netframe_policy
        screened, _blocked = netframe_policy.enforce(text, source="discord")
        return screened
    except Exception as e:  # noqa: BLE001 - loud, never silent, never fatal
        local_audit.record("policy_screen_unavailable", error=str(e))
        return (text + "\n\n⚠️ **UNSCREENED**: the shared policy engine was "
                "unavailable, so this answer was NOT checked against Jarvis policy. "
                "Treat any recommendation above as unverified.")


def audit_mutation(event: str, approver_id=None, approver_name=None, **fields):
    """Record a mutation-lifecycle event to BOTH audit trails.

    The hash-chained ledger is the authoritative one (tamper-evident, Loki-mirrored,
    what the weekly chief report reads); the local JSONL stays for quick grepping.
    approver_id/approver_name is the Discord identity whose explicit reply authorised
    (or declined) the action - the 'approval identity' link in the required chain.
    """
    local_audit.record(event, user=approver_id, **fields)
    try:
        import netframe_audit
        netframe_audit.record(f"oncall_{event}", source="discord",
                              approver_id=approver_id, approver_name=approver_name,
                              **fields)
    except Exception as e:  # noqa: BLE001
        local_audit.record("ledger_mirror_failed", event=event, error=str(e))
