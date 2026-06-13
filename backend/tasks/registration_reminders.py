"""Remind students when a registration window opens or deadlines approach."""
import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select

from core.celery_app import celery_app
from core.database import AsyncSessionLocal
from models.academic import RegistrationPeriod
from models.student import Student
from services.notification_service import notify


async def _run():
    now = datetime.utcnow()
    soon = now + timedelta(days=3)
    sent = 0

    async with AsyncSessionLocal() as db:
        periods = (
            await db.execute(select(RegistrationPeriod).where(RegistrationPeriod.is_active == True))  # noqa: E712
        ).scalars().all()

        relevant = []
        for p in periods:
            if now < p.start_date <= soon:
                relevant.append(("opening", p))
            elif p.drop_deadline and now < p.drop_deadline <= soon:
                relevant.append(("drop", p))
            elif now < p.end_date <= soon:
                relevant.append(("closing", p))

        if not relevant:
            return 0

        students = (await db.execute(select(Student))).scalars().all()
        for kind, period in relevant:
            for s in students:
                if kind == "opening":
                    title = "Registration opens soon"
                    message = f"Registration for {period.semester_code} opens on {period.start_date.date()}."
                elif kind == "drop":
                    title = "Drop deadline approaching"
                    message = f"Drop deadline for {period.semester_code} is {period.drop_deadline.date()}."
                else:
                    title = "Registration closing"
                    message = f"Registration for {period.semester_code} closes on {period.end_date.date()}."

                await notify(
                    student_id=s.id,
                    title=title,
                    message=message,
                    db=db,
                    type="info",
                    link="/schedule-generator",
                )
                sent += 1
    return sent


@celery_app.task(name="tasks.registration_reminders.send_registration_reminders")
def send_registration_reminders():
    return asyncio.run(_run())
