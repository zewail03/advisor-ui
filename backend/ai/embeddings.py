from functools import lru_cache
from typing import List

from core.config import settings


@lru_cache(maxsize=1)
def _model():
    # Lazy import so the backend can boot without sentence-transformers
    # installed (demo build ships without pgvector-backed RAG).
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer("all-MiniLM-L6-v2")


def embed_text(text: str) -> List[float]:
    vec = _model().encode(text, normalize_embeddings=True)
    out = vec.tolist()
    if len(out) != settings.embedding_dim:
        raise RuntimeError(
            f"Embedding dim mismatch: got {len(out)}, expected {settings.embedding_dim}"
        )
    return out


def embed_batch(texts: List[str]) -> List[List[float]]:
    vecs = _model().encode(texts, normalize_embeddings=True, batch_size=32)
    return [v.tolist() for v in vecs]
