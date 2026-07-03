"""Contradiction eval: runs the REAL Sentinel path (Voyage embed + Groq judge) over a fixture canon.

Isolated under team_id='eval' so it never touches live data; fixtures are cleaned up after.
Embeddings are batched (2 Voyage calls total) to respect the free-tier 3 RPM limit.
Usage:  python tests/eval_runner.py
Pass bar: 12/12 conflicts caught AND 0/18 false fires.
"""
from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text

from precedent.agents.sentinel import check_claim
from precedent.db.client import get_engine, session_scope
from precedent.db.schema import Decision
from precedent.services.embeddings import embed_batch

EVAL_TEAM = "eval"

FIXTURES = [
    ("PRE-003", "Pricing page owns discount copy", "The pricing page owns all discount copy.", "product"),
    ("PRE-011", "No new discount tiers", "No new discount tiers or promotional pricing until the Q4 pricing review.", "growth"),
    ("PRE-012", "Errors go through copy review", "All customer-facing error messages go through copy review before shipping.", "product"),
    ("PRE-013", "Billing changes need feature flags", "Any backend change touching billing must be behind a feature flag.", "engineering"),
    ("PRE-014", "Postgres for new services", "All new services use Postgres.", "engineering"),
    ("PRE-015", "Design tokens only", "Components use design tokens only; no raw hex values.", "design"),
    ("PRE-016", "No meetings Wednesdays", "No meetings are scheduled on Wednesdays.", "ops"),
    ("PRE-017", "EU data residency", "All EU analytics data must stay in EU data-residency regions.", "engineering"),
    ("PRE-018", "Changelog per release", "Every release requires a changelog entry.", "ops"),
    ("PRE-020", "Support SLA 4h", "Support first-response SLA is 4 hours.", "ops"),
    ("PRE-021", "Register A/B tests", "All A/B tests must be registered in #growth before launch.", "growth"),
]


def _load_fixtures() -> None:
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM decisions WHERE team_id = :t"), {"t": EVAL_TEAM})
    vecs = embed_batch([f"{t}. {s}" for _, t, s, _ in FIXTURES])  # one Voyage call
    with session_scope() as sess:
        for (pid, title, statement, scope), vec in zip(FIXTURES, vecs):
            sess.add(Decision(id=pid, title=title, statement=statement, scope=scope,
                              status="ratified", ratified_by="eval-bot", evidence=[],
                              embedding=vec, team_id=EVAL_TEAM))


def _cleanup() -> None:
    with get_engine().begin() as c:
        c.execute(text("DELETE FROM decisions WHERE team_id = :t"), {"t": EVAL_TEAM})


def main() -> int:
    cases = [json.loads(x) for x in Path("tests/contradiction_eval.jsonl").read_text().splitlines() if x.strip()]
    print(f"Loading {len(FIXTURES)} fixture rulings (1 batched Voyage call)…")
    _load_fixtures()
    qvecs = embed_batch([c["claim"] for c in cases])  # one Voyage call for all queries

    caught = missed = false_fire = correct_null = 0
    conflicts_total = sum(1 for c in cases if c["expected"])
    rows = []
    try:
        for c, qv in zip(cases, qvecs):
            res = check_claim(c["claim"], team_id=EVAL_TEAM, query_vec=qv)
            predicted = res["conflicts"][0]["id"] if res["verdict"] == "conflict" else None
            exp = c["expected"]
            if exp:
                ok = predicted == exp
                caught += ok
                missed += not ok
            else:
                ok = predicted is None
                correct_null += ok
                false_fire += not ok
            rows.append((ok, exp, predicted, c["claim"][:52]))
    finally:
        _cleanup()

    print("\n  res | expected  | predicted | claim")
    print("  ----+-----------+-----------+" + "-" * 54)
    for ok, exp, pred, claim in rows:
        print(f"  {'PASS' if ok else 'FAIL':4}| {str(exp):9} | {str(pred):9} | {claim}")

    print(f"\nconflicts caught : {caught}/{conflicts_total}")
    print(f"false fires      : {false_fire}/{len(cases) - conflicts_total}")
    passed = caught == conflicts_total and false_fire == 0
    print(f"\n{'EVAL PASS' if passed else 'EVAL FAIL'}  ({caught + correct_null}/{len(cases)} cases correct)")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
