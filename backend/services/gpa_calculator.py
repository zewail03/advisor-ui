"""Pure-math GPA calculations and what-if simulations.

Keys off `Course.code` (string) since that's the natural key in the real AIU
schema. Uses `academic_standing` as authoritative CGPA source, with raw grade
components for simulation math.
"""
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.academic import AcademicStanding, Semester
from models.course import Course, Section
from models.enrollment import Enrollment, GRADE_POINTS, Grade
from models.student import Student


async def _authoritative_cgpa(student_id: int, db: AsyncSession) -> Optional[float]:
    """Get CGPA from academic_standing (single source of truth)."""
    student = await db.get(Student, student_id)
    if not student:
        return None
    result = await db.execute(
        select(AcademicStanding)
        .where(AcademicStanding.student_code == student.student_code)
        .order_by(AcademicStanding.semester_id.desc())
        .limit(1)
    )
    standing = result.scalar_one_or_none()
    if standing and standing.cgpa is not None:
        return float(standing.cgpa)
    if student.cgpa is not None:
        return float(student.cgpa)
    return None


async def get_cgpa_components(student_id: int, db: AsyncSession) -> Tuple[float, int]:
    """Return (total_points, total_credits) for already-graded courses that
    count in GPA (excludes W/I/S/U and any row with counts_in_gpa=False)."""
    result = await db.execute(
        select(Grade.grade_points, Course.credits, Grade.grade_letter, Grade.counts_in_gpa)
        .select_from(Grade)
        .join(Enrollment, Enrollment.enrollment_id == Grade.enrollment_id)
        .join(Section, Section.section_id == Enrollment.section_id)
        .join(Course, Course.code == Section.course_code)
        .where(Enrollment.student_id == student_id)
    )
    total_points = 0.0
    total_credits = 0
    for pts, credits, letter, counts in result.all():
        if not counts:
            continue
        if pts is None:
            continue
        if letter in ("W", "I", "S", "U"):
            continue
        total_points += float(pts) * int(credits or 0)
        total_credits += int(credits or 0)
    return total_points, total_credits


async def _main_semesters_completed(student_id: int, db: AsyncSession) -> int:
    """Distinct MAIN (non-summer) semesters in which the student has any
    graded course — used for the §12.1 probation tier boundary."""
    row = await db.execute(
        select(func.count(func.distinct(Semester.semester_id)))
        .select_from(Grade)
        .join(Enrollment, Enrollment.enrollment_id == Grade.enrollment_id)
        .join(Section, Section.section_id == Enrollment.section_id)
        .join(Semester, Semester.semester_id == Section.semester_id)
        .where(
            Enrollment.student_id == student_id,
            ~Semester.code.like("Summer%"),
        )
    )
    return int(row.scalar() or 0)


async def recompute_and_store_cgpa(student_id: int, db: AsyncSession) -> float:
    """Recompute CGPA and rebuild the student's full standing history through
    the warning/dismissal state machine (services.standing), so a grade edit
    can never leave standing out of sync with the rules. Does NOT commit."""
    from services.standing import replay_student_standing

    result = await replay_student_standing(student_id, db)
    if result is not None:
        return float(result["cgpa"])
    points, credits = await get_cgpa_components(student_id, db)
    return round(points / credits, 3) if credits else 0.0


async def _load_courses_by_code(
    codes: List[str], db: AsyncSession
) -> Dict[str, Course]:
    codes = list({c for c in codes if c})
    if not codes:
        return {}
    rows = await db.execute(select(Course).where(Course.code.in_(codes)))
    return {c.code: c for c in rows.scalars().all()}


async def simulate_cgpa(
    student_id: int,
    scenarios: List[Dict],
    db: AsyncSession,
) -> Dict:
    """scenarios: [{course_code, predicted_grade}]"""
    base_points, base_credits = await get_cgpa_components(student_id, db)
    codes = [s.get("course_code") for s in scenarios if s.get("course_code")]
    courses = await _load_courses_by_code(codes, db)

    added_points = 0.0
    added_credits = 0
    for s in scenarios:
        code = s.get("course_code")
        course = courses.get(code)
        if not course:
            continue
        pts = GRADE_POINTS.get(s.get("predicted_grade"))
        if pts is None:
            continue
        added_points += pts * course.credits
        added_credits += course.credits

    total_pts = base_points + added_points
    total_cr = base_credits + added_credits

    return {
        "projected_cgpa": round(total_pts / total_cr, 3) if total_cr else 0.0,
        "current_cgpa": round(base_points / base_credits, 3) if base_credits else 0.0,
        "total_credits": total_cr,
    }


async def required_grades_for_target(
    student_id: int,
    target_cgpa: float,
    course_codes: List[str],
    db: AsyncSession,
) -> Dict:
    """Return minimum grade per course needed to hit target CGPA."""
    base_points, base_credits = await get_cgpa_components(student_id, db)
    courses_map = await _load_courses_by_code(course_codes, db)
    courses = [courses_map[c] for c in course_codes if c in courses_map]
    upcoming_credits = sum(c.credits for c in courses)

    total_credits = base_credits + upcoming_credits
    required_total = target_cgpa * total_credits
    required_from_upcoming = required_total - base_points
    avg_needed = required_from_upcoming / upcoming_credits if upcoming_credits else 0.0

    ordered = [(k, v) for k, v in GRADE_POINTS.items() if v is not None]
    ordered.sort(key=lambda x: x[1])
    min_letter = "F"
    for letter, pts in ordered:
        if pts >= avg_needed:
            min_letter = letter
            break

    return {
        "target_cgpa": target_cgpa,
        "avg_grade_points_needed": round(avg_needed, 3),
        "minimum_letter_per_course": min_letter,
        "feasible": avg_needed <= 4.0,
        "per_course": [
            {"course_code": c.code, "course_title": c.name, "minimum_grade": min_letter}
            for c in courses
        ],
    }
