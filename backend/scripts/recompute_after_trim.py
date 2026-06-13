"""Recompute CGPA + academic standing for every remaining student after the
2026-06-13 dataset trim (35 courses removed, AIE program dropped). Uses the
production replay engine so standing stays provably rule-consistent.
Run from backend/:  .\\venv\\Scripts\\python.exe -m scripts.recompute_after_trim
"""
import asyncio

from sqlalchemy import select

from core.database import AsyncSessionLocal
from models.student import Student
from services.standing import replay_student_standing


async def main() -> None:
    async with AsyncSessionLocal() as db:
        ids = (await db.execute(select(Student.student_id).order_by(Student.student_id))).scalars().all()
        recomputed = skipped = 0
        for sid in ids:
            res = await replay_student_standing(sid, db)
            if res is None:
                skipped += 1
            else:
                recomputed += 1
        await db.commit()
        print(f"students={len(ids)} recomputed={recomputed} skipped_no_grades={skipped}")


if __name__ == "__main__":
    asyncio.run(main())
