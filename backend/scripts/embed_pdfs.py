"""Chunk + embed university policy PDFs into course_embeddings.

Usage:
    python -m scripts.embed_pdfs ./docs/policies/*.pdf
"""
import asyncio
import sys
from pathlib import Path
from uuid import uuid4

from pypdf import PdfReader
from sqlalchemy import delete

from ai.embeddings import embed_batch
from core.database import AsyncSessionLocal
from models.course import CourseEmbedding

CHUNK_CHARS = 1200
OVERLAP = 150


def _chunk(text: str):
    text = " ".join(text.split())
    i = 0
    while i < len(text):
        yield text[i : i + CHUNK_CHARS]
        i += CHUNK_CHARS - OVERLAP


async def ingest(paths: list[Path]):
    async with AsyncSessionLocal() as db:
        doc_names = [p.name for p in paths]
        if doc_names:
            await db.execute(
                delete(CourseEmbedding).where(CourseEmbedding.document_name.in_(doc_names))
            )
            await db.commit()

        total = 0
        for path in paths:
            reader = PdfReader(str(path))
            records: list[tuple[str, int]] = []
            for page_num, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                for ch in _chunk(text):
                    if ch.strip():
                        records.append((ch, page_num))
            if not records:
                continue
            vectors = embed_batch([r[0] for r in records])
            for (chunk_text, page_num), vec in zip(records, vectors):
                db.add(
                    CourseEmbedding(
                        id=str(uuid4()),
                        course_id=None,
                        chunk_text=chunk_text,
                        embedding=vec,
                        source="policy_pdf",
                        page_number=page_num,
                        document_name=path.name,
                    )
                )
            await db.commit()
            total += len(records)
            print(f"  {path.name}: {len(records)} chunks")
        print(f"Done. {total} total chunks embedded.")


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m scripts.embed_pdfs <pdf> [<pdf> ...]")
        sys.exit(1)
    paths = [Path(p) for p in sys.argv[1:]]
    for p in paths:
        if not p.exists():
            print(f"Missing: {p}")
            sys.exit(1)
    asyncio.run(ingest(paths))


if __name__ == "__main__":
    main()
