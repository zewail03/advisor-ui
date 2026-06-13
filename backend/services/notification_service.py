from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from core.websocket import ws_manager
from models.ai_models import Notification


async def notify(
    student_id: int,
    title: str,
    message: str,
    db: AsyncSession,
    type: str = "info",
    link: Optional[str] = None,  # accepted for API compat; not stored
    push: bool = True,
) -> Notification:
    n = Notification(
        student_id=student_id,
        type=type,
        subject=title,
        message=message,
        status="Unread",
        created_at=datetime.utcnow(),
    )
    db.add(n)
    await db.commit()
    await db.refresh(n)
    if push:
        await ws_manager.send_to_student(
            str(student_id),
            {
                "type": "notification",
                "id": str(n.notification_id),
                "notif_type": n.type,
                "title": n.subject,
                "message": n.message,
                "link": link,
                "created_at": n.created_at.isoformat() if n.created_at else "",
            },
        )
    return n
