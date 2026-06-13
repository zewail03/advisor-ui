"""Business rule validation for enrollment.

Five checks in order:
  1. is_registration_window_open
  2. check_prerequisites
  3. check_credit_limit
  4. check_time_conflict
  5. check_seat_availability (caller should also decide waitlist behavior)

Schema notes:
  - Student identity is the integer `student_id`.
  - Prerequisites join by `course_code` (string) — no more integer FK.
  - Section.meetings is the source of truth for days/times; the generator
    and conflict checker iterate meetings, not Section columns.
  - Seat availability is computed from the live COUNT of Enrollment rows
    where status='Enrolled'; there is no Section.enrolled_count column.
"""
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.academic import AcademicStanding, RegistrationPeriod, Semester
from models.course import Course, Prerequisite, Section, SectionMeeting
from models.enrollment import Enrollment, Grade
from services.policy import get_policy


_ENROLLED_STATUSES = ("Enrolled", "Satisfied")


async def get_credit_limit(
    cgpa: float,
    is_summer: bool,
    db: AsyncSession,
    student_id: Optional[int] = None,
) -> int:
    """Per-term credit-hour cap — the semester-indexed load ladder from
    Dr. Ashraf's advising notes (§1.1–§1.4). When `student_id` is given, the
    semester being registered is (completed main semesters + 1) and the Math 0
    result drives the first-semester load. Every value is policy-driven."""
    if is_summer:
        return int(await get_policy("enrollment.credit_limit_summer", db))

    sem_index = 4  # default to the steady-state tier when caller has no student
    math0_passed = True
    if student_id is not None:
        from models.student import Student
        from services.gpa_calculator import _main_semesters_completed

        sem_index = await _main_semesters_completed(student_id, db) + 1
        student = await db.get(Student, student_id)
        if student is not None and getattr(student, "math0_passed", None) is not None:
            math0_passed = bool(student.math0_passed)

    if sem_index <= 1:  # §1.1 — load set by the Math 0 placement exam
        key = (
            "enrollment.sem1_credits_math0_pass"
            if math0_passed
            else "enrollment.sem1_credits_math0_fail"
        )
        return int(await get_policy(key, db))
    if sem_index == 2:  # §1.2 — fixed load, CGPA not considered
        return int(await get_policy("enrollment.sem2_credits", db))
    if sem_index == 3:  # §1.3 — the 1.667 bar starts to matter
        bar = float(await get_policy("standing.probation_cgpa_early", db))
        key = (
            "enrollment.credit_limit_standard"
            if cgpa >= bar
            else "enrollment.credit_limit_low"
        )
        return int(await get_policy(key, db))
    # §1.4 — semester 4 onward: 2.0 bar, overload above 3.0
    overload_cgpa = float(await get_policy("enrollment.overload_min_cgpa", db))
    regular_bar = float(await get_policy("standing.probation_cgpa", db))
    if cgpa > overload_cgpa:
        return int(await get_policy("enrollment.credit_limit_high", db))
    if cgpa >= regular_bar:
        return int(await get_policy("enrollment.credit_limit_standard", db))
    return int(await get_policy("enrollment.credit_limit_low", db))


def _time_to_minutes(t: Optional[str]) -> Optional[int]:
    if not t:
        return None
    parts = t.strip().split(":")
    try:
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        return h * 60 + m
    except (ValueError, IndexError):
        return None


def _meetings_conflict(
    a: SectionMeeting, b: SectionMeeting
) -> bool:
    if not (a.day_of_week and b.day_of_week):
        return False
    if a.day_of_week.strip().lower() != b.day_of_week.strip().lower():
        return False
    a_start, a_end = _time_to_minutes(a.start_time), _time_to_minutes(a.end_time)
    b_start, b_end = _time_to_minutes(b.start_time), _time_to_minutes(b.end_time)
    if None in (a_start, a_end, b_start, b_end):
        return False
    return not (a_end <= b_start or a_start >= b_end)


def sections_conflict(a: Section, b: Section) -> bool:
    """True iff any meeting of `a` overlaps in day+time with any meeting of `b`.
    Callers must ensure both sections have `.meetings` loaded (selectinload)."""
    for m_a in a.meetings or []:
        for m_b in b.meetings or []:
            if _meetings_conflict(m_a, m_b):
                return True
    return False


async def resolve_semester_id(semester_code: str, db: AsyncSession) -> Optional[int]:
    normalized = semester_code.replace("-", " ")
    row = await db.execute(
        select(Semester.semester_id).where(Semester.code == normalized)
    )
    return row.scalar_one_or_none()


async def current_cgpa_for(
    student_id: int, student_code: str, db: AsyncSession
) -> float:
    row = await db.execute(
        select(AcademicStanding.cgpa)
        .where(AcademicStanding.student_code == student_code)
        .order_by(AcademicStanding.semester_id.desc())
        .limit(1)
    )
    val = row.scalar_one_or_none()
    if val is not None:
        return float(val)
    return 0.0


async def passed_course_codes(student_id: int, db: AsyncSession) -> set:
    """Course codes with a passing grade — the bar comes from the policy
    engine (enrollment.prereq_min_points, default 1.0 = D)."""
    min_points = float(await get_policy("enrollment.prereq_min_points", db))
    rows = await db.execute(
        select(Section.course_code)
        .select_from(Enrollment)
        .join(Grade, Grade.enrollment_id == Enrollment.enrollment_id)
        .join(Section, Section.section_id == Enrollment.section_id)
        .where(
            Enrollment.student_id == student_id,
            Grade.grade_points >= min_points,
        )
    )
    return {r[0] for r in rows.all() if r[0]}


async def active_enrollments_this_semester(
    student_id: int, semester_id: int, db: AsyncSession
) -> List[Section]:
    """Sections the student is currently enrolled in this semester,
    with meetings eager-loaded for conflict checks."""
    rows = await db.execute(
        select(Section)
        .options(selectinload(Section.meetings))
        .join(Enrollment, Enrollment.section_id == Section.section_id)
        .where(
            Enrollment.student_id == student_id,
            Enrollment.status.in_(_ENROLLED_STATUSES),
            Section.semester_id == semester_id,
        )
    )
    return list(rows.scalars().unique().all())


async def is_registration_window_open(
    semester_code: str, db: AsyncSession
) -> Tuple[bool, str]:
    now = datetime.utcnow()
    semester_id = await resolve_semester_id(semester_code, db)
    if not semester_id:
        return False, f"Semester {semester_code} not found"
    result = await db.execute(
        select(RegistrationPeriod).where(
            and_(
                RegistrationPeriod.semester_id == semester_id,
                or_(
                    RegistrationPeriod.open_date.is_(None),
                    RegistrationPeriod.open_date <= now,
                ),
                or_(
                    RegistrationPeriod.close_date.is_(None),
                    RegistrationPeriod.close_date >= now,
                ),
                RegistrationPeriod.is_active == True,  # noqa: E712
            )
        )
    )
    period = result.scalar_one_or_none()
    if not period:
        return False, f"Registration window for {semester_code} is not currently open"
    return True, "OK"


async def check_prerequisites(
    student_id: int, course_code: str, db: AsyncSession
) -> Tuple[bool, str]:
    prereq_rows = await db.execute(
        select(Prerequisite.prerequisite_course_code).where(
            Prerequisite.course_code == course_code
        )
    )
    prereq_codes = [r[0] for r in prereq_rows.all() if r[0]]
    if not prereq_codes:
        return True, "OK"

    passed = await passed_course_codes(student_id, db)
    missing = [code for code in prereq_codes if code not in passed]
    if missing:
        return False, f"Prerequisite(s) not satisfied: {', '.join(missing)} (need grade ≥ D)"
    return True, "OK"


async def check_corequisites(
    student_id: int,
    course_code: str,
    semester_code: str,
    db: AsyncSession,
    planned_course_codes: Optional[set] = None,
) -> Tuple[bool, str]:
    """The real AIU schema has no corequisite table. Kept as a no-op for
    backward compatibility with enrollment_service callers."""
    return True, "OK"


async def check_time_conflict(
    student_id: int, section_id: int, semester_code: str, db: AsyncSession
) -> Tuple[bool, str]:
    new_section = await db.execute(
        select(Section)
        .options(selectinload(Section.meetings))
        .where(Section.section_id == section_id)
    )
    new_section = new_section.scalar_one_or_none()
    if not new_section or not new_section.meetings:
        return True, "OK"

    semester_id = new_section.semester_id
    existing = await active_enrollments_this_semester(student_id, semester_id, db)
    for s in existing:
        if s.section_id == new_section.section_id:
            continue
        if sections_conflict(new_section, s):
            # Describe the first overlapping meeting for the error message
            sample = s.meetings[0] if s.meetings else None
            where = (
                f"{sample.day_of_week} {sample.start_time}-{sample.end_time}"
                if sample
                else "existing section"
            )
            return False, f"Time conflict with {s.course_code} ({where})"
    return True, "OK"


async def check_credit_limit(
    student_id: int,
    new_credits: int,
    semester_code: str,
    db: AsyncSession,
) -> Tuple[bool, str]:
    semester_id = await resolve_semester_id(semester_code, db)
    if semester_id is None:
        return False, f"Semester {semester_code} not found"

    from models.student import Student
    student = await db.get(Student, student_id)
    cgpa = float(student.cgpa) if student and student.cgpa is not None else 0.0
    if student:
        cgpa = await current_cgpa_for(student_id, student.student_code, db) or cgpa
    is_summer = "Summer" in semester_code
    limit = await get_credit_limit(cgpa, is_summer, db, student_id=student_id)

    current_result = await db.execute(
        select(func.coalesce(func.sum(Course.credits), 0))
        .select_from(Enrollment)
        .join(Section, Section.section_id == Enrollment.section_id)
        .join(Course, Course.code == Section.course_code)
        .where(
            Enrollment.student_id == student_id,
            Enrollment.status.in_(_ENROLLED_STATUSES),
            Section.semester_id == semester_id,
        )
    )
    current_credits = int(current_result.scalar() or 0)

    if current_credits + new_credits > limit:
        return False, (
            f"Credit limit exceeded. CGPA {cgpa:.2f} allows max {limit} credits; "
            f"currently enrolled for {current_credits}"
        )
    return True, "OK"


async def count_active_enrollments(section_id: int, db: AsyncSession) -> int:
    row = await db.execute(
        select(func.count(Enrollment.enrollment_id)).where(
            Enrollment.section_id == section_id,
            Enrollment.status.in_(_ENROLLED_STATUSES),
        )
    )
    return int(row.scalar() or 0)


async def check_seat_availability(
    section_id: int, db: AsyncSession
) -> Tuple[bool, str]:
    section = await db.get(Section, section_id)
    if not section:
        return False, "Section not found"
    if section.status != "Open":
        return False, "Section is closed"
    enrolled = await count_active_enrollments(section.section_id, db)
    if enrolled >= section.capacity:
        return False, "Section is full"
    return True, "OK"
