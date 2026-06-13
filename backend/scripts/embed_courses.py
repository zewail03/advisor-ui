"""Embed every course's catalog text into course_embeddings.

Run once after seeding: `python -m scripts.embed_courses`
"""
import asyncio
import json

from sqlalchemy import delete, select

from ai.embeddings import embed_batch
from core.config import settings
from core.database import AsyncSessionLocal
from models.course import Course, CourseEmbedding

_IS_PG = settings.database_url.startswith("postgresql")


def _course_text(c: Course) -> str:
    parts = [f"{c.code} — {c.name}"]
    if c.description:
        parts.append(c.description)
    if c.major_code:
        parts.append(f"Major: {c.major_code}")
    parts.append(f"Credit hours: {c.credits}")
    return "\n".join(parts)


async def main():
    async with AsyncSessionLocal() as db:
        await db.execute(
            delete(CourseEmbedding).where(CourseEmbedding.source == "course_catalog")
        )
        result = await db.execute(select(Course))
        courses = result.scalars().all()
        texts = [_course_text(c) for c in courses]
        if not texts:
            print("No courses found.")
            return
        print(f"Embedding {len(courses)} courses...", flush=True)
        vectors = embed_batch(texts)
        for c, text, vec in zip(courses, texts, vectors):
            db.add(
                CourseEmbedding(
                    course_code=c.code,
                    chunk_text=text,
                    embedding=vec if _IS_PG else json.dumps(vec),
                    source="course_catalog",
                    document_name=f"{c.code}.catalog",
                )
            )
        await db.commit()
        print(f"Embedded {len(courses)} courses.", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
