"""Archaeology-lite (F7): mine channel history into proposed rulings.

Two evidence sources, honestly separated:
- History scan (always works): conversations_history over the invoking channel -> threads with
  replies -> Extractor on the best candidates -> Ratify cards (via the shared capture path, which
  dedups per thread through the meta table).
- RTS (only when an action_token is present, i.e. the @precedent mention path — slash commands
  don't carry one): <=5 assistant.search.context question-queries to *find* decision-ish threads
  in bulk history; hits feed the same Extractor path. Degrades to history-scan-only with a logged
  reason (G1/G2).
"""
from __future__ import annotations

from precedent.services import rts
from precedent.slack.capture import propose_and_post
from precedent.telemetry import get_logger

log = get_logger("backfill")

MAX_EXTRACTIONS = 4          # LLM budget per backfill run
RTS_THEMES = [               # natural-language questions -> semantic mode when available (G2)
    "What has the team decided about databases or infrastructure?",
    "What did the team decide about pricing or discounts?",
    "What process or workflow decisions has the team made?",
]


def run(client, channel_id: str, action_token: str | None) -> dict:
    """Returns {proposed: [ids], scanned_threads, rts_used, rts_note}."""
    candidates: list[tuple[str, str]] = []  # (channel_id, thread_root_ts)

    # ── RTS pass (mention path only) ────────────────────────────────────
    rts_used, rts_note = 0, None
    if action_token:
        info = rts.info(client)
        log.info("backfill.rts_info", info=str(info)[:300])
        budget = rts.RtsBudget(5)
        for theme in RTS_THEMES:
            res = rts.search_context(client, theme, action_token, budget,
                                     context_channel_id=channel_id)
            if res["degraded"]:
                rts_note = res["degraded"]
                break
            for hit in res["results"]:
                if hit.get("channel"):
                    # RTS hits don't carry thread_ts directly; use permalink ts when parsable.
                    ts = (hit.get("permalink") or "").rsplit("/p", 1)[-1]
                    if ts.isdigit():
                        candidates.append((hit["channel"], f"{ts[:-6]}.{ts[-6:]}"))
        rts_used = budget.used
    else:
        rts_note = "no_action_token (slash-command path; mention @precedent backfill to use RTS)"
    log.info("backfill.rts", used=rts_used, note=rts_note, candidates=len(candidates))

    # ── history scan (always) ───────────────────────────────────────────
    scanned = 0
    try:
        resp = client.conversations_history(channel=channel_id, limit=100)
        for m in resp.get("messages", []):
            if m.get("reply_count", 0) >= 2 and m.get("ts"):
                candidates.append((channel_id, m["ts"]))
                scanned += 1
    except Exception as e:  # noqa: BLE001
        log.warning("backfill.history_error", error=str(e)[:150])

    # ── extract the best candidates (dedup happens inside propose_and_post) ──
    proposed: list[str] = []
    seen: set[tuple[str, str]] = set()
    for ch, ts in candidates:
        if len(proposed) >= MAX_EXTRACTIONS:
            break
        if (ch, ts) in seen:
            continue
        seen.add((ch, ts))
        decision = propose_and_post(client, ch, ts)
        if decision:
            proposed.append(decision["id"])

    log.info("backfill.done", proposed=proposed, scanned_threads=scanned, rts_used=rts_used)
    return {"proposed": proposed, "scanned_threads": scanned, "rts_used": rts_used, "rts_note": rts_note}
