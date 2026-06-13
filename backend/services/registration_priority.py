"""Registration priority tiers — who gets the seat (and waitlist order).

When seats are scarce the queue is NOT first-come-first-served:
  Tier 1  on-plan:      the course is due NOW in the student's study plan and
                        they have never failed it (normal timeline always wins)
  Tier 2  retake, near graduation: failed it before AND close to finishing —
                        the F is blocking their degree
  Tier 3  retake:       failed it before (earlier in the program)
  Tier 4  racer:        taking it AHEAD of the study plan to graduate early —
                        welcome, but only after everyone the plan entitles

Everything is computed live from the plan tables + the student's transcript.
"""
from typing import Dict, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.academic import RequirementGroupCourse, Semester
from models.course import Course, Section
from models.enrollment import Enrollment, Grade
from models.student import Program, Student

NEAR_GRADUATION_PCT = 70  # completed % above which a retake is "blocking the degree"


async def _plan_year_for(course_code: str, major_id: Optional[int], db: AsyncSession) -> Optional[int]:
    conds = [RequirementGroupCourse.course_code == course_code]
    if major_id:
        conds.append(RequirementGroupCourse.major_id == major_id)
    row = await db.execute(
        select(func.min(RequirementGroupCourse.required_year)).where(*conds)
    )
    val = row.scalar()
    return int(val) if val is not None else None


async def current_plan_year(student_id: int, db: AsyncSession) -> int:
    """Year the student is in = completed main semesters // 2 + 1."""
    row = await db.execute(
        select(func.count(func.distinct(Semester.semester_id)))
        .select_from(Grade)
        .join(Enrollment, Enrollment.enrollment_id == Grade.enrollment_id)
        .join(Section, Section.section_id == Enrollment.section_id)
        .join(Semester, Semester.semester_id == Section.semester_id)
        .where(Enrollment.student_id == student_id, ~Semester.code.like("Summer%"))
    )
    mains = int(row.scalar() or 0)
    return mains // 2 + 1


async def _has_failed(student_id: int, course_code: str, db: AsyncSession) -> bool:
    row = await db.execute(
        select(func.count(Grade.grade_id))
        .select_from(Grade)
        .join(Enrollment, Enrollment.enrollment_id == Grade.enrollment_id)
        .join(Section, Section.section_id == Enrollment.section_id)
        .where(
            Enrollment.student_id == student_id,
            Section.course_code == course_code,
            Grade.grade_letter.in_(("F", "FW")),
        )
    )
    return int(row.scalar() or 0) > 0


async def _completion_pct(student: Student, db: AsyncSession) -> float:
    program = await db.get(Program, student.program_id)
    total = program.total_credits if program and program.total_credits else 1
    row = await db.execute(
        select(func.coalesce(func.sum(Course.credits), 0))
        .select_from(Grade)
        .join(Enrollment, Enrollment.enrollment_id == Grade.enrollment_id)
        .join(Section, Section.section_id == Enrollment.section_id)
        .join(Course, Course.code == Section.course_code)
        .where(
            Enrollment.student_id == student.student_id,
            Grade.counts_in_gpa == True,  # noqa: E712
            Grade.grade_points >= 1.0,
        )
    )
    earned = int(row.scalar() or 0)
    return round(100.0 * earned / total, 1)


async def registration_tier(
    student: Student, course_code: str, db: AsyncSession
) -> Tuple[int, str]:
    """(tier 1-4, human reason). Lower tier registers first."""
    failed = await _has_failed(student.student_id, course_code, db)
    plan_year = await _plan_year_for(course_code, student.major_id, db)
    current_year = await current_plan_year(student.student_id, db)

    if failed:
        pct = await _completion_pct(student, db)
        if pct >= NEAR_GRADUATION_PCT:
            return 2, (f"retaking a failed course at {pct:.0f}% completion — "
                       "it blocks graduation")
        return 3, "retaking a previously failed course"

    if plan_year is not None and plan_year > current_year:
        return 4, (f"taking a year-{plan_year} course in year {current_year} "
                   "(ahead of plan / fast-track)")

    return 1, (f"on the normal study plan (year-{plan_year or current_year} "
               f"course, year-{current_year} student, never failed)")


async def section_priority_payload(
    student: Student, course_code: str, db: AsyncSession
) -> Dict:
    tier, reason = await registration_tier(student, course_code, db)
    return {"tier": tier, "reason": reason}


async def batch_registration_tiers(
    student: Student, course_codes: list, db: AsyncSession
) -> Dict[str, Tuple[int, str]]:
    """Tier many courses with four queries total (planner-friendly)."""
    codes = [c for c in course_codes if c]
    if not codes:
        return {}

    failed_rows = await db.execute(
        select(Section.course_code)
        .select_from(Grade)
        .join(Enrollment, Enrollment.enrollment_id == Grade.enrollment_id)
        .join(Section, Section.section_id == Enrollment.section_id)
        .where(
            Enrollment.student_id == student.student_id,
            Section.course_code.in_(codes),
            Grade.grade_letter.in_(("F", "FW")),
        )
        .distinct()
    )
    failed = {r[0] for r in failed_rows.all()}

    conds = [RequirementGroupCourse.course_code.in_(codes)]
    if student.major_id:
        conds.append(RequirementGroupCourse.major_id == student.major_id)
    plan_rows = await db.execute(
        select(RequirementGroupCourse.course_code,
               func.min(RequirementGroupCourse.required_year))
        .where(*conds)
        .group_by(RequirementGroupCourse.course_code)
    )
    plan_years = {c: int(y) for c, y in plan_rows.all() if y is not None}

    current_year = await current_plan_year(student.student_id, db)
    pct = await _completion_pct(student, db)

    out: Dict[str, Tuple[int, str]] = {}
    for code in codes:
        if code in failed:
            if pct >= NEAR_GRADUATION_PCT:
                out[code] = (2, f"retake at {pct:.0f}% completion — blocks graduation")
            else:
                out[code] = (3, "retake of a previously failed course")
        elif plan_years.get(code) is not None and plan_years[code] > current_year:
            out[code] = (4, f"year-{plan_years[code]} course taken in year {current_year} (fast-track)")
        else:
            out[code] = (1, "on the normal study plan, never failed")
    return out

