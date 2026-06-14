"""Seed the physical rooms / halls used for scheduling (idempotent).

Run from backend/:  python -m scripts.seed_rooms
Creates the `rooms` table if it doesn't exist yet, then upserts the halls.
"""
import asyncio

from sqlalchemy import select

from core.database import AsyncSessionLocal, Base, engine
from models.room import Room

# Lab halls (used for Lab meetings) and lecture / section halls.
LAB_HALLS = ["201 Lab", "202 Lab", "211 Lab", "212 Lab", "214 Lab", "216 Lab", "222 Sec", "246 Lab", "248 Lab"]
LECTURE_HALLS = ["131 Sec", "132 Sec", "144 Sec", "145 Sec", "301 Sec", "302 Sec"]


async def seed() -> None:
    # make sure the table exists even if the backend hasn't restarted yet
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        created = 0
        for name in LAB_HALLS + LECTURE_HALLS:
            rtype = "lab" if name in LAB_HALLS else "lecture"
            existing = (await db.execute(select(Room).where(Room.name == name))).scalar_one_or_none()
            if existing:
                existing.room_type = rtype
                existing.is_active = True
                continue
            db.add(Room(name=name, room_type=rtype, is_active=True))
            created += 1
        await db.commit()
        print(f"Seeded {created} new room(s). Total: {len(LAB_HALLS)} lab + {len(LECTURE_HALLS)} lecture halls.")


if __name__ == "__main__":
    asyncio.run(seed())
