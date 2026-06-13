"""Admin approval queues — petitions and advisor-approval requests.

The deciding staff member's identity comes from their token (never a query
param), writes are role-guarded, and every decision is audited.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_staff, require_role
from models.advisor import AdvisorApproval, ApprovalStatus
from models.petitions import Petition, PetitionStatus
from models.staff import Staff, StaffRole
from models.student import Student
from services.audit_service import log_action

router = APIRouter()


class Decision(BaseModel):
    approve: bool
    comment: Optional[str] = None


# ------------------------------- petitions ------------------------------- #

@router.get("/petitions")
async def list_petitions(
    status: str = Query("submitted"),
    staff: Staff = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Petition, Student.full_name, Student.student_code).join(
        Student, Student.student_id == Petition.student_id
    )
    if status and status != "all":
        stmt = stmt.where(Petition.status == status)
    stmt = stmt.order_by(Petition.submitted_at.desc()).limit(200)
    rows = (await db.execute(stmt)).all()
    return {
        "petitions": [
            {
                "id": p.id,
                "student_id": p.student_id,
                "student_name": name,
                "student_code": code,
                "type": p.type.value if hasattr(p.type, "value") else p.type,
                "status": p.status.value if hasattr(p.status, "value") else p.status,
                "subject": p.subject,
                "body": p.body,
                "semester_code": p.freeze_semester_code,
                "current_grade": p.current_grade,
                "requested_grade": p.requested_grade,
                "decision_comment": p.decision_comment,
                "created_at": p.submitted_at.isoformat() if p.submitted_at else None,
            }
            for (p, name, code) in rows
        ]
    }


@router.patch("/petitions/{petition_id}")
async def decide_petition(
    petition_id: str,
    body: Decision,
    staff: Staff = Depends(require_role(StaffRole.registrar)),
    db: AsyncSession = Depends(get_db),
):
    p = await db.get(Petition, petition_id)
    if not p:
        raise HTTPException(status_code=404, detail="Petition not found")
    current = p.status.value if hasattr(p.status, "value") else p.status
    if current in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail=f"Petition already {current}")

    new_status = PetitionStatus.approved if body.approve else PetitionStatus.rejected
    p.status = new_status
    p.reviewer_id = str(staff.staff_id)
    p.reviewer_role = staff.role
    p.decision_comment = body.comment
    p.decided_at = datetime.utcnow()

    await log_action(
        db, action=f"petition.{new_status.value}", entity_type="petition",
        entity_id=p.id, actor_id=str(staff.staff_id), actor_role=staff.role,
        subject_student_id=str(p.student_id),
        before={"status": current}, after={"status": new_status.value, "comment": body.comment},
    )
    await db.commit()
    return {"decided": True, "status": new_status.value}


# --------------------------- advisor approvals --------------------------- #

@router.get("/advisor-approvals")
async def list_advisor_approvals(
    status: str = Query("pending"),
    staff: Staff = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AdvisorApproval, Student.full_name, Student.student_code).join(
        Student, Student.student_id == AdvisorApproval.student_id
    )
    if status and status != "all":
        stmt = stmt.where(AdvisorApproval.status == status)
    stmt = stmt.order_by(AdvisorApproval.created_at.desc()).limit(200)
    rows = (await db.execute(stmt)).all()
    return {
        "approvals": [
            {
                "id": a.id,
                "student_id": a.student_id,
                "student_name": name,
                "student_code": code,
                "type": a.type,
                "status": a.status,
                "semester_code": a.semester_code,
                "justification": a.justification,
                "advisor_comment": a.advisor_comment,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for (a, name, code) in rows
        ]
    }


@router.patch("/advisor-approvals/{approval_id}")
async def decide_advisor_approval(
    approval_id: str,
    body: Decision,
    staff: Staff = Depends(require_role(StaffRole.registrar)),
    db: AsyncSession = Depends(get_db),
):
    a = await db.get(AdvisorApproval, approval_id)
    if not a:
        raise HTTPException(status_code=404, detail="Approval not found")
    if a.status in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail=f"Already {a.status}")

    new_status = ApprovalStatus.approved.value if body.approve else ApprovalStatus.rejected.value
    before = {"status": a.status}
    a.status = new_status
    a.advisor_comment = body.comment
    a.resolved_at = datetime.utcnow()

    await log_action(
        db, action=f"advisor_approval.{new_status}", entity_type="advisor_approval",
        entity_id=a.id, actor_id=str(staff.staff_id), actor_role=staff.role,
        subject_student_id=str(a.student_id),
        before=before, after={"status": new_status, "comment": body.comment},
    )
    await db.commit()
    return {"decided": True, "status": new_status}
