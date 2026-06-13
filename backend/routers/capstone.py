"""Field Training + Graduation Project endpoints (§19/§20)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_student
from models.capstone import CapstoneStage
from models.student import Student
from schemas.capstone import CapstoneEnrollRequest, FinalSubmission, MilestoneUpdate
from services.capstone_service import (
    check_eligibility,
    enroll_capstone,
    list_for_student,
    submit_final,
    update_milestone,
)

router = APIRouter()


def _parse_stage(raw: str) -> CapstoneStage:
    try:
        return CapstoneStage(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown capstone stage '{raw}'")


@router.get("/me")
async def my_capstone(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    return {"entries": await list_for_student(student.student_id, db)}


@router.get("/me/eligibility")
async def my_eligibility(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    out = {}
    for stage in CapstoneStage:
        ok, msg, info = await check_eligibility(student.student_id, stage, db)
        out[stage.value] = {"eligible": ok, "message": msg, **info}
    return out


@router.post("/me")
async def enroll(
    req: CapstoneEnrollRequest,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    result = await enroll_capstone(
        student_id=student.student_id,
        stage=_parse_stage(req.stage),
        semester_code=req.semester_code,
        db=db,
        supervisor_name=req.supervisor_name,
        supervisor_email=req.supervisor_email,
        title=req.title,
        company_or_lab=req.company_or_lab,
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.patch("/milestones/{milestone_id}")
async def patch_milestone(
    milestone_id: str,
    update: MilestoneUpdate,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    m = await update_milestone(
        milestone_id, db,
        completed=update.completed,
        score=update.score,
        notes=update.notes,
    )
    if not m:
        raise HTTPException(status_code=404, detail="Milestone not found")
    return {
        "id": m.id,
        "name": m.name,
        "completed": m.completed,
        "score": m.score,
        "notes": m.notes,
    }


@router.post("/{capstone_enrollment_id}/submit")
async def submit(
    capstone_enrollment_id: str,
    payload: FinalSubmission,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    row = await submit_final(
        capstone_enrollment_id,
        grade_letter=payload.grade_letter,
        grade_points=payload.grade_points,
        report_url=payload.report_url,
        db=db,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Capstone entry not found")
    if row.student_id != student.student_id:
        raise HTTPException(status_code=403, detail="Not your capstone entry")
    return {
        "id": row.id,
        "stage": row.stage.value,
        "status": row.status.value,
        "grade_letter": row.grade_letter,
        "grade_points": row.grade_points,
    }
