"""Canon service — create/ratify/supersede/lineage/local-search over the decision store.

One brain, two mouths: Slack listeners and the MCP server both call these functions.
Embeddings are computed at ratify time (proposed rows carry no vector).
"""
from __future__ import annotations

import re

from sqlalchemy import select

from precedent.config import settings
from precedent.db.client import session_scope
from precedent.db.schema import Decision
from precedent.services.embeddings import embed
from precedent.telemetry import get_logger

log = get_logger("canon")

_ID_RE = re.compile(r"^PRE-(\d+)$")


def next_id() -> str:
    with session_scope() as s:
        ids = s.execute(select(Decision.id)).scalars().all()
    highest = 0
    for i in ids:
        m = _ID_RE.match(i or "")
        if m:
            highest = max(highest, int(m.group(1)))
    return f"PRE-{highest + 1:03d}"


def _embedding_text(title: str, statement: str, rationale: str | None) -> str:
    parts = [title or "", statement or ""]
    if rationale:
        parts.append(rationale)
    return ". ".join(p.strip() for p in parts if p and p.strip())


def _to_dict(d: Decision) -> dict:
    return {
        "id": d.id,
        "title": d.title,
        "statement": d.statement,
        "rationale": d.rationale,
        "alternatives": d.alternatives or [],
        "dissent": d.dissent or [],
        "scope": d.scope,
        "status": d.status,
        "decided_by": d.decided_by or [],
        "ratified_by": d.ratified_by,
        "supersedes_id": d.supersedes_id,
        "superseded_by": d.superseded_by,
        "expires_hint": d.expires_hint,
        "evidence": d.evidence or [],
        "decided_at": d.decided_at.isoformat() if d.decided_at else None,
        "team_id": d.team_id,
    }


def create_proposed(obj: dict) -> str:
    """Insert a proposed decision (no embedding until ratified). Returns its id."""
    pid = obj.get("id") or next_id()
    with session_scope() as s:
        s.add(
            Decision(
                id=pid,
                title=obj["title"],
                statement=obj["statement"],
                rationale=obj.get("rationale"),
                alternatives=obj.get("alternatives") or [],
                dissent=obj.get("dissent") or [],
                scope=obj.get("scope"),
                status="proposed",
                decided_by=obj.get("decided_by") or [],
                supersedes_id=obj.get("supersedes_id"),
                expires_hint=obj.get("expires_hint"),
                evidence=obj.get("evidence") or [],
                decided_at=obj.get("decided_at"),
                team_id=obj.get("team_id") or settings.team_id,
            )
        )
    log.info("canon.proposed", id=pid, title=obj.get("title"))
    return pid


def ratify(decision_id: str, user_id: str) -> dict:
    """Mark ratified and compute+store the embedding. Idempotent (double-click safe)."""
    with session_scope() as s:
        d = s.get(Decision, decision_id)
        if d is None:
            raise ValueError(f"decision {decision_id} not found")
        if d.status == "ratified":
            log.info("canon.ratify.noop", id=decision_id)
            return _to_dict(d)
        d.embedding = embed(_embedding_text(d.title, d.statement, d.rationale))
        d.status = "ratified"
        d.ratified_by = user_id
        # If this ruling supersedes an older one (e.g. a drift supersede proposal), link both ways.
        if d.supersedes_id:
            old = s.get(Decision, d.supersedes_id)
            if old is not None and old.status != "superseded":
                old.status = "superseded"
                old.superseded_by = d.id
                log.info("canon.superseded_via_ratify", old=old.id, new=d.id)
        log.info("canon.ratified", id=decision_id, by=user_id)
        return _to_dict(d)


def supersede(old_id: str, new_obj: dict, user_id: str) -> str:
    """Create a new ratified decision that supersedes old_id; link both ways."""
    new_id = new_obj.get("id") or next_id()
    with session_scope() as s:
        old = s.get(Decision, old_id)
        if old is None:
            raise ValueError(f"decision {old_id} not found")
        vec = embed(_embedding_text(new_obj["title"], new_obj["statement"], new_obj.get("rationale")))
        s.add(
            Decision(
                id=new_id,
                title=new_obj["title"],
                statement=new_obj["statement"],
                rationale=new_obj.get("rationale"),
                alternatives=new_obj.get("alternatives") or [],
                dissent=new_obj.get("dissent") or [],
                scope=new_obj.get("scope") or old.scope,
                status="ratified",
                ratified_by=user_id,
                decided_by=new_obj.get("decided_by") or [],
                supersedes_id=old_id,
                evidence=new_obj.get("evidence") or [],
                decided_at=new_obj.get("decided_at"),
                embedding=vec,
                team_id=old.team_id,
            )
        )
        old.status = "superseded"
        old.superseded_by = new_id
    log.info("canon.superseded", old=old_id, new=new_id, by=user_id)
    return new_id


def get_with_lineage(decision_id: str) -> dict | None:
    """Return the decision plus its supersede ancestors and descendants."""
    with session_scope() as s:
        d = s.get(Decision, decision_id)
        if d is None:
            return None
        result = _to_dict(d)
        ancestors: list[dict] = []
        cur = d
        while cur.supersedes_id:
            cur = s.get(Decision, cur.supersedes_id)
            if cur is None:
                break
            ancestors.append(_to_dict(cur))
        descendants: list[dict] = []
        cur = d
        while cur.superseded_by:
            cur = s.get(Decision, cur.superseded_by)
            if cur is None:
                break
            descendants.append(_to_dict(cur))
        result["ancestors"] = ancestors
        result["descendants"] = descendants
        return result


def search_local_vec(qv: list[float], k: int = 5, status: str = "ratified",
                     team_id: str | None = None) -> list[dict]:
    """Nearest decisions to a PRECOMPUTED query vector (no embedding call)."""
    tid = team_id or settings.team_id
    with session_scope() as s:
        dist = Decision.embedding.cosine_distance(qv).label("dist")
        rows = (
            s.execute(
                select(Decision, dist)
                .where(Decision.status == status, Decision.team_id == tid)
                .order_by(dist)
                .limit(k)
            )
            .all()
        )
    out = []
    for d, dv in rows:
        item = _to_dict(d)
        item["similarity"] = 1.0 - float(dv)
        out.append(item)
    return out


def search_local(text: str, k: int = 5, status: str = "ratified", team_id: str | None = None) -> list[dict]:
    """Embed `text` and return the k nearest decisions by cosine similarity (local pgvector)."""
    return search_local_vec(embed(text), k=k, status=status, team_id=team_id)


def delete_proposed(decision_id: str) -> bool:
    """Dismiss a proposed decision (only if still proposed). Idempotent."""
    with session_scope() as s:
        d = s.get(Decision, decision_id)
        if d is None or d.status != "proposed":
            return False
        s.delete(d)
    log.info("canon.dismissed", id=decision_id)
    return True


def update_proposed(decision_id: str, fields: dict) -> dict | None:
    """Edit editable fields of a still-proposed decision before ratification."""
    allowed = {"title", "statement", "rationale", "scope"}
    with session_scope() as s:
        d = s.get(Decision, decision_id)
        if d is None:
            return None
        for k, v in fields.items():
            if k in allowed and v is not None:
                setattr(d, k, v)
        return _to_dict(d)


def get_meta(key: str) -> str | None:
    from precedent.db.schema import Meta

    with session_scope() as s:
        m = s.get(Meta, key)
        return m.value if m else None


def set_meta(key: str, value: str) -> None:
    from precedent.db.schema import Meta

    with session_scope() as s:
        m = s.get(Meta, key)
        if m is None:
            s.add(Meta(key=key, value=value))
        else:
            m.value = value


def counts() -> dict:
    """Live dashboard counts for App Home."""
    from sqlalchemy import func

    from precedent.db.schema import DriftEvent

    with session_scope() as s:
        ratified = s.scalar(select(func.count()).select_from(Decision).where(Decision.status == "ratified"))
        pending = s.scalar(select(func.count()).select_from(Decision).where(Decision.status == "proposed"))
        drift_open = s.scalar(select(func.count()).select_from(DriftEvent).where(DriftEvent.resolution == "open"))
    return {"ratified": ratified or 0, "pending": pending or 0, "drift_open": drift_open or 0}


def get_enrollment(channel_id: str) -> str | None:
    from precedent.db.schema import ChannelEnrollment

    with session_scope() as s:
        e = s.get(ChannelEnrollment, channel_id)
        return e.mode if e else None


def set_enrollment(channel_id: str, mode: str = "observe") -> None:
    from precedent.db.schema import ChannelEnrollment

    with session_scope() as s:
        e = s.get(ChannelEnrollment, channel_id)
        if e is None:
            s.add(ChannelEnrollment(channel_id=channel_id, mode=mode))
        else:
            e.mode = mode
    log.info("canon.enrollment", channel=channel_id, mode=mode)


def is_observed(channel_id: str) -> bool:
    """Privacy default: a channel is watched only if explicitly enrolled as 'observe' (Constraint 4)."""
    return get_enrollment(channel_id) == "observe"


def record_drift(decision_id: str, channel_id: str, author: str, claim: str,
                 confidence: float, permalink: str | None = None) -> int:
    from precedent.db.schema import DriftEvent

    with session_scope() as s:
        ev = DriftEvent(
            decision_id=decision_id, channel_id=channel_id, author=author, claim=claim,
            confidence=confidence, message_permalink=permalink, resolution="open",
        )
        s.add(ev)
        s.flush()
        drift_id = ev.id
    log.info("canon.drift_recorded", id=drift_id, decision=decision_id, confidence=round(confidence, 2))
    return drift_id


def resolve_drift(drift_id: int, resolution: str) -> None:
    from precedent.db.schema import DriftEvent

    with session_scope() as s:
        ev = s.get(DriftEvent, drift_id)
        if ev is not None:
            ev.resolution = resolution
    log.info("canon.drift_resolved", id=drift_id, resolution=resolution)


def get_drift(drift_id: int) -> dict | None:
    from precedent.db.schema import DriftEvent

    with session_scope() as s:
        ev = s.get(DriftEvent, drift_id)
        if ev is None:
            return None
        return {"id": ev.id, "decision_id": ev.decision_id, "claim": ev.claim,
                "channel_id": ev.channel_id, "author": ev.author, "resolution": ev.resolution}


def list_pending(team_id: str | None = None, limit: int = 10) -> list[dict]:
    tid = team_id or settings.team_id
    with session_scope() as s:
        rows = s.execute(
            select(Decision).where(Decision.status == "proposed", Decision.team_id == tid)
            .order_by(Decision.created_at.desc()).limit(limit)
        ).scalars().all()
        return [_to_dict(d) for d in rows]


def list_ratified(team_id: str | None = None) -> list[dict]:
    tid = team_id or settings.team_id
    with session_scope() as s:
        rows = s.execute(
            select(Decision).where(Decision.status == "ratified", Decision.team_id == tid)
            .order_by(Decision.scope, Decision.id)
        ).scalars().all()
        return [_to_dict(d) for d in rows]


def recent_drift(limit: int = 5) -> list[dict]:
    from precedent.db.schema import DriftEvent

    with session_scope() as s:
        rows = s.execute(
            select(DriftEvent).order_by(DriftEvent.created_at.desc()).limit(limit)
        ).scalars().all()
        return [{"id": e.id, "decision_id": e.decision_id, "claim": e.claim,
                 "confidence": e.confidence, "resolution": e.resolution} for e in rows]
