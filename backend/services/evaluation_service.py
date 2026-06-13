"""Course-evaluation submission + aggregation (§31)."""
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.course import Section
from models.enrollment import Enrollment
from models.evaluation import (
    CourseEvaluation,
    CourseEvaluationSummary,
    LIKERT_FIELDS,
)


def _clamp(value: int) -> int:
    return max(1, min(5, int(value)))


async def submit_evaluation(
    student_id: str,
    enrollment_id: str,
    ratings: Dict[str, int],
    db: AsyncSession,
    best_aspect: Optional[str] = None,
    improvement_note: Optional[str] = None,
    anonymous: bool = True,
) -> Dict:
    enrollment = await db.get(Enrollment, enrollment_id)
    if not enrollment or enrollment.student_id != student_id:
        return {"success": False, "message": "Enrollment not found"}

    existing = (
        await db.execute(
            select(CourseEvaluation).where(
                CourseEvaluation.enrollment_id == enrollment_id
            )
        )
    ).scalar_one_or_none()
    if existing:
        return {"success": False, "message": "Already submitted for this enrollment"}

    section = await db.get(Section, enrollment.section_id)
    if not section:
        return {"success": False, "message": "Section missing"}

    row = CourseEvaluation(
        enrollment_id=enrollment_id,
        student_id=student_id,
        section_id=section.id,
        course_id=section.course_id,
        semester_code=enrollment.semester_code,
        best_aspect=best_aspect,
        improvement_note=improvement_note,
        anonymous=anonymous,
    )
    for field in LIKERT_FIELDS:
        setattr(row, field, _clamp(ratings.get(field, 0) or 0))
    db.add(row)
    await db.flush()

    await _recompute_summary(section.id, enrollment.semester_code, db)
    await db.commit()
    return {"success": True, "evaluation_id": row.id}


async def _recompute_summary(
    section_id: str, semester_code: str, db: AsyncSession
) -> None:
    agg_stmt = (
        select(
            func.count(CourseEvaluation.id),
            *(func.avg(getattr(CourseEvaluation, f)) for f in LIKERT_FIELDS),
        )
        .where(CourseEvaluation.section_id == section_id)
        .where(CourseEvaluation.semester_code == semester_code)
    )
    row = (await db.execute(agg_stmt)).one()
    count = row[0] or 0
    avgs = [float(v) if v is not None else 0.0 for v in row[1:]]

    summary = (
        await db.execute(
            select(CourseEvaluationSummary)
            .where(CourseEvaluationSummary.section_id == section_id)
            .where(CourseEvaluationSummary.semester_code == semester_code)
        )
    ).scalar_one_or_none()

    section = await db.get(Section, section_id)
    if not summary:
        summary = CourseEvaluationSummary(
            section_id=section_id,
            course_id=section.course_id if section else None,
            semester_code=semester_code,
        )
        db.add(summary)

    summary.respondents = count
    (
        summary.avg_content,
        summary.avg_teaching,
        summary.avg_materials,
        summary.avg_assessment,
        summary.avg_engagement,
        summary.avg_overall,
    ) = avgs
    summary.last_updated = datetime.utcnow()


async def pending_for_student(student_id: str, db: AsyncSession):
    """Return enrollments eligible for evaluation that haven't been completed."""
    enrollments = (
        await db.execute(
            select(Enrollment).where(Enrollment.student_id == student_id)
        )
    ).scalars().all()
    out = []
    for e in enrollments:
        done = (
            await db.execute(
                select(CourseEvaluation).where(
                    CourseEvaluation.enrollment_id == e.id
                )
            )
        ).scalar_one_or_none()
        if done:
            continue
        section = await db.get(Section, e.section_id)
        if not section:
            continue
        out.append({
            "enrollment_id": e.id,
            "section_id": section.id,
            "course_id": section.course_id,
            "semester_code": e.semester_code,
            "instructor": section.instructor,
        })
    return out


async def course_summary(
    section_id: str, semester_code: str, db: AsyncSession
) -> Optional[Dict]:
    summary = (
        await db.execute(
            select(CourseEvaluationSummary)
            .where(CourseEvaluationSummary.section_id == section_id)
            .where(CourseEvaluationSummary.semester_code == semester_code)
        )
    ).scalar_one_or_none()
    if not summary:
        return None
    return {
        "section_id": section_id,
        "semester_code": semester_code,
        "respondents": summary.respondents,
        "avg_content": summary.avg_content,
        "avg_teaching": summary.avg_teaching,
        "avg_materials": summary.avg_materials,
        "avg_assessment": summary.avg_assessment,
        "avg_engagement": summary.avg_engagement,
        "avg_overall": summary.avg_overall,
        "last_updated": summary.last_updated.isoformat(),
    }
