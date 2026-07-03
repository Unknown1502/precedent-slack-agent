"""Shared capture path: extract a thread -> proposed decision -> Ratify card.

Used by both the ⚖️ reaction (manual, F1) and the Gatekeeper (autonomous, F2).
Idempotent per source thread via the meta table.
"""
from __future__ import annotations

from precedent.agents.extractor import extract_from_thread
from precedent.services import canon
from precedent.slack.blocks.ratify_card import ratify_card
from precedent.telemetry import get_logger

log = get_logger("capture")


def propose_and_post(client, channel: str, ts: str, notify_user: str | None = None) -> dict | None:
    """Extract the thread at `ts`, dedup, and post a Ratify card. Returns the decision or None."""
    try:
        replies = client.conversations_replies(channel=channel, ts=ts, limit=1)
        root_ts = replies.get("messages", [{}])[0].get("ts", ts)
    except Exception:
        root_ts = ts

    meta_key = f"src:{channel}:{root_ts}"
    existing = canon.get_meta(meta_key)
    if existing and canon.get_with_lineage(existing):
        log.info("capture.dedup", key=meta_key, decision=existing)
        return None

    decision = extract_from_thread(client, channel, ts)
    if decision is None:
        if notify_user:
            client.chat_postEphemeral(
                channel=channel,
                user=notify_user,
                thread_ts=root_ts,
                text="I couldn't find a clear, converged decision there. "
                "React :scales: on the message where the call was made once the thread concludes.",
            )
        return None

    canon.set_meta(meta_key, decision["id"])
    client.chat_postMessage(
        channel=channel,
        thread_ts=root_ts,
        blocks=ratify_card(decision),
        text=f"Decision detected — ratify {decision['id']}?",
    )
    log.info("capture.card_posted", id=decision["id"], channel=channel, root_ts=root_ts)
    return decision
