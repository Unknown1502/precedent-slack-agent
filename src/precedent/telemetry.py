"""Structured logging with per-event correlation ids (Playbook: judge-readable telemetry)."""
from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar

import structlog

_cid: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_configured = False


def _inject_cid(_logger, _method, event_dict):
    cid = _cid.get()
    if cid:
        event_dict.setdefault("cid", cid)
    return event_dict


def configure_logging(level: str = "INFO") -> None:
    global _configured
    if _configured:
        return
    # Windows consoles default to cp1252 — force UTF-8 so emoji in logs never crash stdout.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    logging.basicConfig(format="%(message)s", level=getattr(logging, level.upper(), logging.INFO))
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _inject_cid,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level.upper(), 20)),
        cache_logger_on_first_use=True,
    )
    _configured = True


def new_correlation_id() -> str:
    """Start a new correlation scope for one inbound event; returns the id."""
    cid = uuid.uuid4().hex[:12]
    _cid.set(cid)
    return cid


def get_logger(name: str = "precedent"):
    if not _configured:
        configure_logging()
    return structlog.get_logger(name)
