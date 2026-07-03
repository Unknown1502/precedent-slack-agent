"""Extractor: a Slack thread -> a structured Decision Object (proposed), via MODEL_REASON."""
from __future__ import annotations

import json

from precedent.services import canon
from precedent.services.llm import complete_json, load_prompt
from precedent.telemetry import get_logger

log = get_logger("extractor")

_name_cache: dict[str, str] = {}
_SKIP_SUBTYPES = {"channel_join", "channel_leave", "bot_message"}


def _display_name(client, user_id: str | None) -> str:
    if not user_id:
        return "unknown"
    if user_id in _name_cache:
        return _name_cache[user_id]
    try:
        info = client.users_info(user=user_id)["user"]
        name = info.get("profile", {}).get("real_name") or info.get("name") or user_id
    except Exception:
        name = user_id
    _name_cache[user_id] = name
    return name


def fetch_thread(client, channel: str, ts: str) -> tuple[str, list[dict]]:
    """Return (thread_root_ts, [{author, text, permalink}]). ts may be any msg in the thread."""
    resp = client.conversations_replies(channel=channel, ts=ts, limit=50)
    messages = resp.get("messages", [])
    root_ts = messages[0]["ts"] if messages else ts
    out: list[dict] = []
    for m in messages:
        if m.get("subtype") in _SKIP_SUBTYPES:
            continue
        try:
            permalink = client.chat_getPermalink(channel=channel, message_ts=m["ts"]).get("permalink")
        except Exception:
            permalink = None
        out.append(
            {
                "author": _display_name(client, m.get("user")) if m.get("user") else m.get("username", "unknown"),
                "text": m.get("text", ""),
                "permalink": permalink,
            }
        )
    return root_ts, out


def extract_from_thread(client, channel: str, ts: str) -> dict | None:
    """Run the Extractor on a thread. Returns the created proposed decision (with lineage) or None."""
    root_ts, messages = fetch_thread(client, channel, ts)
    if not messages:
        return None
    system = load_prompt("extractor")
    obj = complete_json(system, json.dumps(messages, ensure_ascii=False), temperature=0.2, max_tokens=1024)
    if not obj.get("is_decision"):
        log.info("extractor.not_a_decision", channel=channel, ts=root_ts)
        return None

    # Map the extractor's permalink evidence back to evidence objects.
    valid_links = {m["permalink"] for m in messages if m["permalink"]}
    evidence = [{"permalink": p} for p in (obj.get("evidence") or []) if p in valid_links]
    if not evidence:  # fall back to the thread root permalink
        root = next((m for m in messages if m["permalink"]), None)
        if root:
            evidence = [{"permalink": root["permalink"]}]

    decision = {
        "title": obj["title"],
        "statement": obj["statement"],
        "rationale": obj.get("rationale"),
        "alternatives": obj.get("alternatives") or [],
        "dissent": obj.get("dissent") or [],
        "decided_by": obj.get("decided_by") or [],
        "scope": obj.get("scope"),
        "expires_hint": obj.get("expires_hint"),
        "evidence": evidence,
    }
    pid = canon.create_proposed(decision)
    log.info("extractor.proposed", id=pid, channel=channel, root_ts=root_ts)
    return canon.get_with_lineage(pid)
