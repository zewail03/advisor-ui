"""Promote waitlisted students when a seat opens up."""
import asyncio
from uuid import uuid4

from sqlalchemy import select

from core.celery_app import celery_app
from core.database import AsyncSessionLocal
from models.course import Course, Section
from models.enrollment import Enrollment, Waitlist
from services.notification_service import notify


async def _promote():
    async with AsyncSessionLocal() as db:
        sections = (await db.execute(select(Section))).scalars().all()
        promoted = 0
        for section in sections:
            if section.enrolled_count >= section.capacity:
                continue

            waitlist_rows = (
                await db.execute(
                    select(Waitlist)
                    .where(Waitlist.section_id == section.id)
                    .order_by(Waitlist.position.asc())
                )
            ).scalars().all()

            while section.enrolled_count < section.capacity and waitlist_rows:
                entry = waitlist_rows.pop(0)

                dup = (await db.execute(
                    select(Enrollment).where(
                        Enrollment.student_id == entry.student_id,
                        Enrollment.section_id == section.id,
                        Enrollment.status == "Enrolled",
                    )
                )).scalar_one_or_none()
                if dup:
                    await db.delete(entry)
                    continue

                course = await db.get(Course, section.course_id)
                enrollment = Enrollment(
                    id=str(uuid4()),
                    student_id=entry.student_id,
                    section_id=section.id,
                    semester_code=section.semester_code,
                    status="Enrolled",
                )
                db.add(enrollment)
                section.enrolled_count += 1
                section.waitlist_count = max(0, (section.waitlist_count or 0) - 1)
                await db.delete(entry)

                await notify(
                    student_id=entry.student_id,
                    title="Seat available!",
                    message=f"You were promoted off the waitlist into {course.code if course else section.id}.",
                    db=db,
                    type="success",
                    link="/manage-classes/my-classes",
                )
                promoted += 1

            for i, remaining in enumerate(waitlist_rows, start=1):
                remaining.position = i

        await db.commit()
        return promoted


@celery_app.task(name="tasks.waitlist_monitor.check_waitlist")
def check_waitlist():
    return asyncio.run(_promote())
