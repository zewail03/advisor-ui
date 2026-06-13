"""Academic advisor endpoints (§4)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_staff, get_current_student, require_role
from models.advisor import AdvisorApproval, ApprovalStatus, ApprovalType
from models.staff import Staff, StaffRole
from models.student import Student
from schemas.advisor import ApprovalDecision, ApprovalRequest
from services.advisor_service import (
    create_approval_request,
    decide_approval,
    get_student_advisor,
    list_approvals_for_advisor,
    list_approvals_for_student,
)

router = APIRouter()


def _parse_type(raw: str) -> ApprovalType:
    try:
        return ApprovalType(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown approval type '{raw}'")


def _advisor_dict(a) -> dict:
    return {
        "id": str(a.advisor_id),
        "full_name": a.full_name,
        "email": a.email,
        "phone": a.phone,
        "department": a.department,
        "office": None,
        "specialization": a.specializations,
    }


def _approval_dict(a: AdvisorApproval) -> dict:
    return {
        "id": a.id,
        "student_id": a.student_id,
        "advisor_id": a.advisor_id,
        "type": a.type,
        "status": a.status,
        "related_id": a.related_id,
        "semester_code": a.semester_code,
        "justification": a.justification,
        "advisor_comment": a.advisor_comment,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
    }


@router.get("/me")
async def my_advisor(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    advisor = await get_student_advisor(student.student_code, db)
    return _advisor_dict(advisor) if advisor else None


@router.get("/me/approvals")
async def my_approvals(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    rows = await list_approvals_for_student(student.student_id, db)
    return [_approval_dict(r) for r in rows]


@router.post("/me/approvals")
async def request_approval(
    req: ApprovalRequest,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    approval = await create_approval_request(
        student_id=student.student_id,
        student_code=student.student_code,
        approval_type=_parse_type(req.type),
        db=db,
        related_id=req.related_id,
        semester_code=req.semester_code,
        justification=req.justification,
        payload_json=req.payload_json,
    )
    return _approval_dict(approval)


@router.get("/approvals/{approval_id}")
async def get_approval(
    approval_id: str,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    approval = await db.get(AdvisorApproval, approval_id)
    if not approval or approval.student_id != student.student_id:
        raise HTTPException(status_code=404, detail="Approval not found")
    return _approval_dict(approval)


# ---- advisor-facing endpoints (called by advisor-role UI) ---- #

@router.get("/advisor/{advisor_id}/approvals")
async def advisor_pending_list(
    advisor_id: int,
    status_: Optional[str] = Query("pending", alias="status"),
    staff: Staff = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    parsed: Optional[ApprovalStatus] = None
    if status_:
        try:
            parsed = ApprovalStatus(status_)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status")
    rows = await list_approvals_for_advisor(advisor_id, db, status_=parsed)
    return [_approval_dict(r) for r in rows]


@router.patch("/approvals/{approval_id}")
async def advisor_decide(
    approval_id: str,
    decision: ApprovalDecision,
    staff: Staff = Depends(require_role(StaffRole.registrar)),
    db: AsyncSession = Depends(get_db),
):
    ok, msg, approval = await decide_approval(
        approval_id=approval_id,
        advisor_id=staff.staff_id,
        approve=decision.approve,
        comment=decision.comment,
        db=db,
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return _approval_dict(approval)
