"""Weekly attendance audit: re-compute absence % and fire warnings (§7)."""
import asyncio

from sqlalchemy import select

from core.celery_app import celery_app
from core.database import AsyncSessionLocal
from models.attendance import (
    AttendanceSummary,
    FW_THRESHOLD_PCT,
    WARNING_LEVELS,
)
from models.course import Course, Section
from models.enrollment import Enrollment, Grade, GradeEnum
from services.notification_service import notify


def _tier(pct: float) -> float:
    tier = 0.0
    for threshold in WARNING_LEVELS:
        if pct >= threshold:
            tier = threshold
    return tier


async def _run():
    alerted = 0
    async with AsyncSessionLocal() as db:
        summaries = (await db.execute(select(AttendanceSummary))).scalars().all()
        for s in summaries:
            if s.total_hours <= 0:
                continue
            s.absence_pct = s.absent_hours / s.total_hours * 100.0
            tier = _tier(s.absence_pct)
            if tier <= s.last_warning_level:
                continue

            enrollment = await db.get(Enrollment, s.enrollment_id)
            if not enrollment:
                continue
            section = await db.get(Section, enrollment.section_id)
            course = await db.get(Course, section.course_id) if section else None
            code = course.code if course else ""

            s.last_warning_level = tier
            if tier >= FW_THRESHOLD_PCT and not s.fw_triggered:
                s.fw_triggered = True
                grade = (
                    await db.execute(
                        select(Grade).where(Grade.enrollment_id == enrollment.id)
                    )
                ).scalar_one_or_none()
                if grade:
                    grade.letter_grade = GradeEnum.FW
                    grade.grade_points = 0.0
                else:
                    db.add(Grade(
                        enrollment_id=enrollment.id,
                        letter_grade=GradeEnum.FW,
                        grade_points=0.0,
                    ))
                enrollment.status = "ForceWithdrawn"
                await notify(
                    student_id=enrollment.student_id,
                    title=f"Force Withdrawal \u2014 {code}",
                    message=(
                        f"Absence in {code} reached {s.absence_pct:.1f}%. "
                        "An FW grade has been assigned."
                    ),
                    db=db,
                    type="emergency",
                    link="/manage-classes/my-classes",
                )
            else:
                await notify(
                    student_id=enrollment.student_id,
                    title=f"Attendance warning ({int(tier)}%) \u2014 {code}",
                    message=(
                        f"Absence in {code} is {s.absence_pct:.1f}%. "
                        "Reaching 25% triggers a Force Withdrawal."
                    ),
                    db=db,
                    type="warning",
                    link="/manage-classes/my-classes",
                )
            alerted += 1

        await db.commit()
        return alerted


@celery_app.task(name="tasks.attendance_monitor.audit_attendance")
def audit_attendance():
    return asyncio.run(_run())
