"""Weekly digest message (posted by /precedent digest)."""
from __future__ import annotations


def digest_blocks(stats: dict, ratified: list[dict], drift: list[dict]) -> list[dict]:
    blocks: list[dict] = [
        {"type": "header", "text": {"type": "plain_text", "text": "⚖️ Precedent — weekly digest", "emoji": True}},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Ratified*\n{stats['ratified']}"},
                {"type": "mrkdwn", "text": f"*Pending*\n{stats['pending']}"},
                {"type": "mrkdwn", "text": f"*Open drift*\n{stats['drift_open']}"},
            ],
        },
    ]
    if ratified:
        recent = ratified[-5:]
        lines = "\n".join(f"• *{d['id']}* — {d['title']}: {d['statement']}" for d in recent)
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*Canon*\n{lines}"}})
    if drift:
        lines = "\n".join(
            f"• *{d.get('decision_id')}* — {d.get('resolution')} (_{(d.get('claim') or '')[:50]}_)"
            for d in drift[:5]
        )
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*Recent drift*\n{lines}"}})
    blocks.append({"type": "context", "elements": [
        {"type": "mrkdwn", "text": "Full case law in the 📜 Decision Register canvas."}]})
    return blocks
