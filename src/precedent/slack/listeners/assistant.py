"""Archivist assistant thread (Bolt Assistant): split-view Q&A over the canon.

Registered via app.assistant(assistant) (NOT app.use). Streams the answer with say_stream.
"""
from __future__ import annotations

from slack_bolt import Assistant

from precedent.agents import archivist
from precedent.telemetry import get_logger, new_correlation_id

log = get_logger("assistant")

_GREETING = (
    "I'm Precedent's *Archivist*. Ask what the team has decided and *why* — "
    "I answer from the ratified canon, always cited to the ruling."
)
_STARTER_PROMPTS = [
    {"title": "Why Postgres?", "message": "Why do we use Postgres for new services?"},
    {"title": "Discount policy", "message": "What's our policy on discounts and promotions?"},
    {"title": "Recent rulings", "message": "What has the team decided recently?"},
]


def _find_action_token(body: dict) -> str | None:
    # action_token (for RTS) may ride on the event payload; check known spots, else None (G1).
    if not isinstance(body, dict):
        return None
    for key in ("action_token",):
        if body.get(key):
            return body[key]
    event = body.get("event", {})
    return event.get("action_token") if isinstance(event, dict) else None


def build_assistant() -> Assistant:
    assistant = Assistant()

    @assistant.thread_started
    def on_start(say, set_suggested_prompts):
        new_correlation_id()
        say(_GREETING)
        set_suggested_prompts(prompts=_STARTER_PROMPTS)

    @assistant.user_message
    def on_message(payload, say, say_stream, set_status, set_suggested_prompts, set_title, client, body):
        new_correlation_id()
        query = (payload.get("text") or "").strip()
        if not query:
            return
        set_status("consulting the case law…")
        action_token = _find_action_token(body)
        try:
            stream = say_stream()
            got = False
            for chunk in archivist.answer_stream(query, client, action_token):
                stream.append(markdown_text=chunk)
                got = True
            stream.stop()
            if not got:
                say("I couldn't find anything relevant in the canon yet.")
        except Exception as e:  # noqa: BLE001 — never leave the thread hanging
            log.warning("assistant.error", error=str(e)[:200])
            say("Something went wrong composing that answer — please try again.")
        try:
            set_suggested_prompts(prompts=archivist.suggested_followups(query))
            set_title(query[:60])
        except Exception:
            pass
        log.info("assistant.answered", query=query[:60])

    return assistant
