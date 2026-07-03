"""Sentinel: does a claim contradict the ratified canon?

Hot path = local pgvector ONLY (never RTS). Cheap cosine gate, then an LLM contradiction judge.
Shared by the message listener (F3) and the MCP check_conflict tool (F6) — one brain, two mouths.
"""
from __future__ import annotations

import json

from precedent.config import settings
from precedent.services import canon
from precedent.services.llm import complete_json, load_prompt
from precedent.telemetry import get_logger

log = get_logger("sentinel")

COSINE_GATE = 0.45  # below this top similarity, don't even ask the LLM (cheap gate)


def check_claim(claim: str, k: int = 4, team_id: str | None = None,
                query_vec: list[float] | None = None) -> dict:
    """Return {verdict: clear|conflict, conflicts: [...], top_similarity}. Never raises.

    Pass query_vec to reuse a precomputed embedding (batching / rate-limit friendly).
    """
    try:
        if query_vec is not None:
            candidates = canon.search_local_vec(query_vec, k=k, status="ratified", team_id=team_id)
        else:
            candidates = canon.search_local(claim, k=k, status="ratified", team_id=team_id)
    except Exception as e:  # noqa: BLE001
        log.warning("sentinel.search_error", error=str(e)[:150])
        return {"verdict": "clear", "conflicts": [], "top_similarity": 0.0}

    top = candidates[0]["similarity"] if candidates else 0.0
    if not candidates or top < COSINE_GATE:
        log.info("sentinel.gate_stop", top_similarity=round(top, 3))
        return {"verdict": "clear", "conflicts": [], "top_similarity": top}

    payload = {
        "claim": claim,
        "candidates": [
            {"id": c["id"], "statement": c["statement"], "rationale": c.get("rationale"), "scope": c.get("scope")}
            for c in candidates
        ],
    }
    try:
        out = complete_json(
            load_prompt("sentinel"), json.dumps(payload, ensure_ascii=False),
            model=settings.model_reason, temperature=0, max_tokens=500,
        )
    except Exception as e:  # noqa: BLE001 — stay silent on failure, never block the channel
        log.warning("sentinel.judge_error", error=str(e)[:150])
        return {"verdict": "clear", "conflicts": [], "top_similarity": top}

    by_id = {c["id"]: c for c in candidates}
    conflicts = []
    for r in out.get("results", []):
        if r.get("verdict") == "contradicts" and float(r.get("confidence", 0)) >= settings.drift_threshold:
            cand = by_id.get(r.get("id"))
            if cand:
                conflicts.append(
                    {
                        "id": cand["id"],
                        "title": cand["title"],
                        "statement": cand["statement"],
                        "confidence": float(r["confidence"]),
                        "reason": r.get("reason", ""),
                    }
                )
    conflicts.sort(key=lambda x: -x["confidence"])
    verdict = "conflict" if conflicts else "clear"
    log.info("sentinel.judged", verdict=verdict, n_conflicts=len(conflicts), top_similarity=round(top, 3))
    return {"verdict": verdict, "conflicts": conflicts, "top_similarity": top}
