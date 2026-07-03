"""Slack Real-Time Search (RTS) client — Archivist evidence + backfill ONLY. NEVER the hot path.

RTS has no typed SDK method: we call client.api_call("assistant.search.context" / ".info").
Requires a fresh action_token from a message/app_mention event in the same request cycle (G1).
Budget-enforced (<=3 calls/inquiry). Degrades gracefully to canon-only when unavailable (G2).
"""
from __future__ import annotations

from slack_sdk.errors import SlackApiError

from precedent.telemetry import get_logger

log = get_logger("rts")


class RtsBudget:
    """Hard per-inquiry call budget (Playbook: <=3). Paginated cursor calls count too."""

    def __init__(self, max_calls: int = 3) -> None:
        self.max_calls = max_calls
        self.used = 0

    def can_spend(self) -> bool:
        return self.used < self.max_calls


def info(client) -> dict:
    """assistant.search.info — log capabilities at startup; detect AI-Search availability."""
    try:
        resp = client.api_call("assistant.search.info")
        return dict(resp.data) if hasattr(resp, "data") else dict(resp)
    except SlackApiError as e:
        log.warning("rts.info_error", error=e.response.get("error"))
        return {}


def _parse_results(data: dict) -> list[dict]:
    # Defensive: RTS result shape varies; pull message text + permalink where present.
    results = data.get("results") or data.get("messages") or []
    out = []
    for r in results if isinstance(results, list) else []:
        out.append(
            {
                "text": (r.get("text") or r.get("message", {}).get("text") or "")[:200],
                "permalink": r.get("permalink") or r.get("message", {}).get("permalink"),
                "channel": r.get("channel") or r.get("channel_id"),
            }
        )
    return [r for r in out if r["text"]]


def search_context(client, query: str, action_token: str | None, budget: RtsBudget,
                   *, limit: int = 10, context_channel_id: str | None = None) -> dict:
    """One RTS call. Phrase `query` as a natural-language question for semantic mode (G2).

    Returns {results: [...], degraded: None|reason}.
    """
    if not budget.can_spend():
        return {"results": [], "degraded": "budget_exceeded"}
    if not action_token:
        # No token -> cannot call RTS this cycle; caller falls back to canon-only.
        return {"results": [], "degraded": "no_action_token"}

    params: dict = {
        "query": query,
        "action_token": action_token,
        "limit": limit,
        "include_bots": True,  # seeded content is bot-authored (G4/G10)
    }
    if context_channel_id:
        params["context_channel_id"] = context_channel_id

    budget.used += 1
    try:
        resp = client.api_call("assistant.search.context", params=params)
        data = dict(resp.data) if hasattr(resp, "data") else dict(resp)
        results = _parse_results(data)
        log.info("rts.search", used=budget.used, n=len(results), query=query[:60])
        return {"results": results, "degraded": None}
    except SlackApiError as e:
        err = e.response.get("error")
        if err == "ratelimited":
            retry_after = int(e.response.headers.get("Retry-After", "1"))
            log.warning("rts.ratelimited", retry_after=retry_after)
            return {"results": [], "degraded": "ratelimited"}
        log.warning("rts.error", error=err)
        return {"results": [], "degraded": err or "error"}
