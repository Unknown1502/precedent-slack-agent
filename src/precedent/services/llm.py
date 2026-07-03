"""Provider-neutral LLM wrapper: load versioned prompts, call with timeout+retries, strict JSON.

Provider selected by LLM_PROVIDER (groq | anthropic | gemini). Models are provider-specific IDs
in MODEL_GATE / MODEL_REASON. The rest of the codebase only calls complete_json()/load_prompt().
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

from precedent.config import settings
from precedent.telemetry import get_logger

log = get_logger("llm")

# prompts/ lives at the repo root: src/precedent/services/llm.py -> parents[3] == repo root.
PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def load_prompt(name: str) -> str:
    """Load a versioned system prompt (never inline prompts — Playbook rule)."""
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"prompt file missing: {path}")
    return path.read_text(encoding="utf-8")


def _extract_json(text: str) -> str:
    text = _FENCE.sub("", text.strip()).strip()
    if not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1:
            text = text[start : end + 1]
    return text


# ── provider backends: each returns the raw model text ───────────────────────
def _groq(system_prompt: str, user_content: str, model: str, temperature: float,
          max_tokens: int, timeout: float) -> str:
    from groq import Groq

    settings.require("groq_api_key")
    client = Groq(api_key=settings.groq_api_key, timeout=timeout)
    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    )
    return resp.choices[0].message.content


def _anthropic(system_prompt: str, user_content: str, model: str, temperature: float,
               max_tokens: int, timeout: float) -> str:
    import anthropic

    settings.require("anthropic_api_key")
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=timeout)
    resp = client.messages.create(
        model=model, max_tokens=max_tokens, temperature=temperature,
        system=system_prompt, messages=[{"role": "user", "content": user_content}],
    )
    return resp.content[0].text


def _gemini(system_prompt: str, user_content: str, model: str, temperature: float,
            max_tokens: int, timeout: float) -> str:
    from google import genai  # pip install google-genai
    from google.genai import types

    settings.require("gemini_api_key")
    client = genai.Client(api_key=settings.gemini_api_key)
    resp = client.models.generate_content(
        model=model,
        contents=user_content,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            max_output_tokens=max_tokens,
            response_mime_type="application/json",
        ),
    )
    return resp.text


_PROVIDERS = {"groq": _groq, "anthropic": _anthropic, "gemini": _gemini}


def _call_raw(system_prompt, user_content, model, temperature, max_tokens, retries, timeout) -> str:
    backend = _PROVIDERS.get(settings.llm_provider)
    if backend is None:
        raise ValueError(f"Unknown LLM_PROVIDER '{settings.llm_provider}' — use groq|anthropic|gemini.")
    model = model or settings.model_reason
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return backend(system_prompt, user_content, model, temperature, max_tokens, timeout)
        except Exception as e:  # noqa: BLE001 — log + retry, never crash the listener
            last_err = e
            log.warning("llm.retry", attempt=attempt, provider=settings.llm_provider,
                        model=model, error=str(e)[:200])
            time.sleep(0.5 * (attempt + 1))
    assert last_err is not None
    raise last_err


def complete_json(system_prompt: str, user_content: str, *, model: str | None = None,
                  temperature: float = 0.2, max_tokens: int = 1024, retries: int = 2,
                  timeout: float = 15.0) -> dict:
    """Call the configured provider and parse strict JSON. Bounded timeout + retries."""
    raw = _call_raw(system_prompt, user_content, model, temperature, max_tokens, retries, timeout)
    return json.loads(_extract_json(raw))


def complete_text(system_prompt: str, user_content: str, *, model: str | None = None,
                  temperature: float = 0.3, max_tokens: int = 1024, retries: int = 2,
                  timeout: float = 20.0) -> str:
    """Plain-text (non-JSON) completion, e.g. the Archivist's prose answer."""
    return _call_raw(system_prompt, user_content, model, temperature, max_tokens, retries, timeout)


def stream_text(system_prompt: str, user_content: str, *, model: str | None = None,
                temperature: float = 0.3, max_tokens: int = 1024, timeout: float = 30.0):
    """Yield answer text chunks. Groq streams natively; other providers yield once."""
    model = model or settings.model_reason
    if settings.llm_provider == "groq":
        from groq import Groq

        settings.require("groq_api_key")
        client = Groq(api_key=settings.groq_api_key, timeout=timeout)
        stream = client.chat.completions.create(
            model=model, temperature=temperature, max_tokens=max_tokens, stream=True,
            messages=[{"role": "system", "content": system_prompt},
                      {"role": "user", "content": user_content}],
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
    else:
        yield complete_text(system_prompt, user_content, model=model, temperature=temperature,
                            max_tokens=max_tokens, timeout=timeout)
