"""Backfill week_2_end / week_4_end / week_13_end on existing Semester rows.

Safe to re-run. Only fills columns that are NULL. Uses start_date as the anchor.

Run from backend/:  python -m scripts.backfill_semester_weeks
"""
import asyncio
import os
import sys
from datetime import timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sqlalchemy import select

from core.database import AsyncSessionLocal
from models import Semester


async def backfill():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Semester))
        rows = result.scalars().all()
        updated = 0
        for sem in rows:
            if sem.start_date is None:
                continue
            changed = False
            if sem.week_2_end is None:
                sem.week_2_end = sem.start_date + timedelta(weeks=2)
                changed = True
            if sem.week_4_end is None:
                sem.week_4_end = sem.start_date + timedelta(weeks=4)
                changed = True
            if sem.week_13_end is None:
                sem.week_13_end = sem.start_date + timedelta(weeks=13)
                changed = True
            if changed:
                updated += 1
        if updated:
            await db.commit()
        print(f"Backfilled {updated} Semester row(s).")


if __name__ == "__main__":
    asyncio.run(backfill())
