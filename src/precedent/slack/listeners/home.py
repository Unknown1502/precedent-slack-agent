"""App Home: live dashboard (stats, pending queue, drift feed, Register) + approve-from-home."""
from __future__ import annotations

from slack_bolt import App

from precedent.config import settings
from precedent.services import canon, canvas
from precedent.slack.blocks.app_home import home_view
from precedent.telemetry import get_logger, new_correlation_id

log = get_logger("home")


def publish_home(client, user: str) -> None:
    view = home_view(
        stats=canon.counts(),
        pending=canon.list_pending(),
        drift=canon.recent_drift(),
        canvas_id=canon.get_meta("canvas_id") or None,
    )
    client.views_publish(user_id=user, view=view)


def register(app: App) -> None:
    @app.event("app_home_opened")
    def handle_home_opened(event, client):
        new_correlation_id()
        publish_home(client, event["user"])
        log.info("home.published", user=event["user"], **canon.counts())

    @app.action("home_approve")
    def handle_home_approve(ack, body, client, action):
        ack()
        new_correlation_id()
        decision_id, user = action["value"], body["user"]["id"]
        try:
            canon.ratify(decision_id, user)  # idempotent
            canvas.sync(client, settings.team_id)
        except ValueError:
            pass
        publish_home(client, user)
        log.info("home.approved", id=decision_id, by=user)
