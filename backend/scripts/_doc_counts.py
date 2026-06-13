import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402
from core.database import AsyncSessionLocal  # noqa: E402

QUERIES = [
    ("tables", "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'"),
    ("students", "SELECT count(*) FROM students"),
    ("courses", "SELECT count(*) FROM courses"),
    ("sections", "SELECT count(*) FROM sections"),
    ("enrollments", "SELECT count(*) FROM enrollments"),
    ("grades", "SELECT count(*) FROM grades"),
    ("policies", "SELECT count(*) FROM policies"),
    ("semesters", "SELECT count(*) FROM semesters"),
    ("majors", "SELECT count(*) FROM majors"),
    ("programs", "SELECT count(*) FROM programs"),
    ("prerequisites", "SELECT count(*) FROM prerequisites"),
    ("requirement_group_courses", "SELECT count(*) FROM requirement_group_courses"),
    ("doc_chunks (RAG)", "SELECT count(*) FROM document_chunks"),
    ("admins", "SELECT count(*) FROM admins"),
]


async def main():
    async with AsyncSessionLocal() as db:
        for label, sql in QUERIES:
            try:
                print(f"{label}: {(await db.execute(text(sql))).scalar()}")
            except Exception as e:
                print(f"{label}: ? ({type(e).__name__})")
                await db.rollback()

asyncio.run(main())
