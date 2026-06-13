"""Retake endpoints (§10)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_student
from models.retake import RetakeRecord
from models.student import Student
from services.retake_service import check_retake_eligibility, record_retake_result

router = APIRouter()


@router.get("/eligibility/{section_id}")
async def eligibility(
    section_id: int,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    ok, msg, ctx = await check_retake_eligibility(student.student_id, section_id, db)
    return {"eligible": ok, "message": msg, **ctx}


@router.get("/me")
async def my_retakes(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(RetakeRecord)
            .where(RetakeRecord.student_id == student.student_id)
            .order_by(RetakeRecord.created_at.desc())
        )
    ).scalars().all()
    return {
        "records": [
            {
                "id": r.id,
                "course_id": r.course_id,
                "original_letter": r.original_letter,
                "new_letter": r.new_letter,
                "capped_points": r.capped_points,
                "effective_points": r.effective_points,
                "is_after_fail": r.is_after_fail,
                "is_improvement": r.is_improvement,
                "was_summer": r.was_summer,
                "credit_hours": r.credit_hours,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    }


@router.post("/finalize/{retake_enrollment_id}")
async def finalize(
    retake_enrollment_id: int,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Called after the grade is posted for a retake enrollment.
    Applies the B+ cap (fail-retake) and records the effective points used
    for CGPA. Idempotent in practice via unique course+enrollment pairs."""
    result = await record_retake_result(student.student_id, retake_enrollment_id, db)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "Failed"))
    return result
