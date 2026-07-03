"""Archivist: answers "what did we decide and why?" from canon (+ optional RTS evidence).

Canon-first (always works, keyword-independent). RTS adds conversational evidence when an
action_token is available, capped at <=3 calls; degrades to canon-only otherwise.
"""
from __future__ import annotations

import json

from precedent.services import canon, rts
from precedent.services.llm import load_prompt, stream_text
from precedent.telemetry import get_logger

log = get_logger("archivist")


def _canon_payload(hits: list[dict]) -> list[dict]:
    out = []
    for h in hits:
        out.append(
            {
                "id": h["id"],
                "statement": h["statement"],
                "rationale": h.get("rationale"),
                "dissent": h.get("dissent") or [],
                "alternatives": h.get("alternatives") or [],
                "scope": h.get("scope"),
                "ratified_by": h.get("ratified_by"),
                "decided_at": h.get("decided_at"),
                "supersedes_id": h.get("supersedes_id"),
                "superseded_by": h.get("superseded_by"),
                "evidence_permalinks": [e.get("permalink") for e in (h.get("evidence") or []) if e.get("permalink")],
            }
        )
    return out


def gather(query: str, client=None, action_token: str | None = None, k: int = 5) -> dict:
    canon_hits = canon.search_local(query, k=k, status="ratified")
    rts_hits: list[dict] = []
    degraded = "no_client"
    if client is not None:
        budget = rts.RtsBudget(3)
        # RTS semantic mode wants a natural-language question (G2).
        res = rts.search_context(client, query, action_token, budget)
        rts_hits, degraded = res["results"], res["degraded"]
    if degraded:
        log.info("archivist.rts_degraded", reason=degraded)
    return {"canon": canon_hits, "rts": rts_hits, "degraded": degraded}


def _user_content(query: str, gathered: dict) -> str:
    return json.dumps(
        {
            "question": query,
            "canon": _canon_payload(gathered["canon"]),
            "search_snippets": [{"text": r["text"], "permalink": r["permalink"]} for r in gathered["rts"]],
        },
        ensure_ascii=False,
    )


def answer_stream(query: str, client=None, action_token: str | None = None):
    """Yield the cited answer in streaming chunks."""
    gathered = gather(query, client, action_token)
    yield from stream_text(load_prompt("archivist"), _user_content(query, gathered), max_tokens=700)


def suggested_followups(query: str) -> list[dict]:
    """Canon-aware follow-up prompts (max 4 per Slack)."""
    hits = canon.search_local(query, k=3, status="ratified")
    prompts = [{"title": f"Why {h['id']}?", "message": f"Why did we decide: {h['statement']}?"} for h in hits[:2]]
    prompts.append({"title": "What was rejected?", "message": f"What alternatives were rejected for: {query}?"})
    return prompts[:4]
