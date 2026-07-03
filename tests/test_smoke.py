"""Fast, dependency-free unit tests (no DB/LLM/network). Run: pytest tests/test_smoke.py"""
from precedent.services.llm import _extract_json
from precedent.slack.blocks.app_home import home_view
from precedent.slack.blocks.decision_card import decision_card
from precedent.slack.blocks.drift_card import drift_card
from precedent.slack.blocks.ratify_card import ratify_card

_D = {
    "id": "PRE-014", "title": "Postgres for new services", "statement": "All new services use Postgres.",
    "rationale": "Consistency.", "scope": "engineering", "status": "ratified", "ratified_by": "U1",
    "decided_by": ["priya"], "dissent": [{"author": "Devon", "summary": "wanted Mongo"}],
    "evidence": [{"permalink": "https://x/1"}], "ancestors": [{"id": "PRE-006"}], "descendants": [],
}


def test_extract_json_strips_fences():
    assert _extract_json('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert _extract_json('here: {"a": 1} done') == '{"a": 1}'


def test_ratify_card_shape():
    blocks = ratify_card(_D)
    assert blocks[0]["type"] == "header"
    actions = [b for b in blocks if b.get("block_id") == "ratify_actions"][0]
    assert {e["action_id"] for e in actions["elements"]} == {"ratify_approve", "ratify_edit", "ratify_dismiss"}


def test_drift_card_shape_and_privacy():
    conflict = {"id": "PRE-014", "title": "Postgres", "statement": "All new services use Postgres.",
                "confidence": 0.9, "reason": "mongo conflicts"}
    blocks = drift_card(conflict, _D, drift_id=7)
    ids = {e["action_id"] for b in blocks if b.get("block_id") == "drift_actions" for e in b["elements"]}
    assert ids == {"drift_view", "drift_supersede", "drift_aligned"}
    assert any("Only you can see this" in str(b) for b in blocks)


def test_decision_card_shows_lineage_and_dissent():
    text = str(decision_card(_D))
    assert "PRE-006" in text and "Devon" in text


def test_home_view_states():
    assert "empty" in str(home_view({"ratified": 0, "pending": 0, "drift_open": 0}))
    assert "Pending ratification" in str(
        home_view({"ratified": 1, "pending": 1, "drift_open": 0}, pending=[_D])
    )
