"""Retake validation + bookkeeping (§10)."""
from typing import Dict, Optional, Tuple

from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.academic import Semester
from models.course import Course, Section
from models.enrollment import Enrollment, Grade, GRADE_POINTS
from models.retake import IMPROVEMENT_PRIOR_MIN_POINTS, RetakeRecord
from models.student import Program, Student
from services.policy import get_policy


async def _semester_code(semester_id: int, db: AsyncSession) -> str:
    code = (
        await db.execute(select(Semester.code).where(Semester.semester_id == semester_id))
    ).scalar_one_or_none()
    return code or ""


async def _prior_best(student_id: int, course_code: str, db: AsyncSession):
    rows = (
        await db.execute(
            select(Grade, Enrollment)
            .join(Enrollment, Grade.enrollment_id == Enrollment.enrollment_id)
            .join(Section, Enrollment.section_id == Section.section_id)
            .where(
                and_(
                    Enrollment.student_id == student_id,
                    Section.course_code == course_code,
                    Grade.grade_letter != None,  # noqa: E711
                )
            )
        )
    ).all()
    best = None
    for grade, enrollment in rows:
        pts = grade.grade_points
        if pts is None:
            pts = GRADE_POINTS.get(grade.grade_letter)
        if pts is None:
            continue
        if best is None or pts > best[0]:
            best = (pts, grade, enrollment)
    return best


async def _improvement_ch_used(student_id: int, db: AsyncSession) -> int:
    """Lifetime improvement-retake credit hours (the §10.2 cap is per program
    duration, not per term type)."""
    total = (
        await db.execute(
            select(func.coalesce(func.sum(RetakeRecord.credit_hours), 0))
            .where(RetakeRecord.student_id == student_id)
            .where(RetakeRecord.is_improvement == True)  # noqa: E712
        )
    ).scalar_one()
    return int(total)


async def _improvement_cap(student_id: int, db: AsyncSession) -> int:
    """§10.2: 9 CH lifetime for 4-year programs, 12 CH for 5-year programs."""
    student = await db.get(Student, student_id)
    program = (
        await db.get(Program, student.program_id)
        if student and student.program_id
        else None
    )
    five_year = bool(program and (program.duration_years or 4) >= 5)
    key = "retake.improvement_cap_5yr" if five_year else "retake.improvement_cap_4yr"
    return int(await get_policy(key, db))


async def _all_attempt_points(
    student_id: int, course_code: str, db: AsyncSession
) -> list:
    """Grade points of every graded attempt of the course (for §10.3 averaging)."""
    rows = (
        await db.execute(
            select(Grade.grade_points, Grade.grade_letter)
            .join(Enrollment, Grade.enrollment_id == Enrollment.enrollment_id)
            .join(Section, Enrollment.section_id == Section.section_id)
            .where(
                and_(
                    Enrollment.student_id == student_id,
                    Section.course_code == course_code,
                    Grade.grade_letter != None,  # noqa: E711
                )
            )
        )
    ).all()
    pts = []
    for p, letter in rows:
        if p is None:
            p = GRADE_POINTS.get(letter)
        if p is not None:
            pts.append(float(p))
    return pts


async def _course_for(section: Section, db: AsyncSession) -> Optional[Course]:
    return (
        await db.execute(select(Course).where(Course.code == section.course_code))
    ).scalar_one_or_none()


async def check_retake_eligibility(
    student_id: int, section_id: int, db: AsyncSession
) -> Tuple[bool, str, Dict]:
    """Return (ok, message, context) — caller uses context for booking."""
    section = await db.get(Section, section_id)
    if not section:
        return False, "Section not found", {}
    course = await _course_for(section, db)
    prior = await _prior_best(student_id, section.course_code, db)
    if prior is None:
        return False, "No prior attempt — this is not a retake", {}

    prior_points, prior_grade, _ = prior
    is_fail = prior_points < 1.0
    is_improvement = prior_points >= IMPROVEMENT_PRIOR_MIN_POINTS
    summer = "Summer" in await _semester_code(section.semester_id, db)

    ctx = {
        "course_code": section.course_code,
        "credit_hours": course.credits if course else 0,
        "prior_points": prior_points,
        "is_fail_retake": is_fail,
        "is_improvement": is_improvement,
        "summer": summer,
    }

    if is_improvement:
        used = await _improvement_ch_used(student_id, db)
        cap = await _improvement_cap(student_id, db)
        credits = course.credits if course else 0
        over_limit = used + credits > cap
        ctx.update({
            "improvement_ch_used": used,
            "improvement_ch_cap": cap,
            "over_improvement_limit": over_limit,
        })
        if over_limit:
            # §10.3: exceeding the cap doesn't block the retake — all attempts
            # are AVERAGED in the CGPA instead of taking the higher grade.
            return (
                True,
                f"Improvement limit exceeded ({used} of {cap} CH used) — "
                "all attempts of this course will be averaged in your CGPA",
                ctx,
            )

    return True, "OK", ctx


async def record_retake_result(
    student_id: int,
    retake_enrollment_id: int,
    db: AsyncSession,
) -> Dict:
    """After a grade is posted for a retake enrollment, cap it per §10 and
    persist a RetakeRecord. Returns the effective (CGPA-used) points."""
    enrollment = await db.get(Enrollment, retake_enrollment_id)
    if not enrollment or enrollment.student_id != student_id:
        return {"success": False, "message": "Enrollment not found"}
    section = await db.get(Section, enrollment.section_id)
    if not section:
        return {"success": False, "message": "Section not found"}
    course = await _course_for(section, db)

    grade = (
        await db.execute(select(Grade).where(Grade.enrollment_id == retake_enrollment_id))
    ).scalar_one_or_none()
    if not grade or grade.grade_points is None:
        return {"success": False, "message": "Grade not yet available"}

    prior = await _prior_best(student_id, section.course_code, db)
    if prior is None:
        return {"success": False, "message": "No prior attempt — not a retake"}

    prior_points, prior_grade, _orig = prior
    is_fail = prior_points < 1.0
    is_improvement = prior_points >= IMPROVEMENT_PRIOR_MIN_POINTS
    summer = "Summer" in await _semester_code(section.semester_id, db)

    cap_after_fail = float(await get_policy("retake.cap_after_fail", db))
    new_pts = grade.grade_points
    capped = new_pts
    if is_fail and new_pts > cap_after_fail:
        capped = cap_after_fail
        grade.grade_points = cap_after_fail  # enforce cap on the record itself

    if is_fail:
        # §10.1: the latest grade replaces the F (capped at B+).
        effective = capped
    elif is_improvement:
        used = await _improvement_ch_used(student_id, db)
        cap = await _improvement_cap(student_id, db)
        credits = course.credits if course else 0
        if used + credits > cap:
            # §10.3 over the limit: AVERAGE of all attempts counts in CGPA.
            attempts = await _all_attempt_points(student_id, section.course_code, db)
            effective = round(sum(attempts) / len(attempts), 3) if attempts else capped
        else:
            # §10.3 within the limit: the higher grade counts, lower ignored.
            effective = max(capped, prior_points)
    else:
        effective = max(capped, prior_points)

    db.add(RetakeRecord(
        student_id=student_id,
        course_id=section.course_code,
        retake_enrollment_id=str(retake_enrollment_id),
        original_letter=prior_grade.grade_letter,
        original_points=prior_points,
        credit_hours=course.credits if course else 0,
        is_improvement=is_improvement,
        is_after_fail=is_fail,
        was_summer=summer,
        new_letter=grade.grade_letter,
        new_points=new_pts,
        capped_points=capped,
        effective_points=effective,
    ))
    await db.commit()
    return {
        "success": True,
        "prior_points": prior_points,
        "new_points": new_pts,
        "capped_points": capped,
        "effective_points": effective,
        "is_after_fail": is_fail,
        "is_improvement": is_improvement,
    }
