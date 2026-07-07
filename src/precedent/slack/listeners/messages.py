"""Gatekeeper hot path: every message in an enrolled channel -> classify -> route.

decision_moment (conf >= .8) -> autonomous Extractor -> Ratify card (F2).
assertive_claim (conf >= .7) -> Sentinel drift check (F3, local pgvector only — never RTS).
"""
from __future__ import annotations

import time

from slack_bolt import App

from precedent.agents.gatekeeper import classify
from precedent.agents.sentinel import check_claim
from precedent.config import settings
from precedent.services import canon
from precedent.slack.blocks.drift_card import drift_card
from precedent.slack.capture import propose_and_post
from precedent.telemetry import get_logger, new_correlation_id

log = get_logger("messages")

_SKIP_SUBTYPES = {
    "message_changed",
    "message_deleted",
    "channel_join",
    "channel_leave",
    "bot_message",
    "thread_broadcast",
}
DECISION_CONF = 0.8
CLAIM_CONF = 0.7
DEBOUNCE_SEC = 120  # max one drift card per user per channel per 2 min
_last_drift: dict[tuple[str, str], float] = {}


def _sentinel_check(client, event, channel: str, text: str) -> None:
    """Drift defense hot path — local pgvector only, never RTS."""
    user = event.get("user")
    now = time.monotonic()
    if now - _last_drift.get((user, channel), 0.0) < DEBOUNCE_SEC:
        log.info("sentinel.debounced", user=user, channel=channel)
        return

    res = check_claim(text)  # embed + cosine gate + LLM judge (local only)
    if res["verdict"] != "conflict":
        return
    top = res["conflicts"][0]
    decision = canon.get_with_lineage(top["id"]) or {}

    try:
        permalink = client.chat_getPermalink(channel=channel, message_ts=event["ts"]).get("permalink")
    except Exception:
        permalink = None

    drift_id = canon.record_drift(top["id"], channel, user, text, top["confidence"], permalink)
    _last_drift[(user, channel)] = now
    client.chat_postEphemeral(
        channel=channel,
        user=user,
        thread_ts=event.get("thread_ts"),
        blocks=drift_card(top, decision, drift_id),
        text=f"Heads up — this may conflict with {top['id']}.",
    )
    log.info("sentinel.drift_card", id=top["id"], drift=drift_id, user=user, channel=channel)


def register(app: App) -> None:
    @app.event("message")
    def on_message(event, client, context):
        new_correlation_id()
        # ── G4 filters: never react to our own/bot/edited/seed traffic ──
        if settings.seed_mode:
            return
        if event.get("subtype") in _SKIP_SUBTYPES or event.get("bot_id"):
            return
        if event.get("user") and event.get("user") == context.get("bot_user_id"):
            return
        # Assistant DMs are owned by the Assistant middleware — never gatekeep them.
        if event.get("channel_type") == "im":
            return
        text = (event.get("text") or "").strip()
        if not text:
            return
        channel = event.get("channel")
        if not canon.is_observed(channel):
            return

        # Up to 6 prior thread messages as context.
        ctx: list[str] = []
        thread_ts = event.get("thread_ts")
        if thread_ts:
            try:
                replies = client.conversations_replies(channel=channel, ts=thread_ts, limit=7)
                ctx = [m.get("text", "") for m in replies.get("messages", [])[:-1]][-6:]
            except Exception:
                ctx = []

        result = classify(text, ctx)
        label, conf = result["label"], result["confidence"]

        if label == "decision_moment" and conf >= DECISION_CONF:
            decision = propose_and_post(client, channel, thread_ts or event["ts"])
            if decision:
                log.info("messages.autocapture", id=decision["id"], channel=channel)
        elif label == "assertive_claim" and conf >= CLAIM_CONF:
            _sentinel_check(client, event, channel, text)

    @app.event("member_joined_channel")
    def on_member_joined(event, client, context):
        new_correlation_id()
        # Auto-enroll a channel to 'observe' when *our bot* is added to it.
        if event.get("user") and event.get("user") == context.get("bot_user_id"):
            canon.set_enrollment(event["channel"], "observe")
            log.info("channel.auto_enrolled", channel=event["channel"])

    @app.event("app_mention")
    def on_mention(event, client, say):
        new_correlation_id()
        # app_mention is the only surface that can carry a fresh RTS action_token (G1) —
        # log the truth about what this workspace actually delivers.
        action_token = event.get("action_token")
        log.info("mention.received", has_action_token=bool(action_token),
                 event_keys=sorted(event.keys()))
        text = (event.get("text") or "").lower()
        if "backfill" in text:
            from precedent.slack.backfill import run as run_backfill

            say(text=":pick: Mining history for un-captured decisions…",
                thread_ts=event.get("thread_ts") or event["ts"])
            result = run_backfill(client, event["channel"], action_token)
            summary = (f":scales: Proposed {len(result['proposed'])} ruling(s): "
                       f"{', '.join(result['proposed'])}"
                       if result["proposed"] else
                       f"No new decision threads found ({result['scanned_threads']} scanned).")
            note = result["rts_note"] or f"semantic search used ({result['rts_used']} calls)"
            say(text=f"{summary}\n_RTS: {note}_",
                thread_ts=event.get("thread_ts") or event["ts"])
        else:
            # Archivist over @mention — a reliable, discoverable path to the cited Q&A
            # (works regardless of the Slack assistant/split-view surface).
            import re

            from precedent.agents import archivist

            thread = event.get("thread_ts") or event["ts"]
            question = re.sub(r"<@[A-Z0-9]+>", "", event.get("text") or "").strip()
            if not question or len(question) < 4:
                say(text="Ask me what the team has decided and *why* — e.g. "
                    "`@precedent why do we use Postgres for new services?` "
                    "Or `@precedent backfill` to mine this channel's history.",
                    thread_ts=thread)
                return
            try:
                answer = "".join(archivist.answer_stream(question, client, action_token)).strip()
            except Exception as e:  # noqa: BLE001
                log.warning("mention.archivist_error", error=str(e)[:160])
                answer = ""
            say(text=answer or "I couldn't find anything relevant in the canon yet.", thread_ts=thread)
            log.info("mention.archivist_answered", q=question[:60], chars=len(answer))
