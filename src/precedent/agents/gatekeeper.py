"""Gatekeeper: fast per-message classifier (MODEL_GATE). decision_moment | assertive_claim | neither."""
from __future__ import annotations

import time

from precedent.config import settings
from precedent.services.llm import complete_json, load_prompt
from precedent.telemetry import get_logger

log = get_logger("gatekeeper")

VALID = {"decision_moment", "assertive_claim", "neither"}


def classify(message_text: str, context_msgs: list[str] | None = None) -> dict:
    """Return {label, confidence, latency_ms}. Never raises — defaults to 'neither' on error."""
    system = load_prompt("gatekeeper")
    parts = []
    if context_msgs:
        parts.append("Prior thread context:\n" + "\n".join(f"- {m}" for m in context_msgs[-6:]))
    parts.append("Message to classify:\n" + message_text)
    user = "\n\n".join(parts)

    t0 = time.perf_counter()
    try:
        out = complete_json(
            system, user, model=settings.model_gate, temperature=0, max_tokens=60, timeout=10
        )
        label = out.get("label", "neither")
        if label not in VALID:
            label = "neither"
        conf = float(out.get("confidence", 0.0))
    except Exception as e:  # noqa: BLE001 — hot path must never crash a channel
        log.warning("gatekeeper.error", error=str(e)[:150])
        label, conf = "neither", 0.0
    latency_ms = int((time.perf_counter() - t0) * 1000)
    log.info("gatekeeper.classified", label=label, confidence=round(conf, 2), latency_ms=latency_ms)
    return {"label": label, "confidence": conf, "latency_ms": latency_ms}
