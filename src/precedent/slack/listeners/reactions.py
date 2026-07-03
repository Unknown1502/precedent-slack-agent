"""⚖️ (:scales:) reaction on a message -> Extractor -> Ratify card (manual capture, F1)."""
from __future__ import annotations

from slack_bolt import App

from precedent.slack.capture import propose_and_post
from precedent.telemetry import get_logger, new_correlation_id

log = get_logger("reactions")


def register(app: App) -> None:
    @app.event("reaction_added")
    def on_scales(event, client, context):
        new_correlation_id()
        if event.get("reaction") != "scales":
            return
        if event.get("user") and event.get("user") == context.get("bot_user_id"):
            return  # ignore our own reactions (G4)
        item = event.get("item", {})
        if item.get("type") != "message":
            return
        propose_and_post(client, item["channel"], item["ts"], notify_user=event.get("user"))
