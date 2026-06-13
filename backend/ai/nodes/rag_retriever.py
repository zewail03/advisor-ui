"""RAG retriever.

Postgres+pgvector path uses `embedding.cosine_distance`. SQLite dev stores the
embedding column as TEXT (JSON-encoded list), so we fall back to an in-Python
cosine-similarity scan. Any retrieval failure degrades to an empty doc list
rather than 500-ing the chat stream.
"""
import json
import math
from typing import Any, List

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from ai.state import ChatState
from core.database import AsyncSessionLocal
from models.course import CourseEmbedding


def _parse_vec(raw: Any) -> List[float] | None:
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)):
        return [float(x) for x in raw]
    if isinstance(raw, str):
        try:
            val = json.loads(raw)
            if isinstance(val, list):
                return [float(x) for x in val]
        except (ValueError, TypeError):
            return None
    return None


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return -1.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return -1.0
    return dot / (na * nb)


async def _row_payload(rows):
    return [
        {
            "source": r.source,
            "document": r.document_name,
            "page": r.page_number,
            "course_code": r.course_code,
            "content": r.chunk_text,
        }
        for r in rows
    ]


async def retrieve_docs(state: ChatState, k: int = 5) -> ChatState:
    try:
        from ai.embeddings import embed_text

        query_vec = embed_text(state["message"])
    except Exception:
        return {**state, "rag_docs": []}

    async with AsyncSessionLocal() as db:
        try:
            stmt = (
                select(CourseEmbedding)
                .order_by(CourseEmbedding.embedding.cosine_distance(query_vec))
                .limit(k)
            )
            result = await db.execute(stmt)
            rows = result.scalars().all()
            docs = await _row_payload(rows)
            return {**state, "rag_docs": docs}
        except (AttributeError, SQLAlchemyError):
            pass

        try:
            result = await db.execute(select(CourseEmbedding))
            rows = result.scalars().all()
        except SQLAlchemyError:
            return {**state, "rag_docs": []}

    scored: list[tuple[float, CourseEmbedding]] = []
    for r in rows:
        vec = _parse_vec(r.embedding)
        if vec is None:
            continue
        scored.append((_cosine(query_vec, vec), r))

    scored.sort(key=lambda t: t[0], reverse=True)
    top = [r for _, r in scored[:k]]
    return {**state, "rag_docs": await _row_payload(top)}
