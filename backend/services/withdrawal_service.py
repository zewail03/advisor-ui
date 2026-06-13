"""Week-phased Add/Drop/Withdrawal service (§6).

Weeks 1-2   : Drop allowed, 100% refund, no grade assigned.
Weeks 3-4   : Withdraw with 'W' grade, 50% refund.
Weeks 5-13  : Withdraw with 'W' grade, 0% refund.
Weeks >13   : Not allowed.

Rewritten for the real AIU schema:
  * Semester has `start_date` and `weeks`, not per-phase end_date columns —
    we derive the phase boundaries by offsetting from `start_date`.
  * Enrollment has no `semester_code` column; we go Section -> Semester.
  * Grade uses `grade_letter` (string), not a GradeEnum.
  * Financial transactions and audit logging are intentionally omitted in the
    demo build; the corresponding routers are not mounted.
"""
from datetime import date, datetime, timedelta
from typing import Dict, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.academic import Semester
from models.course import Section
from models.enrollment import Enrollment, Grade


WITHDRAWAL_REVIEW_LIMIT = 3


def _phase(now: date, sem: Semester) -> str:
    """Return 'add_drop' | 'withdraw_half' | 'withdraw_none' | 'blocked'."""
    if not sem.start_date:
        return "add_drop"
    weeks = sem.weeks or 15
    week2_end = sem.start_date + timedelta(weeks=2)
    week4_end = sem.start_date + timedelta(weeks=4)
    week13_end = sem.start_date + timedelta(weeks=min(13, weeks))
    if now <= week2_end:
        return "add_drop"
    if now <= week4_end:
        return "withdraw_half"
    if now <= week13_end:
        return "withdraw_none"
    return "blocked"


async def _section_semester(section_id: int, db: AsyncSession) -> Optional[Semester]:
    section = await db.get(Section, section_id)
    if not section:
        return None
    return await db.get(Semester, section.semester_id)


async def _count_withdrawals(
    student_id: int, semester_id: int, db: AsyncSession
) -> int:
    row = await db.execute(
        select(func.count(Enrollment.enrollment_id))
        .join(Section, Section.section_id == Enrollment.section_id)
        .where(
            and_(
                Enrollment.student_id == student_id,
                Enrollment.status == "Withdrawn",
                Section.semester_id == semester_id,
            )
        )
    )
    return int(row.scalar() or 0)


async def process_drop_or_withdraw(
    student_id: int,
    enrollment_id: int,
    db: AsyncSession,
) -> Dict:
    enrollment = await db.get(Enrollment, int(enrollment_id))
    if not enrollment or enrollment.student_id != student_id:
        return {"success": False, "message": "Enrollment not found"}
    if enrollment.status != "Enrolled":
        return {"success": False, "message": f"Enrollment is {enrollment.status}"}

    sem = await _section_semester(enrollment.section_id, db)
    if not sem:
        return {"success": False, "message": "Semester not configured for add/drop"}

    now = datetime.utcnow().date()
    phase = _phase(now, sem)
    if phase == "blocked":
        return {
            "success": False,
            "message": "Drop/withdrawal window is closed (after week 13)",
        }

    if phase == "add_drop":
        enrollment.status = "Dropped"
        enrollment.drop_date = datetime.utcnow()
        outcome = {
            "success": True,
            "message": "Dropped with full refund",
            "action": "drop",
            "refund_percent": 100,
            "grade_assigned": None,
        }
    else:
        enrollment.status = "Withdrawn"
        enrollment.withdrawal_date = datetime.utcnow()

        existing_grade = (
            await db.execute(
                select(Grade).where(Grade.enrollment_id == enrollment.enrollment_id)
            )
        ).scalar_one_or_none()
        if existing_grade:
            existing_grade.grade_letter = "W"
            existing_grade.grade_points = None
            existing_grade.counts_in_gpa = False
        else:
            db.add(
                Grade(
                    enrollment_id=enrollment.enrollment_id,
                    grade_letter="W",
                    grade_points=None,
                    counts_in_gpa=False,
                    grade_date=datetime.utcnow(),
                )
            )

        refund_pct = 50 if phase == "withdraw_half" else 0
        outcome = {
            "success": True,
            "message": f"Withdrawn with 'W' grade ({refund_pct}% refund)",
            "action": "withdrawal",
            "refund_percent": refund_pct,
            "grade_assigned": "W",
        }

    await db.commit()

    if outcome["action"] == "withdrawal":
        count = await _count_withdrawals(student_id, sem.semester_id, db)
        if count >= WITHDRAWAL_REVIEW_LIMIT:
            outcome["advisor_review_required"] = True
            outcome["advisor_review_reason"] = (
                f"{count} withdrawals recorded in {sem.code} — policy requires advisor review."
            )

    outcome["enrollment_id"] = enrollment_id
    outcome["phase"] = phase
    return outcome
