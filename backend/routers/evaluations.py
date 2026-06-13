"""Course evaluation endpoints (§31).

Self-contained: "pending" is derived from the student's REAL in-progress
enrollments (courses they can evaluate). Submissions land in course_evaluations.
"""
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_student
from models.course import Section
from models.enrollment import Enrollment
from models.evaluation import CourseEvaluation
from models.student import Student
from schemas.evaluation import EvaluationSubmit

router = APIRouter()

_RATING_FIELDS = (
    "rating_content", "rating_teaching", "rating_materials",
    "rating_assessment", "rating_engagement", "rating_overall",
)


@router.get("/me/pending")
async def my_pending(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    # courses the student is actively enrolled in (can evaluate at term end)
    rows = (
        await db.execute(
            select(
                Enrollment.enrollment_id,
                Section.course_code,
                Section.instructor_name,
                Section.section_id,
            )
            .join(Section, Section.section_id == Enrollment.section_id)
            .where(Enrollment.student_id == student.student_id)
            .where(Enrollment.status == "Enrolled")
        )
    ).all()

    # exclude any already evaluated by this student
    done = {
        r[0]
        for r in (
            await db.execute(
                select(CourseEvaluation.enrollment_id).where(
                    CourseEvaluation.student_id == student.student_id
                )
            )
        ).all()
    }

    pending = [
        {
            "enrollment_id": str(eid),
            "course_id": code,
            "semester_code": "Spring 2026",
            "instructor": instr,
            "section_id": str(sec),
        }
        for (eid, code, instr, sec) in rows
        if str(eid) not in done
    ]
    return {"pending": pending}


@router.post("")
async def submit(
    req: EvaluationSubmit,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    existing = (
        await db.execute(
            select(CourseEvaluation).where(
                CourseEvaluation.enrollment_id == str(req.enrollment_id),
                CourseEvaluation.student_id == student.student_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="You already evaluated this course")

    ev = CourseEvaluation(
        id=str(uuid4()),
        enrollment_id=str(req.enrollment_id),
        student_id=student.student_id,
        section_id="",
        course_id="",
        semester_code="",
        rating_content=req.rating_content,
        rating_teaching=req.rating_teaching,
        rating_materials=req.rating_materials,
        rating_assessment=req.rating_assessment,
        rating_engagement=req.rating_engagement,
        rating_overall=req.rating_overall,
        best_aspect=req.best_aspect,
        improvement_note=req.improvement_note,
        anonymous=req.anonymous,
        submitted_at=datetime.utcnow(),
    )
    db.add(ev)
    await db.commit()
    return {"success": True, "message": "Evaluation submitted. Thank you for your feedback."}


@router.get("/sections/{section_id}")
async def section_summary(
    section_id: str,
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(CourseEvaluation).where(CourseEvaluation.section_id == section_id)
        )
    ).scalars().all()
    if not rows:
        raise HTTPException(status_code=404, detail="No evaluations yet")
    n = len(rows)
    return {
        "section_id": section_id,
        "respondents": n,
        **{f: round(sum(getattr(r, f) for r in rows) / n, 2) for f in _RATING_FIELDS},
    }
