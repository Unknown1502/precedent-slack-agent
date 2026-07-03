"""Decision card: full ruling with rationale, alternatives, dissent, lineage, evidence."""
from __future__ import annotations

_STATUS_BADGE = {
    "proposed": "🟡 Proposed",
    "ratified": "🟢 Ratified",
    "superseded": "⚪ Superseded",
    "expired": "🔴 Expired",
}


def decision_card(d: dict) -> list[dict]:
    """`d` may include `ancestors`/`descendants` (from canon.get_with_lineage)."""
    meta = _STATUS_BADGE.get(d.get("status", ""), d.get("status", ""))
    if d.get("ratified_by"):
        meta += f" · ratified by <@{d['ratified_by']}>"
    if d.get("decided_at"):
        meta += f" · {d['decided_at']}"

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{d['id']} — {d['title']}", "emoji": True},
        },
        {"type": "context", "elements": [{"type": "mrkdwn", "text": meta}]},
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*{d['statement']}*"}},
    ]
    if d.get("rationale"):
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*Why*\n{d['rationale']}"}})

    alts = d.get("alternatives") or []
    if alts:
        txt = "\n".join(f"• *{a.get('option', '?')}* — {a.get('why_rejected', '')}" for a in alts)
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*Alternatives rejected*\n{txt}"}})

    dissent = d.get("dissent") or []
    if dissent:
        txt = "\n".join(f"• {x.get('author', '?')}: {x.get('summary', '')}" for x in dissent)
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": f"*Dissent*\n{txt}"}})

    chain = [a["id"] for a in reversed(d.get("ancestors") or [])] + [f"*{d['id']}*"]
    chain += [de["id"] for de in (d.get("descendants") or [])]
    if len(chain) > 1:
        blocks.append(
            {"type": "context", "elements": [{"type": "mrkdwn", "text": "Lineage: " + " → ".join(chain)}]}
        )

    ev_links = [
        f"• <{e['permalink']}|evidence {i + 1}>"
        for i, e in enumerate(d.get("evidence") or [])
        if e.get("permalink")
    ]
    if ev_links:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*Sources*\n" + "\n".join(ev_links)}})
    return blocks
