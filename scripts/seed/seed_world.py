"""Seed the Lumina Labs story arcs into Slack and wire real permalinks into the canon's evidence.

Posts persona messages (chat.postMessage + username/icon_emoji customize — needs chat:write.customize),
collects permalinks via chat.getPermalink, then UPDATEs each ruling's evidence in the DB.
Bot-authored posts carry bot_id, so the Gatekeeper's G4 filters ignore them.

Prereqs: channels #eng-platform #pricing #growth #decisions exist and @precedent is invited.
Usage:   python scripts/seed/seed_world.py            (one-shot; guarded by meta['seed_world_done'])
         python scripts/seed/seed_world.py --force    (bypass the guard — posts duplicates!)
"""
from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

from slack_sdk import WebClient

from precedent.config import settings
from precedent.db.client import session_scope
from precedent.db.schema import Decision
from precedent.services import canon
from precedent.telemetry import configure_logging, get_logger

log = get_logger("seed.world")

PERSONAS = {
    "priya": ("Priya Sharma", ":woman_technologist:"),
    "devon": ("Devon Okafor", ":bar_chart:"),
    "marco": ("Marco Reyes", ":rocket:"),
    "sana": ("Sana Kim", ":art:"),
    "ling": ("Ling Chen", ":hammer_and_wrench:"),
    "tomas": ("Tomas Novak", ":chart_with_upwards_trend:"),
    "aisha": ("Aisha Bello", ":headphones:"),
}

# Each arc: channel name, messages [(persona, text, in_thread)], evidence {ruling_id: [msg indices]}.
# First message is always the thread root; in_thread=True replies to it.
ARCS = [
    {
        "channel": "eng-platform",
        "messages": [
            ("priya", "(May 1) Revisiting our datastore default. The early-April MySQL ruling is creaking — "
                      "replication lag on analytics ingest keeps paging us, and we already run three Postgres "
                      "instances for other services anyway.", False),
            ("ling", "+1. The JSONB story alone would simplify the events schema, and we'd stop maintaining "
                     "two flavors of migrations.", True),
            ("devon", "I'd rather go managed Mongo for the analytics ingest specifically — ops burden is lower "
                      "and it fits the document shape. Costs pencil out too.", True),
            ("tomas", "Managed Mongo means a second backup/restore playbook and another driver in every service. "
                      "Postgres read replicas cover the ingest load we actually have.", True),
            ("priya", "Decision (May 3): *all new services use Postgres.* One operational playbook, one backup "
                      "story. Devon's managed-Mongo preference is recorded as dissent — we revisit if ingest "
                      "outgrows replicas. This supersedes the MySQL default.", True),
        ],
        "evidence": {"PRE-014": [0, 4], "PRE-006": [0]},
    },
    {
        "channel": "eng-platform",
        "messages": [
            ("ling", "(May 14) Postmortem from Tuesday's billing incident: the retry change went straight to "
                     "prod with no kill switch. Took us 40 minutes to roll back under load.", False),
            ("devon", "We refunded 40 customers and burned a week of support goodwill. This can't repeat.", True),
            ("priya", "Decision (May 15): *any backend change touching billing ships behind a feature flag.* "
                      "No exceptions, no matter how tiny the diff looks.", True),
        ],
        "evidence": {"PRE-013": [0, 2]},
    },
    {
        "channel": "eng-platform",
        "messages": [
            ("tomas", "(May 30) Legal flagged the analytics pipeline: EU customer events are currently "
                      "co-mingled with the US cluster. That's a GDPR problem, not a nice-to-have.", False),
            ("devon", "Fines at our stage would be existential. We fix routing before anything else ships "
                      "from this team.", True),
            ("priya", "Decision (Jun 1): *all EU analytics data stays in EU data-residency regions* "
                      "(Frankfurt). Pipeline routing fix is this sprint's top priority.", True),
        ],
        "evidence": {"PRE-017": [0, 2]},
    },
    {
        "channel": "pricing",
        "messages": [
            ("sana", "(Apr 7) Found three different discount blurbs live right now: landing page says 20%, "
                     "checkout says 15%, and the drip emails promise 'up to 25%'. Customers are screenshotting.", False),
            ("marco", "That's... not great. My fault partly — we shipped the email copy without checking.", True),
            ("devon", "Decision (Apr 8): *the pricing page owns ALL discount copy.* Everything else links to "
                      "it, never restates it. One source of truth.", True),
        ],
        "evidence": {"PRE-003": [0, 2]},
    },
    {
        "channel": "pricing",
        "messages": [
            ("marco", "(May 9) Proposal: 20% education discount to juice Q3 signups. Competitors all have one "
                      "and we keep losing student-heavy teams at checkout.", False),
            ("devon", "Margin is already thin and we have a full pricing review scheduled for Q4. Adding tiers "
                      "now means re-doing that work twice.", True),
            ("priya", "Decision (May 10): *no new discount tiers or promotions until the Q4 pricing review.* "
                      "Marco — bring the edu-discount data to that review, it's a strong candidate.", True),
        ],
        "evidence": {"PRE-011": [0, 2]},
    },
    {
        "channel": "growth",
        "messages": [
            ("marco", "(Jun 17) Two overlapping experiments just collided on the signup page — the pricing test "
                      "and the onboarding test shared a control group. Both datasets are contaminated.", False),
            ("tomas", "Confirmed, we can't trust either result. Three weeks of traffic wasted.", True),
            ("marco", "Decision (Jun 18): *every A/B test gets registered in #growth before launch.* Registry "
                      "pinned to the channel. No registration, no launch.", True),
        ],
        "evidence": {"PRE-021": [0, 2]},
    },
    {
        "channel": "all-lumina-labs",
        "messages": [
            ("sana", "(May 21) I had SEVEN meetings yesterday and shipped exactly nothing. Calendar looks like "
                     "a Tetris board someone lost.", False),
            ("priya", "Same. I haven't had a two-hour focus block in two weeks.", True),
            ("devon", "Decision (May 22): *Wednesdays are meeting-free deep-work days, org-wide.* Defend them. "
                      "Recurring invites on Wednesdays get declined automatically.", True),
        ],
        "evidence": {"PRE-016": [0, 2]},
    },
    # Single-message rulings — one decisive post each, so every ruling has real evidence.
    {
        "channel": "all-lumina-labs",
        "messages": [
            ("aisha", "(May 12) Following last quarter's stack-trace leak: decision — *every customer-facing "
                      "error message goes through copy review before it ships.* Sana's team owns the review.", False),
        ],
        "evidence": {"PRE-012": [0]},
    },
    {
        "channel": "all-lumina-labs",
        "messages": [
            ("sana", "(May 20) Design decision, effective now: *components use design tokens only — no raw hex "
                      "values.* Dark mode work starts next sprint and hardcoded colors will break it.", False),
        ],
        "evidence": {"PRE-015": [0]},
    },
    {
        "channel": "eng-platform",
        "messages": [
            ("priya", "(Jun 5) Release hygiene: *every release requires a changelog entry* from now on. Support "
                      "keeps getting surprised by our own ships.", False),
        ],
        "evidence": {"PRE-018": [0]},
    },
    {
        "channel": "all-lumina-labs",
        "messages": [
            ("aisha", "(Jun 12) Support commitment, agreed with leadership: *first response within 4 hours* on "
                      "all paid-plan tickets. Dashboards updated to track it.", False),
        ],
        "evidence": {"PRE-020": [0]},
    },
]


def resolve_channels(client: WebClient) -> dict[str, str]:
    """Map channel name -> id for public channels the bot can see."""
    out: dict[str, str] = {}
    cursor = None
    while True:
        resp = client.conversations_list(limit=200, cursor=cursor, types="public_channel")
        for ch in resp["channels"]:
            out[ch["name"]] = ch["id"]
        cursor = resp.get("response_metadata", {}).get("next_cursor") or None
        if not cursor:
            break
    return out


def main() -> None:
    configure_logging()
    force = "--force" in sys.argv
    if canon.get_meta("seed_world_done") and not force:
        print("seed_world already ran (meta['seed_world_done'] set). Re-running would post duplicate "
              "messages — use --force only against a fresh channel set.")
        return

    settings.require("slack_bot_token")
    client = WebClient(token=settings.slack_bot_token)
    channels = resolve_channels(client)

    needed = {arc["channel"] for arc in ARCS}
    missing = sorted(n for n in needed if n not in channels)
    if missing:
        print(f"MISSING CHANNELS: {missing} — create them and /invite @precedent, then re-run.")
        return

    evidence_map: dict[str, list[dict]] = {}
    posted = 0
    for arc in ARCS:
        ch_id = channels[arc["channel"]]
        root_ts: str | None = None
        permalinks: list[tuple[str, str]] = []  # (ts, permalink) per message index
        for persona_key, text, in_thread in arc["messages"]:
            name, icon = PERSONAS[persona_key]
            resp = client.chat_postMessage(
                channel=ch_id,
                text=text,
                username=name,
                icon_emoji=icon,
                thread_ts=root_ts if in_thread else None,
            )
            ts = resp["ts"]
            if root_ts is None:
                root_ts = ts
            link = client.chat_getPermalink(channel=ch_id, message_ts=ts)["permalink"]
            permalinks.append((ts, link))
            posted += 1
            time.sleep(random.uniform(0.4, 0.8))  # jitter; stay well under rate limits
        for ruling_id, idxs in arc["evidence"].items():
            evidence_map.setdefault(ruling_id, []).extend(
                {"permalink": permalinks[i][1], "channel_id": ch_id, "ts": permalinks[i][0]}
                for i in idxs
            )
        log.info("seed.arc_posted", channel=arc["channel"], messages=len(arc["messages"]))

    # Wire real permalinks into the canon.
    with session_scope() as s:
        for ruling_id, ev in evidence_map.items():
            d = s.get(Decision, ruling_id)
            if d is not None:
                d.evidence = ev
                log.info("seed.evidence_wired", id=ruling_id, links=len(ev))

    canon.set_meta("seed_world_done", "1")
    out_path = Path(__file__).with_name("seed-output.json")
    out_path.write_text(json.dumps(evidence_map, indent=2), encoding="utf-8")
    print(f"posted {posted} messages across {len(needed)} channels; "
          f"evidence wired for {len(evidence_map)} rulings; map -> {out_path.name}")


if __name__ == "__main__":
    main()
