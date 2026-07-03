"""App Home dashboard: live stats, pending-ratification queue, recent drift, Register link."""
from __future__ import annotations


def home_view(stats: dict | None = None, pending: list[dict] | None = None,
              drift: list[dict] | None = None, canvas_id: str | None = None) -> dict:
    stats = stats or {"ratified": 0, "pending": 0, "drift_open": 0}
    pending = pending or []
    drift = drift or []

    blocks: list[dict] = [
        {"type": "header", "text": {"type": "plain_text", "text": "⚖️ Precedent", "emoji": True}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": "*Institutional memory, enforced.*"}]},
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Ratified*\n{stats['ratified']}"},
                {"type": "mrkdwn", "text": f"*Pending*\n{stats['pending']}"},
                {"type": "mrkdwn", "text": f"*Open drift*\n{stats['drift_open']}"},
            ],
        },
    ]

    if canvas_id:
        blocks.append({"type": "context", "elements": [
            {"type": "mrkdwn", "text": "📜 *Decision Register* canvas is live and auto-synced."}]})

    if pending:
        blocks.append({"type": "divider"})
        blocks.append({"type": "header", "text": {"type": "plain_text", "text": "Pending ratification", "emoji": True}})
        for p in pending[:5]:
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*{p['id']} — {p['title']}*\n{p['statement']}"},
                "accessory": {
                    "type": "button",
                    "style": "primary",
                    "text": {"type": "plain_text", "text": "✅ Approve", "emoji": True},
                    "action_id": "home_approve",
                    "value": p["id"],
                },
            })

    if drift:
        blocks.append({"type": "divider"})
        blocks.append({"type": "header", "text": {"type": "plain_text", "text": "Recent drift", "emoji": True}})
        for d in drift[:5]:
            conf = int(round((d.get("confidence") or 0) * 100))
            blocks.append({"type": "context", "elements": [{"type": "mrkdwn",
                "text": f"*{d.get('decision_id')}* · {d.get('resolution')} · {conf}% · _{(d.get('claim') or '')[:70]}_"}]})

    footer = ("React :scales: on a decision thread to capture more rulings."
              if (stats["ratified"] or stats["pending"])
              else "The canon is empty. React :scales: on a decision thread to begin.")
    blocks.append({"type": "divider"})
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": footer}]})
    return {"type": "home", "blocks": blocks}
