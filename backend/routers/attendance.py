"""Attendance endpoints (§7).

The AIU dataset carries no attendance records, so reads return an honest
empty state rather than fabricated data. Faculty can still POST records,
which then surface here.
"""
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_student
from models.attendance import AttendanceRecord, AttendanceStatus, ContactType
from models.enrollment import Enrollment
from models.student import Student

router = APIRouter()


@router.get("/me")
async def my_attendance(
    semester: Optional[str] = Query(None),
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    # enrollment ids belonging to this student
    enr_ids = [
        str(r[0])
        for r in (
            await db.execute(
                select(Enrollment.enrollment_id).where(
                    Enrollment.student_id == student.student_id
                )
            )
        ).all()
    ]
    records = []
    if enr_ids:
        rows = (
            await db.execute(
                select(AttendanceRecord).where(
                    AttendanceRecord.enrollment_id.in_(enr_ids)
                )
            )
        ).scalars().all()
        records = [
            {
                "id": r.id,
                "enrollment_id": r.enrollment_id,
                "session_date": r.session_date.isoformat() if r.session_date else None,
                "status": r.status.value if hasattr(r.status, "value") else r.status,
                "contact_type": r.contact_type.value if hasattr(r.contact_type, "value") else r.contact_type,
                "duration_hours": r.duration_hours,
            }
            for r in rows
        ]
    return {
        "records": records,
        "message": None if records else "No attendance has been recorded for your courses yet.",
    }


@router.post("")
async def post_attendance(
    enrollment_id: str,
    session_date: str,
    status: str,
    contact_type: str = "lecture",
    duration_hours: float = 1.0,
    db: AsyncSession = Depends(get_db),
):
    """Faculty posts an attendance record (role check kept minimal for now)."""
    try:
        status_enum = AttendanceStatus(status)
        contact_enum = ContactType(contact_type)
        sdate = datetime.fromisoformat(session_date).date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status, contact type, or date")

    rec = AttendanceRecord(
        id=str(uuid4()),
        enrollment_id=enrollment_id,
        session_date=sdate,
        status=status_enum,
        contact_type=contact_enum,
        duration_hours=duration_hours,
        created_at=datetime.utcnow(),
    )
    db.add(rec)
    await db.commit()
    return {"success": True, "id": rec.id}
