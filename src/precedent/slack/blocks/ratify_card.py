"""Ratify card (in-thread): a proposed decision awaiting a human Approve."""
from __future__ import annotations


def ratify_card(d: dict) -> list[dict]:
    decided_by = ", ".join(d.get("decided_by") or []) or "—"
    dissent_n = len(d.get("dissent") or [])
    evidence_n = len([e for e in (d.get("evidence") or []) if e.get("permalink")])
    blocks: list[dict] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "⚖️ Decision detected — ratify?", "emoji": True},
        },
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*{d['title']}*\n{d['statement']}"}},
    ]
    if d.get("rationale"):
        blocks.append(
            {"type": "context", "elements": [{"type": "mrkdwn", "text": f"_Why:_ {d['rationale']}"}]}
        )
    blocks.append(
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Decided by*\n{decided_by}"},
                {"type": "mrkdwn", "text": f"*Scope*\n{d.get('scope') or '—'}"},
                {"type": "mrkdwn", "text": f"*Dissent*\n{dissent_n} recorded"},
                {"type": "mrkdwn", "text": f"*Evidence*\n{evidence_n} linked"},
            ],
        }
    )
    blocks.append(
        {
            "type": "actions",
            "block_id": "ratify_actions",
            "elements": [
                {
                    "type": "button",
                    "style": "primary",
                    "text": {"type": "plain_text", "text": "✅ Approve", "emoji": True},
                    "action_id": "ratify_approve",
                    "value": d["id"],
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✏️ Edit", "emoji": True},
                    "action_id": "ratify_edit",
                    "value": d["id"],
                },
                {
                    "type": "button",
                    "style": "danger",
                    "text": {"type": "plain_text", "text": "🗑️ Dismiss", "emoji": True},
                    "action_id": "ratify_dismiss",
                    "value": d["id"],
                },
            ],
        }
    )
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Nothing enters canon without a human approval. · _{d['id']}_",
                }
            ],
        }
    )
    return blocks


def ratified_confirmation(d: dict, user_id: str) -> list[dict]:
    return [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"✅ *Ratified {d['id']}* — {d['title']}"},
        },
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Entered canon · approved by <@{user_id}>"}
            ],
        },
    ]


def dismissed_note(decision_id: str) -> list[dict]:
    return [
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"🗑️ Dismissed — _{decision_id}_ was not added to canon."}
            ],
        }
    ]
