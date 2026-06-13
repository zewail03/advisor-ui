"""Attendance tracking (§7).

Warnings escalate at 10% / 15% / 25% absence. At 25% the student receives
a Force Withdrawal (FW) grade for the course automatically.
"""
import enum
from datetime import datetime, date
from typing import Optional
from uuid import uuid4

from sqlalchemy import String, Integer, Float, Boolean, DateTime, Date, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


def _uuid() -> str:
    return str(uuid4())


class AttendanceStatus(str, enum.Enum):
    present = "present"
    absent = "absent"
    excused = "excused"
    late = "late"


class ContactType(str, enum.Enum):
    lecture = "lecture"
    tutorial = "tutorial"
    lab = "lab"


WARNING_LEVELS = (10.0, 15.0, 25.0)  # percent
FW_THRESHOLD_PCT = 25.0


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    enrollment_id: Mapped[str] = mapped_column(String, index=True)
    session_date: Mapped[date] = mapped_column(Date, nullable=False)
    contact_type: Mapped[ContactType] = mapped_column(Enum(ContactType), default=ContactType.lecture)
    duration_hours: Mapped[float] = mapped_column(Float, default=1.0)
    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus), default=AttendanceStatus.present
    )
    recorded_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "enrollment_id", "session_date", "contact_type",
            name="uq_enrollment_session",
        ),
    )


class AttendanceSummary(Base):
    __tablename__ = "attendance_summaries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    enrollment_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    total_hours: Mapped[float] = mapped_column(Float, default=0.0)
    absent_hours: Mapped[float] = mapped_column(Float, default=0.0)
    excused_hours: Mapped[float] = mapped_column(Float, default=0.0)
    absence_pct: Mapped[float] = mapped_column(Float, default=0.0)
    last_warning_level: Mapped[float] = mapped_column(Float, default=0.0)
    fw_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
