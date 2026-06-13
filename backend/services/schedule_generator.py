"""Generate 3 candidate schedules for a student.

Strategy:
  - Determine student's credit limit from CGPA
  - Compute remaining required courses (RequirementGroupCourse minus passed
    course_codes from Enrollment+Grade+Section)
  - Filter: prereqs met, offered this semester, seats available (live
    enrollment count < capacity), section.status == "Open"
  - Build 3 non-conflicting bundles using SectionMeeting for time checks:
      "fastest"  -> max credits up to limit
      "lightest" -> lower credits (12 target)
      "balanced" -> mid (18 target)

Schema translation notes (from the old codebase):
  - `Course.id` → `Course.code`
  - `Section.course_id` → `Section.course_code`
  - `Section.days / time_start / time_end` → `SectionMeeting.day_of_week /
    start_time / end_time`
  - `Section.enrolled_count` → `COUNT(Enrollment)` with status Enrolled
  - `TranscriptRecord` → `Enrollment` JOIN `Grade` JOIN `Section`
  - `student.id` → `student.student_id` (int)
"""
from typing import Dict, Iterable, List, Optional, Tuple
from uuid import uuid4

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.academic import AcademicStanding, RequirementGroupCourse
from models.course import Course, Section
from models.enrollment import Enrollment, Grade
from models.student import Major, Student
from services.academic_profile import build_academic_profile, personal_difficulty
from services.policy import get_policy
from services.registration_priority import batch_registration_tiers, current_plan_year
from services.validation import (
    check_prerequisites,
    get_credit_limit,
    passed_course_codes,
    resolve_semester_id,
    sections_conflict,
)


_DIFFICULTY_WEIGHT = {"Easy": 1.0, "Moderate": 2.0, "Hard": 3.0, "Unknown": 2.0}
_MIN_SAMPLE_SIZE = 3
_ENROLLED_STATUSES = ("Enrolled", "Satisfied")


def _difficulty_label(sample_size: int, pass_rate: Optional[float]) -> str:
    if sample_size < _MIN_SAMPLE_SIZE or pass_rate is None:
        return "Unknown"
    if pass_rate >= 0.85:
        return "Easy"
    if pass_rate >= 0.65:
        return "Moderate"
    return "Hard"


async def course_difficulty_stats(
    course_codes: Iterable[str], db: AsyncSession
) -> Dict[str, Dict]:
    """Historical pass-rate stats per course_code from Grade+Enrollment+Section."""
    codes = [c for c in course_codes if c]
    if not codes:
        return {}
    result = await db.execute(
        select(
            Section.course_code.label("course_code"),
            func.count(Grade.grade_id).label("total"),
            func.avg(Grade.grade_points).label("avg_gp"),
            func.sum(case((Grade.grade_points >= 2.0, 1), else_=0)).label("passed"),
        )
        .select_from(Grade)
        .join(Enrollment, Enrollment.enrollment_id == Grade.enrollment_id)
        .join(Section, Section.section_id == Enrollment.section_id)
        .where(
            Section.course_code.in_(codes),
            Grade.grade_points.is_not(None),
        )
        .group_by(Section.course_code)
    )
    out: Dict[str, Dict] = {}
    for row in result.all():
        total = int(row.total or 0)
        passed = int(row.passed or 0)
        pass_rate = (passed / total) if total else None
        avg_gp = float(row.avg_gp) if row.avg_gp is not None else None
        out[row.course_code] = {
            "sample_size": total,
            "pass_rate": pass_rate,
            "avg_grade_points": avg_gp,
            "difficulty": _difficulty_label(total, pass_rate),
        }
    return out


def _bundle_load(per_course: List[Tuple[int, str]]) -> Dict:
    total_credits = sum(cr for cr, _ in per_course)
    if total_credits == 0:
        return {"label": "Easy", "weighted_difficulty": 0.0, "total_credits": 0}
    weighted = sum(cr * _DIFFICULTY_WEIGHT[label] for cr, label in per_course) / total_credits
    if total_credits >= 19 or weighted >= 2.5:
        label = "Heavy"
    elif total_credits >= 15 or weighted >= 1.7:
        label = "Moderate"
    else:
        label = "Easy"
    return {
        "label": label,
        "weighted_difficulty": round(weighted, 2),
        "total_credits": total_credits,
    }


async def _remaining_required_codes(
    student_id: int,
    program_id: Optional[int],
    major_id: Optional[int],
    db: AsyncSession,
) -> set:
    if not program_id:
        return set()
    conds = [RequirementGroupCourse.program_id == program_id]
    if major_id:
        conds.append(
            (RequirementGroupCourse.major_id == major_id)
            | (RequirementGroupCourse.major_id.is_(None))
        )
    req_rows = await db.execute(
        select(RequirementGroupCourse.course_code).where(*conds)
    )
    required = {r[0] for r in req_rows.all() if r[0]}
    if not required:
        return set()
    taken = await passed_course_codes(student_id, db)
    # also exclude courses currently in progress (enrolled, no grade yet)
    in_progress_rows = await db.execute(
        select(Section.course_code)
        .select_from(Enrollment)
        .join(Section, Section.section_id == Enrollment.section_id)
        .where(
            Enrollment.student_id == student_id,
            Enrollment.status == "Enrolled",
        )
    )
    taken |= {r[0] for r in in_progress_rows.all() if r[0]}
    return required - taken


async def _seat_counts(
    section_ids: List[int], db: AsyncSession
) -> Dict[int, int]:
    """Live enrolled-count per section (status in Enrolled/Satisfied)."""
    if not section_ids:
        return {}
    rows = await db.execute(
        select(Enrollment.section_id, func.count(Enrollment.enrollment_id))
        .where(
            Enrollment.section_id.in_(section_ids),
            Enrollment.status.in_(_ENROLLED_STATUSES),
        )
        .group_by(Enrollment.section_id)
    )
    return {sid: int(cnt) for sid, cnt in rows.all()}


async def _candidate_sections(
    student_id: int,
    remaining_codes: set,
    semester_id: int,
    db: AsyncSession,
) -> List[Section]:
    if not remaining_codes:
        return []

    rows = await db.execute(
        select(Section)
        .options(selectinload(Section.meetings))
        .where(
            Section.course_code.in_(remaining_codes),
            Section.semester_id == semester_id,
            Section.status == "Open",
        )
    )
    sections = list(rows.scalars().unique().all())
    if not sections:
        return []

    seat_counts = await _seat_counts([s.section_id for s in sections], db)
    sections = [s for s in sections if seat_counts.get(s.section_id, 0) < s.capacity]

    viable: List[Section] = []
    for s in sections:
        ok, _ = await check_prerequisites(student_id, s.course_code, db)
        if ok:
            viable.append(s)
    return viable


async def course_demand(
    course_codes: Iterable[str], db: AsyncSession
) -> Dict[str, int]:
    """How many active students still need each course (it is in their major's
    plan and they have not passed it yet) — Dr. Ashraf §5: when seats are
    scarce, high-demand courses must be registered first."""
    codes = [c for c in course_codes if c]
    if not codes:
        return {}

    active_by_major = {
        code: int(cnt)
        for code, cnt in (await db.execute(
            select(Major.code, func.count(Student.student_id))
            .select_from(Student)
            .join(Major, Major.major_id == Student.major_id)
            .where(Student.status.in_(("Active", "Probation")))
            .group_by(Major.code)
        )).all()
    }
    needing_majors = (await db.execute(
        select(RequirementGroupCourse.course_code, RequirementGroupCourse.major_code)
        .where(RequirementGroupCourse.course_code.in_(codes))
        .distinct()
    )).all()
    passed_counts = {
        code: int(cnt)
        for code, cnt in (await db.execute(
            select(Section.course_code, func.count(func.distinct(Enrollment.student_id)))
            .select_from(Grade)
            .join(Enrollment, Enrollment.enrollment_id == Grade.enrollment_id)
            .join(Section, Section.section_id == Enrollment.section_id)
            .where(Section.course_code.in_(codes), Grade.grade_points >= 1.0)
            .group_by(Section.course_code)
        )).all()
    }

    demand: Dict[str, int] = {c: 0 for c in codes}
    for course_code, major_code in needing_majors:
        demand[course_code] = demand.get(course_code, 0) + active_by_major.get(major_code, 0)
    for code in demand:
        demand[code] = max(demand[code] - passed_counts.get(code, 0), 0)
    return demand


async def _load_course_map(codes: Iterable[str], db: AsyncSession) -> Dict[str, Course]:
    codes = list({c for c in codes if c})
    if not codes:
        return {}
    rows = await db.execute(select(Course).where(Course.code.in_(codes)))
    return {c.code: c for c in rows.scalars().all()}


async def _build_bundle(
    sections: List[Section],
    courses: Dict[str, Course],
    target_credits: int,
    credit_limit: int,
    hard_codes: Optional[set] = None,
    max_hard: int = 99,
) -> List[Section]:
    """Greedy: pick non-conflicting sections until target reached (cap at
    limit). Never stacks more than `max_hard` personally-hard courses — a
    student weak in an area gets those courses with room to focus."""
    hard_codes = hard_codes or set()
    chosen: List[Section] = []
    used_codes = set()
    total = 0
    hard_count = 0
    for s in sections:
        if s.course_code in used_codes:
            continue
        if any(sections_conflict(s, c) for c in chosen):
            continue
        course = courses.get(s.course_code)
        if not course:
            continue
        if total + course.credits > credit_limit:
            continue
        if s.course_code in hard_codes and hard_count >= max_hard:
            continue
        chosen.append(s)
        used_codes.add(s.course_code)
        total += course.credits
        if s.course_code in hard_codes:
            hard_count += 1
        if total >= target_credits:
            break
    return chosen


async def _current_cgpa(student: Student, db: AsyncSession) -> float:
    row = await db.execute(
        select(AcademicStanding.cgpa)
        .where(AcademicStanding.student_code == student.student_code)
        .order_by(AcademicStanding.semester_id.desc())
        .limit(1)
    )
    val = row.scalar_one_or_none()
    if val is not None:
        return float(val)
    return float(student.cgpa) if student.cgpa is not None else 0.0


def _serialize_meetings(section: Section) -> List[Dict]:
    return [
        {
            "meeting_type": m.meeting_type,
            "day_of_week": m.day_of_week,
            "start_time": m.start_time,
            "end_time": m.end_time,
            "location": m.location,
        }
        for m in (section.meetings or [])
    ]


async def generate_schedules(
    student: Student,
    semester_code: str,
    db: AsyncSession,
    max_credits_preference: Optional[int] = None,
) -> List[Dict]:
    semester_id = await resolve_semester_id(semester_code, db)
    if semester_id is None:
        return []

    cgpa = await _current_cgpa(student, db)
    hard_limit = await get_credit_limit(
        cgpa, "Summer" in semester_code, db, student_id=student.student_id
    )
    effective_limit = min(max_credits_preference or hard_limit, hard_limit)

    remaining_codes = await _remaining_required_codes(
        student.student_id, student.program_id, student.major_id, db
    )
    candidates = await _candidate_sections(
        student.student_id, remaining_codes, semester_id, db
    )
    if not candidates:
        return []

    courses = await _load_course_map(
        {s.course_code for s in candidates}, db
    )
    stats = await course_difficulty_stats(list(courses.keys()), db)
    demand = await course_demand(list(courses.keys()), db)

    # Where each course sits in the student's study plan — recommendations
    # follow the plan year, with §5 scarcity ordering within it.
    plan_conds = [RequirementGroupCourse.course_code.in_(list(courses.keys()))]
    if student.major_id:
        plan_conds.append(RequirementGroupCourse.major_id == student.major_id)
    plan_year: Dict[str, int] = {
        code: int(yr or 9)
        for code, yr in (await db.execute(
            select(
                RequirementGroupCourse.course_code,
                func.min(RequirementGroupCourse.required_year),
            ).where(*plan_conds).group_by(RequirementGroupCourse.course_code)
        )).all()
    }

    # Open seats per course in THIS semester — scarcity is demand vs seats.
    seat_counts = await _seat_counts([s.section_id for s in candidates], db)
    open_seats: Dict[str, int] = {}
    for s in candidates:
        free = max(s.capacity - seat_counts.get(s.section_id, 0), 0)
        open_seats[s.course_code] = open_seats.get(s.course_code, 0) + free

    def _scarcity(code: str) -> float:
        return demand.get(code, 0) / max(open_seats.get(code, 1), 1)

    # ---- per-student intelligence, derived live (never memorized) ----
    profile = await build_academic_profile(student.student_id, db)
    tiers = await batch_registration_tiers(student, list(courses.keys()), db)
    current_year = await current_plan_year(student.student_id, db)

    personal: Dict[str, Dict] = {}
    for code, c in courses.items():
        cohort_diff = stats.get(code, {}).get("difficulty", "Unknown")
        personal[code] = personal_difficulty(profile, code, c.name, cohort_diff)
    hard_codes = {code for code, p in personal.items() if p["personal"] == "Hard for you"}

    def _bucket(code: str) -> int:
        """0 = retake/backlog (urgent), 1 = due now per plan, 2 = ahead of plan."""
        if tiers.get(code, (1, ""))[0] in (2, 3):
            return 0
        py = plan_year.get(code, current_year)
        if py < current_year:
            return 0
        if py > current_year:
            return 2
        return 1

    # Racing ahead of the plan needs a strong record (same bar as overload).
    overload_bar = float(await get_policy("enrollment.overload_min_cgpa", db))
    if cgpa <= overload_bar:
        on_plan = [s for s in candidates if _bucket(s.course_code) != 2]
        if on_plan:
            candidates = on_plan

    # Chain criticality: a course that transitively unlocks many still-owed
    # courses must come early — delaying it delays everything behind it.
    from services.prereq_graph import load_chain_unlocks
    chain = await load_chain_unlocks(db, restrict_to=set(remaining_codes))

    # Ordering: urgency bucket → plan year → chain criticality → scarcity
    # (Dr. Ashraf §5) → credits → cohort difficulty.
    def _order_key(s: Section):
        course = courses.get(s.course_code)
        credits = course.credits if course else 0
        diff_label = stats.get(s.course_code, {}).get("difficulty", "Unknown")
        diff_weight = _DIFFICULTY_WEIGHT.get(diff_label, 2.0)
        code = s.course_code
        return (_bucket(code), plan_year.get(code, 9),
                -chain.get(code, 0), -_scarcity(code), -credits, diff_weight)

    candidates.sort(key=_order_key)

    # Focus ordering: when a due course sits in the student's WEAK area it
    # comes first, surrounded by their easiest companions — light load to
    # concentrate on the hard subject without falling behind the plan.
    def _focus_key(s: Section):
        code = s.course_code
        diff_label = stats.get(code, {}).get("difficulty", "Unknown")
        return (
            0 if (code in hard_codes and _bucket(code) <= 1) else 1,
            _bucket(code),
            plan_year.get(code, 9),
            _DIFFICULTY_WEIGHT.get(diff_label, 2.0),
            -_scarcity(code),
        )

    focus_candidates = sorted(candidates, key=_focus_key)

    # Hard-course caps per bundle: never stack weak-area courses together.
    # Balanced/lightest are HARD-capped at their targets so the three options
    # are genuinely different loads (greedy must not overshoot into a clone
    # of the fastest bundle).
    fastest = await _build_bundle(candidates, courses, effective_limit, effective_limit,
                                  hard_codes=hard_codes, max_hard=2)
    balanced = await _build_bundle(candidates, courses, min(18, effective_limit),
                                   min(18, effective_limit),
                                   hard_codes=hard_codes, max_hard=1)
    lightest = await _build_bundle(focus_candidates, courses, min(12, effective_limit),
                                   min(12, effective_limit),
                                   hard_codes=hard_codes, max_hard=1)

    def serialize(bundle: List[Section], label: str) -> Dict:
        items = []
        per_course_difficulty: List[Tuple[int, str]] = []
        for s in bundle:
            course = courses.get(s.course_code)
            credits = course.credits if course else 0
            stat = stats.get(
                s.course_code,
                {"difficulty": "Unknown", "pass_rate": None, "sample_size": 0, "avg_grade_points": None},
            )
            per_course_difficulty.append((credits, stat["difficulty"]))
            pers = personal.get(s.course_code, {})
            tier, tier_reason = tiers.get(s.course_code, (1, ""))
            items.append(
                {
                    "section_id": s.section_id,
                    "course_code": s.course_code,
                    "course_title": course.name if course else "",
                    "credits": credits,
                    "section_number": s.section_number,
                    "instructor": s.instructor_name,
                    "meetings": _serialize_meetings(s),
                    "difficulty": stat["difficulty"],
                    "personal_difficulty": pers.get("personal", stat["difficulty"]),
                    "personal_reason": pers.get("reason", ""),
                    "subject_area": pers.get("area", ""),
                    "historical_pass_rate": stat["pass_rate"],
                    "historical_sample_size": stat["sample_size"],
                    "historical_avg_grade_points": stat["avg_grade_points"],
                    "students_needing": demand.get(s.course_code, 0),
                    "open_seats": open_seats.get(s.course_code, 0),
                    "registration_tier": tier,
                    "registration_tier_reason": tier_reason,
                    "registration_priority": (
                        "High" if _scarcity(s.course_code) >= 1.0 else "Normal"
                    ),
                    "plan_status": ("retake" if tier in (2, 3)
                                    else "ahead of plan" if tier == 4 else "on plan"),
                }
            )
        load = _bundle_load(per_course_difficulty)

        hard_in = [s.course_code for s in bundle if s.course_code in hard_codes]
        note = ""
        if hard_in:
            p = personal[hard_in[0]]
            note = (f"{', '.join(hard_in)} is in your weaker area ({p['area']}: "
                    f"{p['reason']}) — paired with lighter companions so you can focus on it.")

        return {
            "option_id": str(uuid4()),
            "label": label,
            "total_credits": load["total_credits"],
            "load_score": load["label"],
            "weighted_difficulty": load["weighted_difficulty"],
            "note": note,
            "sections": items,
        }

    options = [
        serialize(fastest, "Fastest to Graduation"),
        serialize(balanced, "Balanced"),
        serialize(lightest, "Focus Load" if any(
            s.course_code in hard_codes for s in lightest) else "Lightest Load"),
    ]
    # never show the same bundle twice under different labels
    seen_sets = []
    unique = []
    for o in options:
        ids = frozenset(item["section_id"] for item in o["sections"])
        if ids in seen_sets:
            continue
        seen_sets.append(ids)
        unique.append(o)
    return unique
