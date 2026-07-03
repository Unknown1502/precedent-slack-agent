"""Bolt app init with a Socket/HTTP switch. Phase 0: boot + /precedent + App Home stub."""
from __future__ import annotations

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from precedent.config import settings
from precedent.slack.listeners import actions, assistant, commands, home, messages, reactions
from precedent.telemetry import configure_logging, get_logger

log = get_logger("slack.app")


def build_app(token_verification: bool = True) -> App:
    """Construct the Bolt app and register listeners.

    token_verification=False lets us construct/import the app offline (tests, CI)
    without calling Slack's auth.test. Bolt still requires *some* token string to
    construct, so we supply a placeholder that is never used for a network call.
    """
    token = settings.slack_bot_token or (None if token_verification else "xoxb-offline-construct")
    app = App(
        token=token,
        # Socket Mode does not use the signing secret; a placeholder avoids BoltError.
        signing_secret=settings.slack_signing_secret or "socket-mode-placeholder",
        token_verification_enabled=token_verification,
        raise_error_for_unhandled_request=False,
    )
    commands.register(app)
    home.register(app)
    reactions.register(app)
    actions.register(app)
    messages.register(app)
    app.assistant(assistant.build_assistant())  # Archivist split-view (NOT app.use)
    return app


def main() -> None:
    configure_logging()
    settings.require("slack_bot_token", "slack_app_token")
    app = build_app(token_verification=True)
    log.info("slack.boot", mode="socket", team_id=settings.team_id)
    SocketModeHandler(app, settings.slack_app_token).start()


if __name__ == "__main__":
    main()
