"""Apply ddl.sql to the configured database. Idempotent (CREATE ... IF NOT EXISTS).

Usage:  python -m precedent.db.migrate
"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from precedent.config import settings
from precedent.db.client import get_engine
from precedent.db.schema import ALL_TABLES
from precedent.telemetry import get_logger

log = get_logger("migrate")
DDL_PATH = Path(__file__).with_name("ddl.sql")


def render_ddl() -> str:
    ddl = DDL_PATH.read_text(encoding="utf-8")
    return ddl.replace("__EMBED_DIM__", str(settings.embed_dim))


def main() -> None:
    settings.require("database_url")
    engine = get_engine()
    ddl = render_ddl()
    with engine.begin() as conn:
        conn.execute(text(ddl))
    # Verify every table is queryable (Phase 0 acceptance).
    with engine.connect() as conn:
        for tbl in ALL_TABLES:
            count = conn.execute(text(f"SELECT count(*) FROM {tbl}")).scalar_one()
            log.info("table.ready", table=tbl, rows=count)
    log.info("migrate.done", embed_dim=settings.embed_dim, tables=list(ALL_TABLES))


if __name__ == "__main__":
    main()
