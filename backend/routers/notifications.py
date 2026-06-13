from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_student
from models.ai_models import Notification
from models.student import Student

router = APIRouter()


def _is_read(n: Notification) -> bool:
    return (n.status or "").lower() == "read" or n.read_at is not None


def _serialize(n: Notification) -> dict:
    return {
        "id": str(n.notification_id),
        "type": n.type or "info",
        "title": n.subject or "Notification",
        "message": n.message,
        "link": None,
        "read": _is_read(n),
        "created_at": n.created_at.isoformat() if n.created_at else "",
    }


@router.get("")
async def list_notifications(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification)
        .where(Notification.student_id == student.student_id)
        .order_by(Notification.created_at.desc())
        .limit(100)
    )
    return [_serialize(n) for n in result.scalars().all()]


@router.patch("/{notification_id}/read")
async def mark_read(
    notification_id: str,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    try:
        nid = int(notification_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=404, detail="Notification not found")
    notif = await db.get(Notification, nid)
    if not notif or notif.student_id != student.student_id:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.status = "Read"
    notif.read_at = datetime.utcnow()
    await db.commit()
    return {"message": "marked as read"}


@router.post("/mark-all-read")
async def mark_all_read(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification).where(Notification.student_id == student.student_id)
    )
    now = datetime.utcnow()
    for n in result.scalars().all():
        if not _is_read(n):
            n.status = "Read"
            n.read_at = now
    await db.commit()
    return {"message": "all marked as read"}
