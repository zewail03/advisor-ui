"""Emergency academic recovery plan builder.

Produces a structured plan for any student: at-risk current courses (failing
percentage on graded rows), retake candidates (prior F/FW/D from Grade history),
grades needed to hit CGPA 2.0, and severity.

Schema notes:
  - AcademicStanding is per-semester; look up latest by student_code.
  - Real schema has no midterm_score column; we use Grade.percentage on in-
    progress rows as the failing-grade signal.
  - "Transcript" = Enrollment JOIN Grade JOIN Section JOIN Course.
  - Status enum: Good Standing / Warning / Probation / Final Chance / Dismissed.
"""
from typing import Dict, List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.academic import AcademicStanding
from models.course import Course, Section
from models.enrollment import GRADE_POINTS, Enrollment, Grade
from models.student import Student
from services.gpa_calculator import get_cgpa_components, required_grades_for_target


TARGET_RECOVERY_CGPA = 2.0
FAILING_PERCENTAGE_THRESHOLD = 60.0
RETAKEABLE_GRADES = {"F", "FW", "D", "D+", "C-"}
_ENROLLED_STATUSES = ("Enrolled", "Satisfied")


async def _latest_standing(
    student_code: str, db: AsyncSession
) -> Optional[AcademicStanding]:
    row = await db.execute(
        select(AcademicStanding)
        .where(AcademicStanding.student_code == student_code)
        .order_by(AcademicStanding.semester_id.desc())
        .limit(1)
    )
    return row.scalar_one_or_none()


async def build_recovery_plan(student_id: int, db: AsyncSession) -> Dict:
    student = await db.get(Student, student_id)
    if not student:
        return {
            "severity": "none",
            "current_cgpa": 0.0,
            "target_cgpa": TARGET_RECOVERY_CGPA,
            "probation_semesters": 0,
            "at_risk_courses": [],
            "drop_candidates": [],
            "retake_candidates": [],
            "grades_needed": None,
            "recommended_actions": ["Student record not found."],
        }

    standing = await _latest_standing(student.student_code, db)
    cgpa = (
        float(standing.cgpa)
        if standing and standing.cgpa is not None
        else float(student.cgpa or 0.0)
    )

    at_risk = await _current_at_risk_courses(student_id, db)
    retake_candidates = await _retake_candidates(student_id, db)
    grades_needed = await _grades_needed_for_recovery(student_id, db)

    severity = _severity(standing)
    drop_candidates = [c for c in at_risk if c["flagged"]]

    return {
        "severity": severity,
        "current_cgpa": round(cgpa, 3),
        "target_cgpa": TARGET_RECOVERY_CGPA,
        "probation_semesters": standing.probation_semesters if standing else 0,
        "at_risk_courses": at_risk,
        "drop_candidates": drop_candidates,
        "retake_candidates": retake_candidates,
        "grades_needed": grades_needed,
        "recommended_actions": _recommended_actions(
            severity, drop_candidates, retake_candidates, grades_needed
        ),
    }


def render_plan_summary(plan: Dict) -> str:
    lines = [
        f"Severity: {plan['severity']}",
        f"CGPA: {plan['current_cgpa']} (target {plan['target_cgpa']})",
        f"Probation semesters: {plan['probation_semesters']}",
    ]
    if plan["drop_candidates"]:
        lines.append("Courses failing this semester (<60%):")
        for c in plan["drop_candidates"]:
            pct = c["current_percentage"]
            lines.append(
                f"  - {c['course_code']} {c['course_title']} "
                f"({'pct ' + str(pct) if pct is not None else 'no grade yet'})"
            )
    if plan["retake_candidates"]:
        lines.append("Top retake candidates (prior grade → up to +4.0 per credit):")
        for c in plan["retake_candidates"][:3]:
            lines.append(
                f"  - {c['course_code']} (prior {c['prior_grade']}, {c['credits']}cr, ceiling +{c['improvement_ceiling']})"
            )
    gn = plan["grades_needed"] or {}
    if gn.get("feasible"):
        lines.append(
            f"Minimum grade per enrolled course to reach {plan['target_cgpa']}: "
            f"{gn.get('minimum_letter_per_course')} "
            f"(avg {gn.get('avg_grade_points_needed')} points needed)."
        )
    elif gn:
        lines.append(
            f"Reaching CGPA {plan['target_cgpa']} this semester is not feasible with current load."
        )
    lines.append("Recommended actions:")
    for a in plan["recommended_actions"]:
        lines.append(f"  - {a}")
    return "\n".join(lines)


def _severity(standing) -> str:
    if not standing:
        return "none"
    status = (standing.status or "").strip()
    if status in ("Dismissed", "Final Chance"):
        return "critical"
    if status in ("Probation", "Warning"):
        return "warning"
    if status == "Good Standing":
        return "none"
    try:
        if float(standing.cgpa) < TARGET_RECOVERY_CGPA:
            return "warning"
    except (TypeError, ValueError):
        pass
    return "none"


async def _current_at_risk_courses(
    student_id: int, db: AsyncSession
) -> List[Dict]:
    """Courses the student is actively enrolled in, flagged if their running
    percentage is below the failing threshold. Rows without a Grade yet are
    returned unflagged so advisors can still see the full load."""
    rows = (
        await db.execute(
            select(Enrollment, Section, Course, Grade)
            .join(Section, Section.section_id == Enrollment.section_id)
            .join(Course, Course.code == Section.course_code)
            .join(Grade, Grade.enrollment_id == Enrollment.enrollment_id, isouter=True)
            .where(
                and_(
                    Enrollment.student_id == student_id,
                    Enrollment.status == "Enrolled",
                )
            )
        )
    ).all()

    out: List[Dict] = []
    for enrollment, section, course, grade in rows:
        pct = (
            float(grade.percentage)
            if grade and grade.percentage is not None
            else None
        )
        letter = grade.grade_letter if grade else None
        pts = grade.grade_points if grade and grade.grade_points is not None else None
        flagged = (
            (pct is not None and pct < FAILING_PERCENTAGE_THRESHOLD)
            or (letter in {"F", "FW"})
            or (pts is not None and pts < 1.0)
        )
        out.append(
            {
                "enrollment_id": enrollment.enrollment_id,
                "section_id": section.section_id,
                "course_code": course.code,
                "course_title": course.name,
                "credits": course.credits,
                "current_percentage": pct,
                "current_letter": letter,
                "current_grade_points": pts,
                "flagged": flagged,
            }
        )
    return out


async def _retake_candidates(
    student_id: int, db: AsyncSession
) -> List[Dict]:
    """Prior graded courses (any semester) with a retakeable letter.
    Deduplicated by course_code, keeping the worst prior attempt."""
    rows = (
        await db.execute(
            select(Enrollment, Grade, Section, Course)
            .join(Grade, Grade.enrollment_id == Enrollment.enrollment_id)
            .join(Section, Section.section_id == Enrollment.section_id)
            .join(Course, Course.code == Section.course_code)
            .where(
                and_(
                    Enrollment.student_id == student_id,
                    Grade.grade_letter.in_(list(RETAKEABLE_GRADES)),
                )
            )
        )
    ).all()

    by_code: Dict[str, Dict] = {}
    for enrollment, grade, section, course in rows:
        prior_pts = (
            float(grade.grade_points)
            if grade.grade_points is not None
            else GRADE_POINTS.get(grade.grade_letter) or 0.0
        )
        entry = {
            "course_code": course.code,
            "course_title": course.name,
            "credits": course.credits,
            "prior_grade": grade.grade_letter,
            "prior_grade_points": prior_pts,
            "improvement_ceiling": round(4.0 - prior_pts, 2),
        }
        existing = by_code.get(course.code)
        if existing is None or prior_pts < existing["prior_grade_points"]:
            by_code[course.code] = entry

    out = list(by_code.values())
    out.sort(key=lambda x: x["improvement_ceiling"], reverse=True)
    return out[:6]


async def _grades_needed_for_recovery(
    student_id: int, db: AsyncSession
) -> Dict:
    enrolled_course_codes = [
        row[0]
        for row in (
            await db.execute(
                select(Section.course_code)
                .join(Enrollment, Enrollment.section_id == Section.section_id)
                .where(
                    and_(
                        Enrollment.student_id == student_id,
                        Enrollment.status == "Enrolled",
                    )
                )
            )
        ).all()
    ]

    base_points, base_credits = await get_cgpa_components(student_id, db)
    if not enrolled_course_codes:
        return {
            "target_cgpa": TARGET_RECOVERY_CGPA,
            "feasible": False,
            "reason": "No courses currently enrolled — register first to build a recovery plan.",
            "current_cgpa": round(base_points / base_credits, 3) if base_credits else 0.0,
        }

    return await required_grades_for_target(
        student_id=student_id,
        target_cgpa=TARGET_RECOVERY_CGPA,
        course_codes=enrolled_course_codes,
        db=db,
    )


def _recommended_actions(
    severity: str,
    drop_candidates: List[Dict],
    retake_candidates: List[Dict],
    grades_needed: Optional[Dict],
) -> List[str]:
    actions: List[str] = []
    if severity == "critical":
        actions.append(
            "Meet your advisor immediately — you are one semester away from dismissal."
        )
    if drop_candidates:
        codes = ", ".join(c["course_code"] for c in drop_candidates)
        actions.append(
            f"Drop these courses before the deadline — performance is below 60%: {codes}."
        )
    if retake_candidates:
        top = retake_candidates[0]
        actions.append(
            f"Retake {top['course_code']} (prior {top['prior_grade']}) — "
            f"grade-replacement can raise CGPA by up to {top['improvement_ceiling']} per credit."
        )
    if grades_needed and grades_needed.get("feasible"):
        actions.append(
            f"Aim for at least {grades_needed['minimum_letter_per_course']} in every "
            f"enrolled course to reach a {grades_needed['target_cgpa']} CGPA."
        )
    elif grades_needed and grades_needed.get("feasible") is False:
        actions.append(
            "Your current enrolled load cannot reach CGPA 2.0 this semester — "
            "focus on retakes and petition to extend your recovery window."
        )
    if not actions:
        actions.append("You are not currently at academic risk — no emergency actions required.")
    return actions
