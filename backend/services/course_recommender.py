"""Course recommendation engine.

Ranks remaining required courses for a student using real data:
  - Unlock impact: how many other required courses list this as a prerequisite
    (courses that unblock the most progress score higher).
  - Historical difficulty from Grade pass rates (real transcript data).
  - Offered this semester (has an Open section).
  - Prerequisites actually met by the student's passed enrollments.
  - CGPA-aware: students below 2.0 get easier courses boosted; students above
    3.0 get difficulty-agnostic ranking since they can handle heavier load.

No hardcoded difficulty labels; difficulty comes from historical pass rates of
Enrollment+Grade rows joined through Section.course_code. Safe to explain to a
committee.
"""
from typing import Dict, Iterable, List, Optional

from sqlalchemy import select, and_, case, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.academic import AcademicStanding, RequirementGroupCourse, Semester
from models.course import Course, Section
from models.enrollment import Enrollment, Grade
from models.student import Student
from services.validation import check_prerequisites


_DIFFICULTY_BOOST_LOW_CGPA = {"Easy": 1.5, "Moderate": 1.0, "Hard": 0.4, "Unknown": 1.0}
_DIFFICULTY_BOOST_MID_CGPA = {"Easy": 1.2, "Moderate": 1.0, "Hard": 0.8, "Unknown": 1.0}
_DIFFICULTY_BOOST_HIGH_CGPA = {"Easy": 1.0, "Moderate": 1.0, "Hard": 1.1, "Unknown": 1.0}
_MIN_SAMPLE_SIZE = 3


def _cgpa_weights(cgpa: float) -> Dict[str, float]:
    if cgpa < 2.0:
        return _DIFFICULTY_BOOST_LOW_CGPA
    if cgpa < 3.0:
        return _DIFFICULTY_BOOST_MID_CGPA
    return _DIFFICULTY_BOOST_HIGH_CGPA


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
    """Historical pass-rate stats per course_code, derived from Grade+Enrollment+Section."""
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


async def _required_course_codes(
    program_id: Optional[int], major_id: Optional[int], db: AsyncSession
) -> set:
    if not program_id:
        return set()
    conds = [RequirementGroupCourse.program_id == program_id]
    if major_id:
        conds.append(
            (RequirementGroupCourse.major_id == major_id)
            | (RequirementGroupCourse.major_id.is_(None))
        )
    rows = await db.execute(
        select(RequirementGroupCourse.course_code).where(and_(*conds))
    )
    return {r[0] for r in rows.all() if r[0]}


async def _passed_course_codes(student_id: int, db: AsyncSession) -> set:
    rows = await db.execute(
        select(Section.course_code)
        .select_from(Enrollment)
        .join(Grade, Grade.enrollment_id == Enrollment.enrollment_id)
        .join(Section, Section.section_id == Enrollment.section_id)
        .where(
            Enrollment.student_id == student_id,
            Grade.grade_points >= 1.0,
        )
    )
    passed = {r[0] for r in rows.all() if r[0]}
    # also exclude courses the student is taking RIGHT NOW (in-progress,
    # no grade yet) — never recommend what they're already enrolled in
    in_progress = await db.execute(
        select(Section.course_code)
        .select_from(Enrollment)
        .join(Section, Section.section_id == Enrollment.section_id)
        .where(
            Enrollment.student_id == student_id,
            Enrollment.status == "Enrolled",
        )
    )
    return passed | {r[0] for r in in_progress.all() if r[0]}


async def _remaining_required_courses(
    student_id: int,
    program_id: Optional[int],
    major_id: Optional[int],
    db: AsyncSession,
) -> List[Course]:
    required_codes = await _required_course_codes(program_id, major_id, db)
    if not required_codes:
        return []
    taken_codes = await _passed_course_codes(student_id, db)
    remaining_codes = required_codes - taken_codes
    if not remaining_codes:
        return []
    course_rows = await db.execute(
        select(Course).where(Course.code.in_(remaining_codes))
    )
    return list(course_rows.scalars().all())


async def _unlock_counts(
    remaining_codes: List[str], required_codes: set, db: AsyncSession
) -> Dict[str, int]:
    """For each remaining course, how many still-owed courses it TRANSITIVELY
    unlocks — a course at the head of a long prerequisite chain is critical
    because delaying it delays everything behind it."""
    if not remaining_codes:
        return {}
    from services.prereq_graph import load_chain_unlocks

    remaining_set = set(remaining_codes) & set(required_codes) if required_codes else set(remaining_codes)
    chain = await load_chain_unlocks(db, restrict_to=remaining_set)
    return {code: chain.get(code, 0) for code in remaining_codes}


async def _offered_course_codes(
    course_codes: List[str], semester_id: int, db: AsyncSession
) -> set:
    if not course_codes:
        return set()
    rows = await db.execute(
        select(Section.course_code).where(
            and_(
                Section.course_code.in_(course_codes),
                Section.semester_id == semester_id,
                Section.status == "Open",
            )
        )
    )
    return {r[0] for r in rows.all() if r[0]}


async def _resolve_semester_id(semester_code: str, db: AsyncSession) -> Optional[int]:
    normalized = (semester_code or "").replace("-", " ").strip()
    row = await db.execute(
        select(Semester.semester_id).where(Semester.code == normalized)
    )
    return row.scalar_one_or_none()


async def _current_cgpa(student: Student, db: AsyncSession) -> float:
    if student.cgpa is not None:
        try:
            return float(student.cgpa)
        except (TypeError, ValueError):
            pass
    row = await db.execute(
        select(AcademicStanding.cgpa)
        .where(AcademicStanding.student_code == student.student_code)
        .order_by(AcademicStanding.recorded_at.desc())
        .limit(1)
    )
    val = row.scalar_one_or_none()
    return float(val) if val is not None else 0.0


async def recommend_courses(
    student: Student,
    semester_code: str,
    db: AsyncSession,
    top_n: int = 5,
) -> Dict:
    remaining = await _remaining_required_courses(
        student.student_id, student.program_id, student.major_id, db
    )
    if not remaining:
        return {
            "semester": semester_code,
            "current_cgpa": 0.0,
            "recommendations": [],
            "reason": "No remaining required courses found for this program.",
        }

    required_codes = await _required_course_codes(
        student.program_id, student.major_id, db
    )
    cgpa = await _current_cgpa(student, db)
    weights = _cgpa_weights(cgpa)

    codes = [c.code for c in remaining]
    stats = await course_difficulty_stats(codes, db)
    unlocks = await _unlock_counts(codes, required_codes, db)

    semester_id = await _resolve_semester_id(semester_code, db)
    offered = await _offered_course_codes(codes, semester_id, db) if semester_id else set()

    scored: List[Dict] = []
    for c in remaining:
        prereqs_met, prereq_msg = await check_prerequisites(
            student.student_id, c.code, db
        )
        stat = stats.get(
            c.code,
            {"difficulty": "Unknown", "pass_rate": None, "sample_size": 0, "avg_grade_points": None},
        )
        unlock = unlocks.get(c.code, 0)
        difficulty_mult = weights.get(stat["difficulty"], 1.0)
        offered_bonus = 1.0 if c.code in offered else 0.0

        base = 2.0 * unlock + 1.5 * offered_bonus + 0.5 * c.credits
        score = base * difficulty_mult
        if not prereqs_met:
            score *= 0.2

        scored.append(
            {
                "course_id": c.course_id,
                "code": c.code,
                "title": c.name,
                "credits": c.credits,
                "unlocks": unlock,
                "offered_this_semester": c.code in offered,
                "prereqs_met": prereqs_met,
                "prereq_blocker": None if prereqs_met else prereq_msg,
                "difficulty": stat["difficulty"],
                "historical_pass_rate": stat["pass_rate"],
                "historical_sample_size": stat["sample_size"],
                "score": round(score, 3),
                "reason": _reason(unlock, stat, offered=c.code in offered, prereqs_met=prereqs_met, cgpa=cgpa),
            }
        )

    scored.sort(key=lambda r: (r["prereqs_met"], r["score"]), reverse=True)
    return {
        "semester": semester_code,
        "current_cgpa": cgpa,
        "cgpa_band": _cgpa_band(cgpa),
        "recommendations": scored[:top_n],
    }


def _cgpa_band(cgpa: float) -> str:
    if cgpa < 2.0:
        return "recovery"
    if cgpa < 3.0:
        return "standard"
    return "advanced"


def _reason(unlock: int, stat: Dict, offered: bool, prereqs_met: bool, cgpa: float) -> str:
    bits: List[str] = []
    if unlock > 0:
        bits.append(f"unlocks {unlock} downstream course{'s' if unlock != 1 else ''}")
    if stat["difficulty"] != "Unknown" and stat["pass_rate"] is not None:
        bits.append(
            f"{stat['difficulty'].lower()} historically ({int(stat['pass_rate']*100)}% pass rate, n={stat['sample_size']})"
        )
    if offered:
        bits.append("offered this semester")
    else:
        bits.append("not offered this semester")
    if not prereqs_met:
        bits.append("prereqs not yet met")
    if cgpa < 2.0 and stat["difficulty"] == "Easy":
        bits.append("good fit for recovery term")
    return "; ".join(bits)


def render_recommendations_summary(payload: Dict) -> str:
    recs = payload.get("recommendations", [])
    if not recs:
        return payload.get("reason") or "No course recommendations available."
    lines = [
        f"Top {len(recs)} courses for {payload['semester']} (CGPA {payload.get('current_cgpa', 0):.2f}):"
    ]
    for i, r in enumerate(recs, 1):
        lines.append(f"  {i}. {r['code']} — {r['title']} ({r['credits']}cr). {r['reason']}.")
    return "\n".join(lines)
