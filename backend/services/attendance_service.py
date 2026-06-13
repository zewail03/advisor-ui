"""Attendance service (§7).

Records per-session attendance and keeps a summary with absence %.
Fires warnings at 10 / 15 / 25 % absence and auto-assigns FW at 25 %.
"""
from datetime import date as _date, datetime
from typing import Dict, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.attendance import (
    AttendanceRecord,
    AttendanceStatus,
    AttendanceSummary,
    ContactType,
    FW_THRESHOLD_PCT,
    WARNING_LEVELS,
)
from models.course import Course, Section
from models.enrollment import Enrollment, Grade, GradeEnum
from services.audit_service import log_action
from services.notification_service import notify


async def _get_or_create_summary(
    enrollment_id: str, db: AsyncSession
) -> AttendanceSummary:
    row = (
        await db.execute(
            select(AttendanceSummary).where(
                AttendanceSummary.enrollment_id == enrollment_id
            )
        )
    ).scalar_one_or_none()
    if row:
        return row
    row = AttendanceSummary(enrollment_id=enrollment_id)
    db.add(row)
    await db.flush()
    return row


def _warning_tier(pct: float) -> float:
    tier = 0.0
    for threshold in WARNING_LEVELS:
        if pct >= threshold:
            tier = threshold
    return tier


async def _assign_fw(enrollment: Enrollment, db: AsyncSession) -> None:
    grade = (
        await db.execute(select(Grade).where(Grade.enrollment_id == enrollment.id))
    ).scalar_one_or_none()
    if grade:
        grade.letter_grade = GradeEnum.FW
        grade.grade_points = 0.0
    else:
        db.add(Grade(
            id=str(uuid4()),
            enrollment_id=enrollment.id,
            letter_grade=GradeEnum.FW,
            grade_points=0.0,
        ))
    enrollment.status = "ForceWithdrawn"


async def record_attendance(
    enrollment_id: str,
    session_date: _date,
    status: AttendanceStatus,
    db: AsyncSession,
    contact_type: ContactType = ContactType.lecture,
    duration_hours: float = 1.0,
    recorded_by: Optional[str] = None,
    note: Optional[str] = None,
) -> Dict:
    enrollment = await db.get(Enrollment, enrollment_id)
    if not enrollment:
        return {"success": False, "message": "Enrollment not found"}

    record = AttendanceRecord(
        enrollment_id=enrollment_id,
        session_date=session_date,
        contact_type=contact_type,
        duration_hours=duration_hours,
        status=status,
        recorded_by=recorded_by,
        note=note,
    )
    db.add(record)

    summary = await _get_or_create_summary(enrollment_id, db)
    summary.total_hours += duration_hours
    if status == AttendanceStatus.absent:
        summary.absent_hours += duration_hours
    elif status == AttendanceStatus.excused:
        summary.excused_hours += duration_hours
    # 'late' counts as present for the absence %.
    summary.absence_pct = (
        (summary.absent_hours / summary.total_hours * 100.0)
        if summary.total_hours > 0 else 0.0
    )
    summary.last_updated = datetime.utcnow()

    tier = _warning_tier(summary.absence_pct)
    warning_fired = False
    fw_fired = False

    if tier > summary.last_warning_level:
        summary.last_warning_level = tier
        course_code = ""
        section = await db.get(Section, enrollment.section_id)
        if section:
            course = await db.get(Course, section.course_id)
            if course:
                course_code = course.code

        if tier >= FW_THRESHOLD_PCT and not summary.fw_triggered:
            summary.fw_triggered = True
            await _assign_fw(enrollment, db)
            fw_fired = True
            await log_action(
                db,
                action="attendance.fw_triggered",
                entity_type="enrollment",
                entity_id=enrollment.id,
                actor_id=recorded_by,
                actor_role="system",
                subject_student_id=enrollment.student_id,
                after={
                    "absence_pct": round(summary.absence_pct, 2),
                    "course_code": course_code,
                    "grade": "FW",
                },
            )
            await notify(
                student_id=enrollment.student_id,
                title=f"Force Withdrawal — {course_code}",
                message=(
                    f"Your absence in {course_code} reached "
                    f"{summary.absence_pct:.1f}%. A grade of FW has been recorded."
                ),
                db=db,
                type="emergency",
                link="/manage-classes/my-classes",
            )
        else:
            await notify(
                student_id=enrollment.student_id,
                title=f"Attendance warning ({int(tier)}%) — {course_code}",
                message=(
                    f"Your absence in {course_code} is {summary.absence_pct:.1f}%. "
                    "Reaching 25% triggers an automatic Force Withdrawal."
                ),
                db=db,
                type="warning",
                link="/manage-classes/my-classes",
            )
            warning_fired = True

    await db.commit()
    return {
        "success": True,
        "absence_pct": round(summary.absence_pct, 2),
        "warning_tier": summary.last_warning_level,
        "warning_fired": warning_fired,
        "fw_assigned": fw_fired,
    }


async def get_summary_for_student(
    student_id: str, db: AsyncSession, semester_code: Optional[str] = None
) -> Dict:
    stmt = select(Enrollment).where(Enrollment.student_id == student_id)
    if semester_code:
        stmt = stmt.where(Enrollment.semester_code == semester_code)
    enrollments = (await db.execute(stmt)).scalars().all()

    rows = []
    for e in enrollments:
        summary = (
            await db.execute(
                select(AttendanceSummary).where(
                    AttendanceSummary.enrollment_id == e.id
                )
            )
        ).scalar_one_or_none()
        section = await db.get(Section, e.section_id)
        course = await db.get(Course, section.course_id) if section else None
        rows.append({
            "enrollment_id": e.id,
            "semester_code": e.semester_code,
            "course_code": course.code if course else "",
            "course_title": course.title if course else "",
            "status": e.status,
            "total_hours": summary.total_hours if summary else 0.0,
            "absent_hours": summary.absent_hours if summary else 0.0,
            "absence_pct": round(summary.absence_pct, 2) if summary else 0.0,
            "warning_tier": summary.last_warning_level if summary else 0.0,
            "fw_triggered": summary.fw_triggered if summary else False,
        })
    return {"records": rows}
