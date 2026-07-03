"""Ephemeral drift card: a private, cited nudge when a claim conflicts with the canon."""
from __future__ import annotations


def drift_card(conflict: dict, decision: dict, drift_id: int) -> list[dict]:
    """`conflict`: {id,title,statement,confidence,reason}; `decision`: full ruling (lineage optional)."""
    conf_pct = int(round(conflict["confidence"] * 100))
    meta = []
    if decision.get("decided_at"):
        meta.append(f"ratified {decision['decided_at']}")
    if decision.get("ratified_by"):
        meta.append(f"by <@{decision['ratified_by']}>")
    approvals = len(decision.get("decided_by") or [])
    if approvals:
        meta.append(f"{approvals} on record")
    meta.append(f"confidence {conf_pct}%")

    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"⚖️ *Heads up — this may conflict with* *{conflict['id']} — {conflict['title']}*",
            },
        },
        {"type": "context", "elements": [{"type": "mrkdwn", "text": " · ".join(meta)}]},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"> {conflict['statement']}"}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"_{conflict['reason']}_"}]},
        {
            "type": "actions",
            "block_id": "drift_actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "📖 View ruling", "emoji": True},
                    "action_id": "drift_view",
                    "value": conflict["id"],
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "⤴️ Propose supersede", "emoji": True},
                    "action_id": "drift_supersede",
                    "value": str(drift_id),
                },
                {
                    "type": "button",
                    "style": "primary",
                    "text": {"type": "plain_text", "text": "✅ I'm aligned", "emoji": True},
                    "action_id": "drift_aligned",
                    "value": str(drift_id),
                },
            ],
        },
        {"type": "context", "elements": [{"type": "mrkdwn", "text": "Only you can see this."}]},
    ]
