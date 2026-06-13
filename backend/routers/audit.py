"""Audit-log viewer (§30). Intended for admin/registrar UIs."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_staff, get_current_student
from models.audit import AuditLog
from models.staff import Staff
from models.student import Student

router = APIRouter()


@router.get("/me")
async def my_audit_trail(
    limit: int = Query(100, le=500),
    action: Optional[str] = None,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AuditLog).where(AuditLog.subject_student_id == str(student.student_id))
    if action:
        stmt = stmt.where(AuditLog.action == action)
    stmt = stmt.order_by(AuditLog.occurred_at.desc()).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return {
        "events": [
            {
                "id": r.id,
                "occurred_at": r.occurred_at.isoformat(),
                "action": r.action,
                "entity_type": r.entity_type,
                "entity_id": r.entity_id,
                "actor_id": r.actor_id,
                "actor_role": r.actor_role,
                "before": r.before_json,
                "after": r.after_json,
            }
            for r in rows
        ]
    }


@router.get("/admin")
async def admin_audit(
    limit: int = Query(200, le=1000),
    action: Optional[str] = None,
    entity_type: Optional[str] = None,
    subject_student_id: Optional[str] = None,
    staff: Staff = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if subject_student_id:
        stmt = stmt.where(AuditLog.subject_student_id == subject_student_id)
    stmt = stmt.order_by(AuditLog.occurred_at.desc()).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return {
        "events": [
            {
                "id": r.id,
                "occurred_at": r.occurred_at.isoformat(),
                "action": r.action,
                "entity_type": r.entity_type,
                "entity_id": r.entity_id,
                "actor_id": r.actor_id,
                "actor_role": r.actor_role,
                "subject_student_id": r.subject_student_id,
                "before": r.before_json,
                "after": r.after_json,
                "metadata": r.metadata_json,
            }
            for r in rows
        ]
    }
