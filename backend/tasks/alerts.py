"""Daily alerts: GPA risk, probation escalation, midterm failures."""
import asyncio

from sqlalchemy import select

from core.celery_app import celery_app
from core.database import AsyncSessionLocal
from models.academic import AcademicStanding, StandingEnum
from models.enrollment import Enrollment, Grade
from models.student import Student
from services.notification_service import notify


async def _run():
    alerted = 0
    async with AsyncSessionLocal() as db:
        standings = (
            await db.execute(select(AcademicStanding))
        ).scalars().all()

        for s in standings:
            if s.standing == StandingEnum.dismissal_risk:
                await notify(
                    student_id=s.student_id,
                    title="Dismissal risk \u2014 act now",
                    message=(
                        f"Your CGPA {s.cgpa:.2f} puts you at dismissal risk after "
                        f"{s.consecutive_probation_semesters} consecutive probation semesters. "
                        "Please book an advisor meeting immediately."
                    ),
                    db=db,
                    type="emergency",
                    link="/analytics",
                )
                alerted += 1
            elif s.standing == StandingEnum.probation:
                await notify(
                    student_id=s.student_id,
                    title="Academic probation",
                    message=(
                        f"CGPA {s.cgpa:.2f} is below 2.00. Review your study plan and "
                        "consider lightening next semester's load."
                    ),
                    db=db,
                    type="warning",
                    link="/study-plan",
                )
                alerted += 1

        # Midterm-failure alerts
        failing = (
            await db.execute(
                select(Enrollment, Grade)
                .join(Grade, Grade.enrollment_id == Enrollment.id)
                .where(Enrollment.status == "Enrolled")
                .where(Grade.midterm_score != None)  # noqa: E711
            )
        ).all()
        for enrollment, grade in failing:
            if grade.midterm_score is not None and grade.midterm_score < 50:
                student = await db.get(Student, enrollment.student_id)
                if student:
                    await notify(
                        student_id=student.id,
                        title="Midterm below passing",
                        message=(
                            f"Your midterm score ({grade.midterm_score:.0f}) in this "
                            "course is below 50. Check drop deadlines."
                        ),
                        db=db,
                        type="warning",
                        link="/manage-classes/my-classes",
                    )
                    alerted += 1
        return alerted


@celery_app.task(name="tasks.alerts.run_daily_alerts")
def run_daily_alerts():
    return asyncio.run(_run())
