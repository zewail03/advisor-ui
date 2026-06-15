"""Text embeddings for pgvector RAG.

Two interchangeable backends (same model -> same 384-dim space, so vectors are
compatible across both):
  * "local" — sentence-transformers (PyTorch). Default for local dev.
  * "hf"    — HuggingFace Inference API. No torch, so the deployed backend fits
              free tiers (~512MB). Set EMBEDDING_BACKEND=hf + HF_API_TOKEN.

Callers (rag_retriever) already treat any embedding failure as "no RAG docs",
so an HF outage degrades gracefully — the chatbot still answers, just without
cited policy snippets.
"""
import math
from functools import lru_cache
from typing import List

from core.config import settings

_HF_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
_HF_URL = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{_HF_MODEL}"


@lru_cache(maxsize=1)
def _model():
    # Lazy import so the backend boots without sentence-transformers/torch
    # installed (the lightweight deploy ships without them).
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer("all-MiniLM-L6-v2")


def _normalize(v: List[float]) -> List[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def _hf_embed(texts: List[str]) -> List[List[float]]:
    import httpx

    if not settings.hf_api_token:
        raise RuntimeError("EMBEDDING_BACKEND=hf but HF_API_TOKEN is not set")
    resp = httpx.post(
        _HF_URL,
        headers={"Authorization": f"Bearer {settings.hf_api_token}"},
        json={"inputs": texts, "options": {"wait_for_model": True}},
        timeout=30.0,
    )
    resp.raise_for_status()
    data = resp.json()  # list[list[float]] for a list of inputs
    return [_normalize([float(x) for x in vec]) for vec in data]


def embed_batch(texts: List[str]) -> List[List[float]]:
    if settings.embedding_backend == "hf":
        return _hf_embed(texts)
    vecs = _model().encode(texts, normalize_embeddings=True, batch_size=32)
    return [v.tolist() for v in vecs]


def embed_text(text: str) -> List[float]:
    if settings.embedding_backend == "hf":
        out = _hf_embed([text])[0]
    else:
        out = _model().encode(text, normalize_embeddings=True).tolist()
    if len(out) != settings.embedding_dim:
        raise RuntimeError(
            f"Embedding dim mismatch: got {len(out)}, expected {settings.embedding_dim}"
        )
    return out
