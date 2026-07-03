"""Seed the 12 Lumina Labs canon rulings directly into the store (narrative dates + embeddings).

Scaled-down honest version of "mined 90 days": we direct-insert ratified rulings so the drift
landmines fire. Embeddings are batched (1 Voyage call) to respect the free-tier 3 RPM limit.

Usage:  python scripts/seed/insert_canon.py        (--wipe clears the team's canon first)
"""
from __future__ import annotations

import sys
from datetime import date

from sqlalchemy import text

from precedent.config import settings
from precedent.db.client import get_engine, session_scope
from precedent.db.schema import Decision
from precedent.services.embeddings import embed_batch

# (id, title, statement, scope, decided_at, rationale, dissent, supersedes_id, superseded_by)
RULINGS = [
    ("PRE-003", "Pricing page owns discount copy", "The pricing page owns all discount copy.",
     "product", date(2026, 4, 8), "One source of truth for pricing language.", [], None, None),
    ("PRE-006", "MySQL default (superseded)", "New services default to MySQL.",
     "engineering", date(2026, 4, 2), "Historical default before the Postgres standard.", [], None, "PRE-014"),
    ("PRE-011", "No new discount tiers", "No new discount tiers or promotions until the Q4 pricing review.",
     "growth", date(2026, 5, 10), "Protect margin until pricing is revisited.", [], None, None),
    ("PRE-012", "Errors go through copy review", "All customer-facing error messages go through copy review before shipping.",
     "product", date(2026, 5, 12), "Raw stack traces leaked to users last quarter.", [], None, None),
    ("PRE-013", "Billing changes need feature flags", "Any backend change touching billing must be behind a feature flag.",
     "engineering", date(2026, 5, 15), "Billing incidents must be instantly reversible.", [], None, None),
    ("PRE-014", "Postgres for new services", "All new services use Postgres.",
     "engineering", date(2026, 5, 3), "Operational consistency; supersedes the MySQL default.",
     [{"author": "Devon", "summary": "Preferred managed Mongo for analytics ingest"}], "PRE-006", None),
    ("PRE-015", "Design tokens only", "Components use design tokens only; no raw hex values.",
     "design", date(2026, 5, 20), "Consistent theming and dark mode.", [], None, None),
    ("PRE-016", "No meetings Wednesdays", "No meetings are scheduled on Wednesdays.",
     "ops", date(2026, 5, 22), "Protected deep-work day.", [], None, None),
    ("PRE-017", "EU data residency", "All EU analytics data must stay in EU data-residency regions.",
     "engineering", date(2026, 6, 1), "GDPR compliance for the analytics pipeline.", [], None, None),
    ("PRE-018", "Changelog per release", "Every release requires a changelog entry.",
     "ops", date(2026, 6, 5), "Customers and support need release visibility.", [], None, None),
    ("PRE-020", "Support SLA 4h", "Support first-response SLA is 4 hours.",
     "ops", date(2026, 6, 12), "Customer trust and retention.", [], None, None),
    ("PRE-021", "Register A/B tests", "All A/B tests must be registered in #growth before launch.",
     "growth", date(2026, 6, 18), "Avoid overlapping experiments and skewed metrics.", [], None, None),
]


def main() -> None:
    tid = settings.team_id
    if "--wipe" in sys.argv:
        with get_engine().begin() as c:
            c.execute(text("DELETE FROM decisions WHERE team_id = :t"), {"t": tid})
        print(f"wiped canon for team '{tid}'")

    vecs = embed_batch([f"{t}. {s}" for _, t, s, *_ in RULINGS])  # one batched Voyage call
    with session_scope() as sess:
        for (pid, title, statement, scope, decided_at, rationale, dissent, sup_id, sup_by), vec in zip(RULINGS, vecs):
            status = "superseded" if sup_by else "ratified"
            sess.merge(Decision(
                id=pid, title=title, statement=statement, rationale=rationale, scope=scope,
                status=status, ratified_by="seed", decided_by=["priya"], dissent=dissent or [],
                supersedes_id=sup_id, superseded_by=sup_by, evidence=[], embedding=vec,
                decided_at=decided_at, team_id=tid,
            ))
    print(f"seeded {len(RULINGS)} rulings into '{tid}' (PRE-006 superseded by PRE-014).")


if __name__ == "__main__":
    main()
