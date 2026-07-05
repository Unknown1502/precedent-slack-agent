"""Slash command: /precedent (help | log | backfill). Phase 0 wires `help`."""
from __future__ import annotations

from slack_bolt import App

from precedent.services import canon
from precedent.telemetry import get_logger, new_correlation_id

log = get_logger("cmd")


def _help_blocks() -> list[dict]:
    return [
        {"type": "header", "text": {"type": "plain_text", "text": "⚖️ Precedent", "emoji": True}},
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "*Institutional memory, enforced.*"}],
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*Commands*\n"
                    "• `/precedent help` — this message\n"
                    "• `/precedent log` — inside a thread, capture it as a decision _(Phase 1)_\n"
                    "• `/precedent backfill` — mine history into proposed rulings _(Phase 7)_\n\n"
                    "React :scales: on a thread to propose a decision. "
                    "Nothing enters canon without a human approval."
                ),
            },
        },
    ]


def register(app: App) -> None:
    @app.command("/precedent")
    def handle_precedent(ack, command, respond, client):
        # ack() first — Slack requires a response within 3s (Gotcha G6).
        ack()
        new_correlation_id()
        text = (command.get("text") or "").strip()
        sub = text.split()[0].lower() if text else "help"
        log.info("cmd.precedent", sub=sub, user=command.get("user_id"))

        if sub in ("", "help"):
            respond(blocks=_help_blocks(), text="Precedent — help")
        elif sub == "log":
            respond(
                text=":scales: To capture a decision, *react* :scales: *on the message where the call "
                "was made.* (Slack slash commands can't see which thread you're in — the reaction can.) "
                "I'll extract it and post a ratify card in that thread."
            )
        elif sub == "enroll":
            canon.set_enrollment(command["channel_id"], "observe")
            respond(text=":eye: Now *observing* this channel — I'll watch for decision moments and drift. "
                    "Use `/precedent unenroll` to stop.")
        elif sub == "unenroll":
            canon.set_enrollment(command["channel_id"], "manual_only")
            respond(text="Stopped observing this channel. Manual capture with :scales: still works.")
        elif sub == "digest":
            from precedent.slack.blocks.digest import digest_blocks
            client.chat_postMessage(
                channel=command["channel_id"],
                blocks=digest_blocks(canon.counts(), canon.list_ratified(), canon.recent_drift()),
                text="Precedent — weekly digest",
            )
            respond(text="Posted the weekly digest to this channel. :scales:")
        elif sub == "backfill":
            from precedent.slack.backfill import run as run_backfill

            respond(text=":pick: Mining this channel's history for un-captured decisions…")
            result = run_backfill(client, command["channel_id"], action_token=None)
            if result["proposed"]:
                respond(text=f":scales: Proposed {len(result['proposed'])} ruling(s): "
                        f"{', '.join(result['proposed'])} — ratify cards posted in their threads. "
                        f"_(RTS: {result['rts_note']})_")
            else:
                respond(text="No new decision threads found in recent history. "
                        f"_(scanned {result['scanned_threads']} threads · RTS: {result['rts_note']})_")
        else:
            respond(text=f"Unknown subcommand `{sub}`. Try `/precedent help`.")
