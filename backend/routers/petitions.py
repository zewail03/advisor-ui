"""Petition endpoints: Final Chance / Freeze / Transfer / Grade Appeal."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_staff, get_current_student, require_role
from models.petitions import Petition, PetitionStatus, PetitionType
from models.staff import Staff, StaffRole
from models.student import Student
from schemas.petitions import PetitionDecision, PetitionSubmit
from services.petition_service import (
    decide_petition,
    submit_petition,
    validate_eligibility,
)

router = APIRouter()


def _parse_type(raw: str) -> PetitionType:
    try:
        return PetitionType(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown petition type '{raw}'")


def _petition_dict(p: Petition) -> dict:
    return {
        "id": p.id,
        "student_id": p.student_id,
        "type": p.type.value if hasattr(p.type, "value") else p.type,
        "status": p.status.value if hasattr(p.status, "value") else p.status,
        "subject": p.subject,
        "body": p.body,
        "semester_code": p.freeze_semester_code,
        "current_grade": p.current_grade,
        "requested_grade": p.requested_grade,
        "advisor_comment": p.decision_comment,
        "created_at": p.submitted_at.isoformat() if p.submitted_at else None,
        "decided_at": p.decided_at.isoformat() if p.decided_at else None,
    }


@router.get("/me/eligibility")
async def my_eligibility(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    out = {}
    for t in PetitionType:
        ok, msg = await validate_eligibility(student.student_id, t, db)
        out[t.value] = {"eligible": ok, "message": msg}
    return out


@router.get("/me")
async def my_petitions(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(Petition)
            .where(Petition.student_id == student.student_id)
            .order_by(Petition.submitted_at.desc())
        )
    ).scalars().all()
    return [_petition_dict(p) for p in rows]


@router.post("/me")
async def submit(
    req: PetitionSubmit,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    result = await submit_petition(
        student_id=student.student_id,
        ptype=_parse_type(req.type),
        subject=req.subject,
        db=db,
        body=req.body,
        payload_json=req.payload_json,
        enrollment_id=req.enrollment_id,
        current_grade=req.current_grade,
        requested_grade=req.requested_grade,
        freeze_semester_code=req.freeze_semester_code,
        source_program_code=req.source_program_code,
        target_program_code=req.target_program_code,
    )
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


# --- reviewer side ---

@router.get("/review")
async def review_queue(
    status_: Optional[str] = Query("submitted", alias="status"),
    type_: Optional[str] = Query(None, alias="type"),
    staff: Staff = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Petition)
    if status_:
        try:
            stmt = stmt.where(Petition.status == PetitionStatus(status_))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status")
    if type_:
        stmt = stmt.where(Petition.type == _parse_type(type_))
    stmt = stmt.order_by(Petition.submitted_at.asc()).limit(200)
    rows = (await db.execute(stmt)).scalars().all()
    return [_petition_dict(p) for p in rows]


@router.patch("/{petition_id}")
async def decide(
    petition_id: str,
    decision: PetitionDecision,
    staff: Staff = Depends(require_role(StaffRole.registrar)),
    db: AsyncSession = Depends(get_db),
):
    ok, msg, petition = await decide_petition(
        petition_id=petition_id,
        reviewer_id=str(staff.staff_id),
        reviewer_role=decision.reviewer_role,
        approve=decision.approve,
        comment=decision.comment,
        db=db,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return _petition_dict(petition)
