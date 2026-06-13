"""Advisor assignment + approval workflow (§4).

Aligned to the real AIU schema:
  * advisor_assignments links to a student by ``student_code`` (not id).
  * approvals are stored in ``advisor_approvals`` keyed by integer student_id.
"""
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.advisor import (
    Advisor,
    AdvisorApproval,
    AdvisorAssignment,
    ApprovalStatus,
    ApprovalType,
)
from services.audit_service import log_action


async def get_student_advisor(student_code: str, db: AsyncSession) -> Optional[Advisor]:
    """Return the active advisor for a student, resolved via student_code."""
    return (
        await db.execute(
            select(Advisor)
            .join(AdvisorAssignment, AdvisorAssignment.advisor_id == Advisor.advisor_id)
            .where(AdvisorAssignment.student_code == student_code)
            .where(AdvisorAssignment.is_active == True)  # noqa: E712
        )
    ).scalars().first()


async def create_approval_request(
    student_id: int,
    student_code: str,
    approval_type: ApprovalType,
    db: AsyncSession,
    related_id: Optional[str] = None,
    semester_code: Optional[str] = None,
    justification: Optional[str] = None,
    payload_json: Optional[str] = None,
) -> AdvisorApproval:
    advisor = await get_student_advisor(student_code, db)
    approval = AdvisorApproval(
        student_id=student_id,
        advisor_id=advisor.advisor_id if advisor else None,
        type=approval_type.value,
        status=ApprovalStatus.pending.value,
        related_id=related_id,
        semester_code=semester_code,
        justification=justification,
        payload_json=payload_json,
    )
    db.add(approval)
    await db.commit()
    await db.refresh(approval)
    return approval


async def has_approval(
    student_id: int,
    approval_type: ApprovalType,
    db: AsyncSession,
    related_id: Optional[str] = None,
    semester_code: Optional[str] = None,
) -> bool:
    stmt = select(AdvisorApproval).where(
        AdvisorApproval.student_id == student_id,
        AdvisorApproval.type == approval_type.value,
        AdvisorApproval.status == ApprovalStatus.approved.value,
    )
    if related_id is not None:
        stmt = stmt.where(AdvisorApproval.related_id == related_id)
    if semester_code is not None:
        stmt = stmt.where(AdvisorApproval.semester_code == semester_code)
    return (await db.execute(stmt)).scalar_one_or_none() is not None


async def decide_approval(
    approval_id: str,
    advisor_id: int,
    approve: bool,
    comment: Optional[str],
    db: AsyncSession,
) -> Tuple[bool, str, Optional[AdvisorApproval]]:
    approval = await db.get(AdvisorApproval, approval_id)
    if not approval:
        return False, "Approval not found", None
    if approval.status != ApprovalStatus.pending.value:
        return False, f"Approval already {approval.status}", approval
    before = {"status": approval.status, "advisor_id": approval.advisor_id}
    approval.advisor_id = advisor_id
    approval.status = ApprovalStatus.approved.value if approve else ApprovalStatus.rejected.value
    approval.advisor_comment = comment
    approval.resolved_at = datetime.utcnow()
    await log_action(
        db,
        action="advisor.decide",
        entity_type="advisor_approval",
        entity_id=approval.id,
        actor_id=str(advisor_id),
        actor_role="advisor",
        subject_student_id=str(approval.student_id),
        before=before,
        after={"status": approval.status, "advisor_id": approval.advisor_id},
    )
    await db.commit()
    await db.refresh(approval)
    return True, "OK", approval


async def list_approvals_for_student(
    student_id: int, db: AsyncSession, limit: int = 50
) -> List[AdvisorApproval]:
    rows = (
        await db.execute(
            select(AdvisorApproval)
            .where(AdvisorApproval.student_id == student_id)
            .order_by(AdvisorApproval.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    return list(rows)


async def list_approvals_for_advisor(
    advisor_id: int,
    db: AsyncSession,
    status_: Optional[ApprovalStatus] = ApprovalStatus.pending,
    limit: int = 100,
) -> List[AdvisorApproval]:
    stmt = select(AdvisorApproval).where(AdvisorApproval.advisor_id == advisor_id)
    if status_ is not None:
        stmt = stmt.where(AdvisorApproval.status == status_.value)
    stmt = stmt.order_by(AdvisorApproval.created_at.desc()).limit(limit)
    return list((await db.execute(stmt)).scalars().all())
