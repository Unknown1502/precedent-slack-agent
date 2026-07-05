"""Precedent MCP server (Streamable HTTP) — the canon as a rulebook other AI agents consult.

Tools reuse canon.py + sentinel.py — one brain, two mouths (Slack + MCP).
propose_decision writes a PROPOSED row and posts a Ratify card to Slack (humans ratify).

Run:  python -m precedent.mcp.server
"""
from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from precedent.agents.sentinel import check_claim
from precedent.config import settings
from precedent.services import canon
from precedent.telemetry import configure_logging, get_logger

log = get_logger("mcp")

# Behind a platform proxy (Railway/Render/Fly) the inbound Host header is the public domain, which
# the SDK's DNS-rebinding protection rejects with 421 unless allow-listed. Our real access control is
# the bearer token (BearerAuthMiddleware -> 401), so default protection OFF (works on any host); set
# MCP_ALLOWED_HOSTS="host1,host2" to re-enable a strict allow-list.
_allowed = [h.strip() for h in os.environ.get("MCP_ALLOWED_HOSTS", "").split(",") if h.strip()]
_security = TransportSecuritySettings(
    enable_dns_rebinding_protection=bool(_allowed),
    allowed_hosts=_allowed,
    allowed_origins=_allowed,
)

mcp = FastMCP(
    "precedent",
    instructions="Consult the organization's ratified decision canon before acting. "
    "Use check_conflict before proposing plans; propose_decision routes to human ratification in Slack.",
    transport_security=_security,
)


@mcp.tool()
def search_decisions(query: str, status: str = "ratified") -> list[dict]:
    """Semantic search over the decision canon. Returns matching rulings (id/title/statement/status)."""
    hits = canon.search_local(query, k=5, status=status)
    return [
        {"id": h["id"], "title": h["title"], "statement": h["statement"],
         "status": h["status"], "decided_at": h.get("decided_at")}
        for h in hits
    ]


@mcp.tool()
def get_decision(id: str) -> dict:
    """Full decision object with lineage (ancestors + descendants)."""
    d = canon.get_with_lineage(id)
    return d if d is not None else {"error": "not_found", "id": id}


@mcp.tool()
def check_conflict(proposed_action: str) -> dict:
    """Check a proposed action against the canon (the SAME Sentinel path Slack uses)."""
    res = check_claim(proposed_action)
    verdict = "conflict" if res["verdict"] == "conflict" else "clear"
    return {
        "verdict": verdict,
        "conflicts": [
            {"id": c["id"], "title": c["title"], "statement": c["statement"],
             "confidence": round(c["confidence"], 2), "reason": c["reason"]}
            for c in res["conflicts"]
        ],
    }


@mcp.tool()
def propose_decision(title: str, statement: str, rationale: str = "") -> dict:
    """Propose a new decision. Creates a PROPOSED row and posts a Ratify card in Slack.

    Nothing is ratified by this call — a human must Approve in Slack.
    """
    pid = canon.create_proposed(
        {"title": title, "statement": statement, "rationale": rationale or None, "evidence": []}
    )
    _post_ratify_card(pid)
    log.info("mcp.propose_decision", id=pid)
    return {"id": pid, "status": "proposed", "note": "awaiting human ratification in Slack"}


def _post_ratify_card(decision_id: str) -> None:
    if not (settings.slack_bot_token and settings.decisions_channel):
        return
    try:
        from slack_sdk import WebClient

        from precedent.slack.blocks.ratify_card import ratify_card

        decision = canon.get_with_lineage(decision_id)
        WebClient(token=settings.slack_bot_token).chat_postMessage(
            channel=settings.decisions_channel,
            blocks=ratify_card(decision),
            text=f"An agent proposed {decision_id} — ratify?",
        )
    except Exception as e:  # noqa: BLE001
        log.warning("mcp.card_post_error", error=str(e)[:150])


def main() -> None:
    configure_logging()
    import uvicorn
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    from precedent.mcp.auth import BearerAuthMiddleware

    async def _healthz(_request):
        return JSONResponse({"status": "ok", "service": "precedent-mcp"})

    import os

    # Railway/Render/Fly inject $PORT; prefer it so the service "just works" on deploy,
    # falling back to MCP_PORT (8933) for local runs.
    port = int(os.environ.get("PORT") or settings.mcp_port)

    app = mcp.streamable_http_app()
    app.router.routes.append(Route("/healthz", _healthz))
    app.add_middleware(BearerAuthMiddleware, token=settings.mcp_bearer_token)
    log.info("mcp.boot", port=port, auth=bool(settings.mcp_bearer_token))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    main()
