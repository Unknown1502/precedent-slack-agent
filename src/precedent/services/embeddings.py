"""Embedding adapter — swap providers via EMBED_MODEL. Default: voyage-3 (1024-dim).

The rest of the codebase only calls embed()/embed_batch(); provider details stay here.
"""
from __future__ import annotations

from precedent.config import settings
from precedent.telemetry import get_logger

log = get_logger("embeddings")


def embed(text: str) -> list[float]:
    return embed_batch([text])[0]


def embed_batch(texts: list[str]) -> list[list[float]]:
    model = settings.embed_model
    if model.startswith("voyage"):
        vecs = _voyage(texts)
    elif model.startswith("text-embedding"):
        vecs = _openai(texts)
    else:
        raise ValueError(f"Unknown EMBED_MODEL '{model}' — use a voyage-* or text-embedding-* model.")
    for v in vecs:
        if len(v) != settings.embed_dim:
            raise ValueError(
                f"Embedding dim {len(v)} != EMBED_DIM {settings.embed_dim}. "
                "Fix EMBED_MODEL/EMBED_DIM (and re-migrate if the column dim changed)."
            )
    return vecs


def _voyage(texts: list[str]) -> list[list[float]]:
    import voyageai

    settings.require("voyage_api_key")
    client = voyageai.Client(api_key=settings.voyage_api_key)
    result = client.embed(texts, model=settings.embed_model, input_type="document")
    return [list(v) for v in result.embeddings]


def _openai(texts: list[str]) -> list[list[float]]:
    # Swappable path; requires `pip install openai` + OPENAI_API_KEY, and EMBED_DIM=1536.
    from openai import OpenAI

    settings.require("openai_api_key")
    client = OpenAI(api_key=settings.openai_api_key)
    resp = client.embeddings.create(model=settings.embed_model, input=texts)
    return [list(d.embedding) for d in resp.data]
