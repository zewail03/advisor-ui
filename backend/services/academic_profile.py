"""Per-student academic profile, derived live from real grades.

Nothing here is remembered or hand-labeled: every time it runs it groups the
student's own graded courses into subject areas (math, physics, hardware,
programming, AI/data, general), compares their average grade points in each
area against the COHORT average for the very same courses, and flags areas
where the student is measurably weaker or stronger.

The planner uses this to shape load: a student weak in mathematics gets math
courses scheduled in lighter semesters with easier companions — never skipped,
never reordered against the study plan.
"""
import re
from typing import Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.course import Course, Section
from models.enrollment import Enrollment, Grade

# An area is "weak"/"strong" only with enough evidence and a real gap.
MIN_COURSES_FOR_SIGNAL = 2
WEAK_DELTA = -0.35     # at least this far below the cohort
STRONG_DELTA = 0.35
WEAK_ABSOLUTE = 2.0    # below C average is weak regardless of cohort

_AREA_RULES = [
    ("mathematics", lambda code, name: code.startswith("MAT")
        or re.search(r"\b(calculus|algebra|statistic|probabilit|differential|discrete math)", name)),
    ("physics", lambda code, name: code.startswith("PHY")),
    ("hardware", lambda code, name: code.startswith("ELE")
        or re.search(r"\b(logic|circuit|architecture|electronics|embedded|digital|hardware|signal|microprocessor)", name)),
    ("programming", lambda code, name: re.search(
        r"\b(programming|software|data structure|database|web|object.?oriented|algorithm|operating system|compiler)", name)),
    ("ai_data", lambda code, name: code.startswith(("AIE", "AIS"))
        or re.search(r"\b(machine learning|artificial|intelligen|data mining|neural|vision|nlp|natural language|robot|deep learning)", name)),
]


def course_area(code: str, name: str) -> str:
    code_u = (code or "").upper()
    name_l = (name or "").lower()
    for area, rule in _AREA_RULES:
        if rule(code_u, name_l):
            return area
    return "general"


async def _cohort_avg_by_course(course_codes: List[str], db: AsyncSession) -> Dict[str, float]:
    """Average counted grade points per course across ALL students."""
    if not course_codes:
        return {}
    rows = await db.execute(
        select(Section.course_code, func.avg(Grade.grade_points))
        .select_from(Grade)
        .join(Enrollment, Enrollment.enrollment_id == Grade.enrollment_id)
        .join(Section, Section.section_id == Enrollment.section_id)
        .where(
            Section.course_code.in_(course_codes),
            Grade.counts_in_gpa == True,  # noqa: E712
            Grade.grade_points.is_not(None),
        )
        .group_by(Section.course_code)
    )
    return {code: float(avg) for code, avg in rows.all() if avg is not None}


async def build_academic_profile(student_id: int, db: AsyncSession) -> Dict:
    """Live profile: per-area averages vs cohort + weak/strong area flags."""
    rows = (await db.execute(
        select(Section.course_code, Course.name, Grade.grade_points)
        .select_from(Grade)
        .join(Enrollment, Enrollment.enrollment_id == Grade.enrollment_id)
        .join(Section, Section.section_id == Enrollment.section_id)
        .join(Course, Course.code == Section.course_code)
        .where(
            Enrollment.student_id == student_id,
            Grade.counts_in_gpa == True,  # noqa: E712
            Grade.grade_points.is_not(None),
        )
    )).all()
    if not rows:
        return {"areas": {}, "weak_areas": [], "strong_areas": [], "graded_courses": 0}

    cohort = await _cohort_avg_by_course([r[0] for r in rows], db)

    areas: Dict[str, Dict] = {}
    for code, name, pts in rows:
        area = course_area(code, name)
        a = areas.setdefault(area, {"points": [], "cohort_points": [], "courses": []})
        a["points"].append(float(pts))
        if code in cohort:
            a["cohort_points"].append(cohort[code])
        a["courses"].append({"code": code, "points": float(pts),
                             "cohort_avg": round(cohort.get(code, 0.0), 2)})

    weak, strong = [], []
    out: Dict[str, Dict] = {}
    for area, a in areas.items():
        n = len(a["points"])
        avg = sum(a["points"]) / n
        pass_rate = len([p for p in a["points"] if p >= 1.0]) / n
        cohort_avg = (sum(a["cohort_points"]) / len(a["cohort_points"])) if a["cohort_points"] else avg
        delta = avg - cohort_avg
        label = "average"
        if n >= MIN_COURSES_FOR_SIGNAL and (delta <= WEAK_DELTA or avg < WEAK_ABSOLUTE):
            label = "weak"
            weak.append(area)
        elif n >= MIN_COURSES_FOR_SIGNAL and delta >= STRONG_DELTA:
            label = "strong"
            strong.append(area)
        out[area] = {
            "avg_points": round(avg, 2),
            "cohort_avg": round(cohort_avg, 2),
            "delta": round(delta, 2),
            "pass_rate": round(pass_rate, 2),
            "courses_taken": n,
            "label": label,
            "evidence": a["courses"],
        }

    return {
        "areas": out,
        "weak_areas": weak,
        "strong_areas": strong,
        "graded_courses": len(rows),
    }


def personal_difficulty(
    profile: Dict, course_code: str, course_name: str, cohort_difficulty: str
) -> Dict:
    """Blend cohort difficulty with the student's own area record."""
    area = course_area(course_code, course_name)
    info: Optional[Dict] = (profile.get("areas") or {}).get(area)
    if info and info["label"] == "weak":
        return {
            "area": area,
            "personal": "Hard for you",
            "reason": (f"your {area} average is {info['avg_points']:.2f} "
                       f"vs class {info['cohort_avg']:.2f} over {info['courses_taken']} courses"),
        }
    if info and info["label"] == "strong":
        return {
            "area": area,
            "personal": "Easier for you",
            "reason": (f"your {area} average is {info['avg_points']:.2f} "
                       f"vs class {info['cohort_avg']:.2f}"),
        }
    return {"area": area, "personal": cohort_difficulty, "reason": ""}
