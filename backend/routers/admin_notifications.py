"""Admin notifications — send an announcement to one student or all students.

Rows land in the same `notifications` table the student portal's bell reads,
so recipients see them immediately. Sending is role-guarded and audited.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_staff, require_role
from models.ai_models import Notification
from models.staff import Staff, StaffRole
from models.student import Student
from services.audit_service import log_action

router = APIRouter()


class SendNotification(BaseModel):
    subject: str
    message: str
    type: str = "Announcement"
    target: str  # "all" | "student"
    student_code: Optional[str] = None


@router.post("/notifications/send")
async def send_notification(
    body: SendNotification,
    staff: Staff = Depends(require_role(StaffRole.registrar)),
    db: AsyncSession = Depends(get_db),
):
    if not body.subject.strip() or not body.message.strip():
        raise HTTPException(status_code=400, detail="Subject and message are required")

    now = datetime.utcnow()

    if body.target == "student":
        if not body.student_code:
            raise HTTPException(status_code=400, detail="student_code is required for a single send")
        student = (
            await db.execute(select(Student).where(Student.student_code == body.student_code.strip()))
        ).scalar_one_or_none()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        db.add(Notification(
            student_id=student.student_id, type=body.type, subject=body.subject,
            message=body.message, status="Unread", created_at=now,
        ))
        await log_action(
            db, action="notification.send", entity_type="notification",
            actor_id=str(staff.staff_id), actor_role=staff.role,
            subject_student_id=str(student.student_id),
            after={"subject": body.subject, "to": student.student_code},
        )
        await db.commit()
        return {"sent": 1, "recipients": student.full_name}

    if body.target == "all":
        ids = (await db.execute(select(Student.student_id))).scalars().all()
        rows = [
            {"student_id": sid, "type": body.type, "subject": body.subject,
             "message": body.message, "status": "Unread", "created_at": now}
            for sid in ids
        ]
        if rows:
            await db.execute(insert(Notification), rows)
        await log_action(
            db, action="notification.broadcast", entity_type="notification",
            actor_id=str(staff.staff_id), actor_role=staff.role,
            after={"subject": body.subject, "recipients": len(rows)},
        )
        await db.commit()
        return {"sent": len(rows), "recipients": "all students"}

    raise HTTPException(status_code=400, detail="target must be 'all' or 'student'")


@router.get("/notifications/recent")
async def recent_broadcasts(
    staff: Staff = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    """Most recent distinct announcements (subject + count), for an at-a-glance log."""
    rows = (
        await db.execute(
            select(
                Notification.subject,
                Notification.type,
                func.count().label("recipients"),
                func.max(Notification.created_at).label("sent_at"),
            )
            .where(Notification.type == "Announcement")
            .group_by(Notification.subject, Notification.type)
            .order_by(func.max(Notification.created_at).desc())
            .limit(15)
        )
    ).all()
    return {
        "announcements": [
            {"subject": s, "type": t, "recipients": int(n), "sent_at": sent.isoformat() if sent else None}
            for (s, t, n, sent) in rows
        ]
    }
