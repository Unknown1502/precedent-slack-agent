"""Engine/session factory. Lazily built so importing the package never requires a DB."""
from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from precedent.config import settings

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _normalize_url(url: str) -> str:
    """Force the psycopg3 driver so both Neon and local URLs work identically."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        settings.require("database_url")
        _engine = create_engine(_normalize_url(settings.database_url), pool_pre_ping=True)
    return _engine


def get_sessionmaker() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _SessionLocal


@contextmanager
def session_scope():
    """Transactional session context: commit on success, rollback on error."""
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
