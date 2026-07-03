"""Decision Register — a Slack Canvas auto-synced from canon (G8: regenerate full markdown).

One canvas per workspace; its id lives in meta['canvas_id']. On every canon change we rebuild
the whole markdown and replace it (simplest reliable sync).
"""
from __future__ import annotations

from sqlalchemy import select

from precedent.db.client import session_scope
from precedent.db.schema import Decision
from precedent.services import canon
from precedent.telemetry import get_logger

log = get_logger("canvas")

_STATUS = {"ratified": "🟢", "proposed": "🟡", "superseded": "⚪", "expired": "🔴"}
CANVAS_TITLE = "⚖️ Decision Register"


def render_register(team_id: str) -> str:
    with session_scope() as s:
        rows = s.execute(
            select(Decision).where(Decision.team_id == team_id).order_by(Decision.scope, Decision.id)
        ).scalars().all()
        decisions = [canon._to_dict(d) for d in rows]

    lines = ["# ⚖️ Decision Register", "_Precedent — institutional memory, enforced._", ""]
    if not decisions:
        lines.append("_No rulings yet. React :scales: on a decision thread to begin._")
        return "\n".join(lines)

    by_scope: dict[str, list[dict]] = {}
    for d in decisions:
        by_scope.setdefault(d.get("scope") or "general", []).append(d)

    for scope in sorted(by_scope):
        lines.append(f"## {scope}")
        for d in by_scope[scope]:
            badge = _STATUS.get(d["status"], d["status"])
            meta = []
            if d.get("decided_at"):
                meta.append(d["decided_at"])
            if d.get("ratified_by"):
                meta.append(f"ratified by @{d['ratified_by']}")
            lines.append(f"### {badge} {d['id']} — {d['title']}")
            lines.append(f"**{d['statement']}**" + (f"  ·  _{' · '.join(meta)}_" if meta else ""))
            if d.get("rationale"):
                lines.append(f"> {d['rationale']}")
            if d.get("supersedes_id"):
                lines.append(f"↳ supersedes {d['supersedes_id']}")
            if d.get("superseded_by"):
                lines.append(f"⚠️ superseded by {d['superseded_by']}")
            ev = [e.get("permalink") for e in (d.get("evidence") or []) if e.get("permalink")]
            if ev:
                lines.append("Evidence: " + " ".join(f"[{i + 1}]({p})" for i, p in enumerate(ev)))
            lines.append("")
    return "\n".join(lines)


def sync(client, team_id: str) -> str | None:
    """Create-or-replace the Decision Register canvas. Returns canvas_id."""
    markdown = render_register(team_id)
    content = {"type": "markdown", "markdown": markdown}
    canvas_id = canon.get_meta("canvas_id")
    try:
        if not canvas_id:
            resp = client.canvases_create(title=CANVAS_TITLE, document_content=content)
            canvas_id = resp["canvas_id"]
            canon.set_meta("canvas_id", canvas_id)
            log.info("canvas.created", canvas_id=canvas_id)
        else:
            client.canvases_edit(
                canvas_id=canvas_id,
                changes=[{"operation": "replace", "document_content": content}],
            )
            log.info("canvas.synced", canvas_id=canvas_id)
        return canvas_id
    except Exception as e:  # noqa: BLE001 — canvas is a surface, not the source of truth
        log.warning("canvas.sync_error", error=str(e)[:200])
        return canvas_id
