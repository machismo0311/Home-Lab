#!/usr/bin/env python3
"""Jarvis On-Call — Discord bot for troubleshooting the km-cluster homelab.

Phase 1 (this file): authentication + channel gate + llm_router round-trip with
tool-calling. When the model requests a tool, the bot REPORTS the proposed call
and audit-logs it as 'proposed' — it does not execute anything on nodes yet.
Read-only execution arrives in Phase 2; the restart_service confirm-and-execute
flow in Phase 3.

Security invariants already enforced here:
- Only ALLOWED_USER_ID is ever answered; everyone else is ignored (and logged).
- The bot only listens in DMs with that user and/or one CHANNEL_ID.
- The model can only ever name a whitelisted tool (see tools.py) — never a raw
  shell string.
"""
import asyncio
import json
import logging
import os

import discord

from router_client import complete
from prompts import system_prompt
from tools import TOOL_SCHEMAS, render_call, is_mutating
from policy_bridge import screen_llm, audit_mutation
from executors import run_readonly
from registry import registry
import ssh
import audit

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("jarvis-oncall")

ALLOWED_USER_ID = int(os.environ.get("ALLOWED_USER_ID", "0"))
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "0"))  # 0 = DMs only
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", "")
MAX_STEPS = int(os.environ.get("ONCALL_MAX_STEPS", "4"))  # tool→analyze rounds per message
CONFIRM_TIMEOUT = int(os.environ.get("ONCALL_CONFIRM_TIMEOUT", "60"))  # seconds to wait for "yes"

MAX_DISCORD = 1900  # leave headroom under Discord's 2000-char limit
AFFIRMATIVE = {"yes", "y", "do it", "doit", "confirm", "proceed", "go", "yep", "yeah"}

# Channels with a restart confirmation in flight — on_message suppresses normal
# handling here so the pending wait_for consumes the operator's "yes"/"no".
_awaiting_confirmation: set[int] = set()


def _parse_call(tc: dict) -> tuple[str, dict]:
    fn = tc.get("function", {})
    name = fn.get("name", "?")
    try:
        args = json.loads(fn.get("arguments") or "{}")
    except Exception:
        args = {}
    return name, args


def _authorized(message: discord.Message) -> bool:
    if message.author.id != ALLOWED_USER_ID:
        return False
    is_dm = isinstance(message.channel, discord.DMChannel)
    if is_dm:
        return True
    return CHANNEL_ID != 0 and message.channel.id == CHANNEL_ID


async def _send(channel, text: str):
    """Send text, chunked to respect Discord's message limit."""
    text = text or "(no content)"
    for i in range(0, len(text), MAX_DISCORD):
        await channel.send(text[i : i + MAX_DISCORD])


class OnCallClient(discord.Client):
    async def on_ready(self):
        log.info("Logged in as %s (id=%s); allowed user=%s channel=%s",
                 self.user, self.user.id, ALLOWED_USER_ID, CHANNEL_ID or "DM-only")

    async def on_message(self, message: discord.Message):
        if message.author.id == self.user.id:
            return
        if not _authorized(message):
            if message.author.id != self.user.id:
                log.warning("Ignored message from unauthorized user id=%s", message.author.id)
                audit.record("ignored", user=message.author.id,
                             channel=getattr(message.channel, "id", None))
            return
        # A restart confirmation is pending in this channel — let the waiting
        # coroutine handle this reply instead of starting a new request.
        if message.channel.id in _awaiting_confirmation:
            return
        content = message.content.strip()
        if not content:
            return

        async with message.channel.typing():
            try:
                await self._handle(message, content)
            except Exception as e:
                log.exception("handler error")
                audit.record("error", user=message.author.id, error=str(e))
                await _send(message.channel, f"⚠️ Error talking to llm_router: `{e}`")

    async def _handle(self, message: discord.Message, content: str):
        user = message.author.id
        channel = message.channel
        messages = [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": content},
        ]

        for _ in range(MAX_STEPS):
            reply = await complete(messages, tools=TOOL_SCHEMAS)
            tool_calls = reply.get("tool_calls") or []

            if not tool_calls:
                await _send(channel, screen_llm(reply.get("content")) or "(no response)")
                return

            # Record the assistant's tool request so the follow-up turn has context.
            messages.append({
                "role": "assistant",
                "content": reply.get("content") or "",
                "tool_calls": tool_calls,
            })

            for tc in tool_calls:
                name, args = _parse_call(tc)
                tcid = tc.get("id", "")

                if is_mutating(name):
                    result = await self._confirm_and_restart(message, args)
                    messages.append({"role": "tool", "tool_call_id": tcid,
                                     "name": name, "content": result})
                    continue

                await _send(channel, f"🔧 `{render_call(name, args)}`")
                ok, text = await run_readonly(name, args)
                audit.record("executed" if ok else "denied", user=user, tool=name,
                             args=args, ok=ok, output=text[:2000])
                messages.append({
                    "role": "tool", "tool_call_id": tcid, "name": name,
                    "content": text if ok else f"TOOL ERROR: {text}",
                })

        # Ran out of steps — ask for a final answer with no more tools.
        messages.append({"role": "user",
                         "content": "Stop calling tools. Give your best diagnosis and recommendation now."})
        final = await complete(messages, tools=None)
        await _send(channel, screen_llm(final.get("content")) or "(no further analysis)")

    async def _confirm_and_restart(self, message: discord.Message, args: dict) -> str:
        """Confirm-then-execute for restart_service. Returns a tool-result string
        (fed back to the model) describing what happened. Posts operator-facing
        messages directly. NEVER runs without an explicit affirmative reply."""
        user = message.author.id
        channel = message.channel
        node = registry.get(args.get("node", ""))
        unit = args.get("unit", "")

        # --- validation: refuse (no prompt) if the target is illegal ---
        if node is None or not node.reachable:
            audit.record("denied", user=user, tool="restart_service", args=args,
                         reason="unknown/unreachable node")
            return f"REFUSED: node '{args.get('node')}' is unknown or unreachable."
        if not unit:
            return "REFUSED: restart_service requires a 'unit'."
        if not node.may_restart(unit):
            audit.record("denied", user=user, tool="restart_service",
                         args=args, reason="unit not in allowlist")
            allowed = ", ".join(node.restart_allowed) or "(none)"
            return (f"REFUSED: '{unit}' is not in {node.name}'s restart allowlist "
                    f"({allowed}). Recommend the manual step instead.")

        argv = ["/usr/bin/systemctl", "restart", unit]
        cmd = " ".join(argv)

        # Guard the channel BEFORE prompting so a fast "yes" can't spawn a new
        # handler (on_message suppresses while we hold the channel).
        _awaiting_confirmation.add(channel.id)
        try:
            await _send(channel,
                        f"🔴 **Confirm restart** — run `sudo {cmd}` on **{node.name}**"
                        f" ({node.ssh_host})?\nReply `yes` / `do it` to proceed — anything"
                        f" else cancels. Waiting {CONFIRM_TIMEOUT}s.")
            audit_mutation("await_confirm", approver_id=user,
                           approver_name=str(message.author), node=node.name, unit=unit)

            def _check(m: discord.Message) -> bool:
                return m.author.id == ALLOWED_USER_ID and m.channel.id == channel.id

            try:
                resp = await self.wait_for("message", check=_check, timeout=CONFIRM_TIMEOUT)
            except asyncio.TimeoutError:
                audit_mutation("confirm_timeout", approver_id=user,
                               approver_name=str(message.author), node=node.name, unit=unit)
                await _send(channel, f"⌛ No confirmation in {CONFIRM_TIMEOUT}s — **cancelled**, nothing ran.")
                return f"CANCELLED (timeout): {cmd} on {node.name} was NOT run."
        finally:
            _awaiting_confirmation.discard(channel.id)

        answer = resp.content.strip().lower()
        if answer not in AFFIRMATIVE:
            audit_mutation("cancelled", approver_id=user, approver_name=str(message.author),
                       node=node.name, unit=unit, reply=answer)
            await _send(channel, "🚫 **Cancelled** — nothing ran.")
            return f"CANCELLED (operator said '{answer}'): {cmd} on {node.name} was NOT run."

        # --- execute ---
        audit_mutation("confirmed", approver_id=user, approver_name=str(message.author),
                       node=node.name, unit=unit, reply=answer)
        rc, out, err = await ssh.run(node, argv, sudo=True, timeout=60)
        audit_mutation("executed_mutation", approver_id=user,
                       approver_name=str(message.author), node=node.name, unit=unit,
                       rc=rc, output=(out + err)[:2000])
        body = (out or "").strip() or (err or "").strip() or "(no output)"
        if rc == 0:
            await _send(channel, f"✅ `sudo {cmd}` on **{node.name}** — done.")
            return f"EXECUTED: {cmd} on {node.name} succeeded (rc=0)."
        await _send(channel, f"⚠️ `sudo {cmd}` on **{node.name}** exited {rc}:\n```\n{body[:1500]}\n```")
        return f"EXECUTED with error: {cmd} on {node.name} rc={rc}: {err.strip()[:300]}"


def main():
    if not DISCORD_TOKEN:
        raise SystemExit("DISCORD_TOKEN is not set (put it in /opt/jarvis-oncall/.env)")
    if not ALLOWED_USER_ID:
        raise SystemExit("ALLOWED_USER_ID is not set — refusing to start with an empty allowlist")
    intents = discord.Intents.default()
    intents.message_content = True
    OnCallClient(intents=intents).run(DISCORD_TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
