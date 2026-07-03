"""Ratify card actions: Approve / Edit / Dismiss. All idempotent (Slack retries + double-clicks)."""
from __future__ import annotations

import json

from slack_bolt import App

from precedent.config import settings
from precedent.services import canon, canvas
from precedent.slack.blocks.decision_card import decision_card
from precedent.slack.blocks.ratify_card import dismissed_note, ratify_card, ratified_confirmation
from precedent.telemetry import get_logger, new_correlation_id

log = get_logger("actions")


def _supersede_modal(drift_id: int, old_id: str, claim: str, home_channel: str) -> dict:
    return {
        "type": "modal",
        "callback_id": "drift_supersede_submit",
        "private_metadata": json.dumps({"drift": drift_id, "old": old_id, "channel": home_channel}),
        "title": {"type": "plain_text", "text": "Propose supersede"},
        "submit": {"type": "plain_text", "text": "Propose"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"Proposing to *supersede {old_id}*. This creates a "
                         "*proposed* ruling a human must ratify — nothing changes until then."},
            },
            {
                "type": "input", "block_id": "title",
                "label": {"type": "plain_text", "text": "New ruling title"},
                "element": {"type": "plain_text_input", "action_id": "v"},
            },
            {
                "type": "input", "block_id": "statement",
                "label": {"type": "plain_text", "text": "New statement"},
                "element": {"type": "plain_text_input", "action_id": "v", "multiline": True,
                            "initial_value": claim},
            },
            {
                "type": "input", "block_id": "rationale", "optional": True,
                "label": {"type": "plain_text", "text": "Rationale"},
                "element": {"type": "plain_text_input", "action_id": "v", "multiline": True},
            },
        ],
    }


def _edit_modal(decision_id: str, channel: str, ts: str, d: dict) -> dict:
    return {
        "type": "modal",
        "callback_id": "ratify_edit_submit",
        "private_metadata": json.dumps({"id": decision_id, "channel": channel, "ts": ts}),
        "title": {"type": "plain_text", "text": "Edit decision"},
        "submit": {"type": "plain_text", "text": "Approve"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "title",
                "label": {"type": "plain_text", "text": "Title"},
                "element": {"type": "plain_text_input", "action_id": "v", "initial_value": d["title"]},
            },
            {
                "type": "input",
                "block_id": "statement",
                "label": {"type": "plain_text", "text": "Statement"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "v",
                    "multiline": True,
                    "initial_value": d["statement"],
                },
            },
            {
                "type": "input",
                "block_id": "rationale",
                "optional": True,
                "label": {"type": "plain_text", "text": "Rationale"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "v",
                    "multiline": True,
                    "initial_value": d.get("rationale") or "",
                },
            },
        ],
    }


def register(app: App) -> None:
    @app.action("ratify_approve")
    def approve(ack, body, client, action):
        ack()  # within 3s (G6) — ratify runs after
        new_correlation_id()
        decision_id = action["value"]
        user = body["user"]["id"]
        container = body.get("container", {})
        channel, ts = container.get("channel_id"), container.get("message_ts")
        try:
            d = canon.ratify(decision_id, user)  # idempotent
        except ValueError:
            client.chat_update(channel=channel, ts=ts, text="Already resolved.",
                               blocks=dismissed_note(decision_id))
            return
        client.chat_update(channel=channel, ts=ts, text=f"Ratified {decision_id}",
                           blocks=ratified_confirmation(d, user))
        canvas.sync(client, settings.team_id)
        log.info("actions.approved", id=decision_id, by=user)

    @app.action("ratify_dismiss")
    def dismiss(ack, body, client, action):
        ack()
        new_correlation_id()
        decision_id = action["value"]
        container = body.get("container", {})
        canon.delete_proposed(decision_id)  # idempotent (no-op if already gone/ratified)
        client.chat_update(channel=container.get("channel_id"), ts=container.get("message_ts"),
                           text="Dismissed", blocks=dismissed_note(decision_id))
        log.info("actions.dismissed", id=decision_id)

    @app.action("ratify_edit")
    def edit(ack, body, client, action):
        ack()
        new_correlation_id()
        decision_id = action["value"]
        container = body.get("container", {})
        d = canon.get_with_lineage(decision_id)
        if d is None:
            return
        client.views_open(
            trigger_id=body["trigger_id"],
            view=_edit_modal(decision_id, container.get("channel_id"), container.get("message_ts"), d),
        )

    @app.view("ratify_edit_submit")
    def edit_submit(ack, body, client, view):
        ack()
        new_correlation_id()
        meta = json.loads(view["private_metadata"])
        vals = view["state"]["values"]
        fields = {
            "title": vals["title"]["v"]["value"],
            "statement": vals["statement"]["v"]["value"],
            "rationale": vals["rationale"]["v"]["value"] or None,
        }
        user = body["user"]["id"]
        canon.update_proposed(meta["id"], fields)
        d = canon.ratify(meta["id"], user)
        client.chat_update(channel=meta["channel"], ts=meta["ts"], text=f"Ratified {meta['id']}",
                           blocks=ratified_confirmation(d, user))
        canvas.sync(client, settings.team_id)
        log.info("actions.edited_ratified", id=meta["id"], by=user)

    # ── drift card actions ──────────────────────────────────────────────
    @app.action("drift_view")
    def drift_view(ack, body, client, action):
        ack()
        new_correlation_id()
        d = canon.get_with_lineage(action["value"])
        if d is None:
            return
        client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "title": {"type": "plain_text", "text": "Ruling"},
                "close": {"type": "plain_text", "text": "Close"},
                "blocks": decision_card(d),
            },
        )

    @app.action("drift_aligned")
    def drift_aligned(ack, body, action, respond):
        ack()
        new_correlation_id()
        canon.resolve_drift(int(action["value"]), "aligned")
        respond(
            replace_original=True,
            text="Thanks for confirming — noted as aligned.",
            blocks=[{"type": "context", "elements": [
                {"type": "mrkdwn", "text": "✅ Thanks — marked as *aligned*. Carry on."}]}],
        )
        log.info("actions.drift_aligned", drift=action["value"])

    @app.action("drift_supersede")
    def drift_supersede(ack, body, client, action):
        ack()
        new_correlation_id()
        drift = canon.get_drift(int(action["value"]))
        if drift is None:
            return
        client.views_open(
            trigger_id=body["trigger_id"],
            view=_supersede_modal(drift["id"], drift["decision_id"], drift["claim"], drift["channel_id"]),
        )

    @app.view("drift_supersede_submit")
    def drift_supersede_submit(ack, body, client, view):
        ack()
        new_correlation_id()
        meta = json.loads(view["private_metadata"])
        vals = view["state"]["values"]
        new_obj = {
            "title": (vals["title"]["v"]["value"] or "Superseding ruling").strip(),
            "statement": vals["statement"]["v"]["value"].strip(),
            "rationale": (vals["rationale"]["v"]["value"] or None),
            "supersedes_id": meta["old"],
        }
        pid = canon.create_proposed(new_obj)
        canon.resolve_drift(meta["drift"], "superseded")
        decision = canon.get_with_lineage(pid)
        client.chat_postMessage(
            channel=meta["channel"],
            blocks=ratify_card(decision),
            text=f"Supersede proposed — ratify {pid}?",
        )
        log.info("actions.supersede_proposed", new=pid, supersedes=meta["old"])
