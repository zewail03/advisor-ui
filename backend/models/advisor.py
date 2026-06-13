from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlalchemy import String, Integer, Boolean, Text, Date, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


MAX_STUDENTS_PER_ADVISOR = 25


def _uuid() -> str:
    return str(uuid4())


class ApprovalType(str, Enum):
    registration = "registration"
    add = "add"
    drop = "drop"
    withdrawal = "withdrawal"
    load_adjustment = "load_adjustment"
    retake = "retake"
    freeze = "freeze"
    final_chance = "final_chance"


class ApprovalStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    cancelled = "cancelled"


class Advisor(Base):
    __tablename__ = "advisors"

    advisor_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    max_students: Mapped[int] = mapped_column(Integer, default=MAX_STUDENTS_PER_ADVISOR)
    specializations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array as text

    assignments = relationship("AdvisorAssignment", back_populates="advisor", cascade="all, delete-orphan")


class AdvisorAssignment(Base):
    __tablename__ = "advisor_assignments"

    advisor_assignment_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    advisor_id: Mapped[int] = mapped_column(Integer, ForeignKey("advisors.advisor_id", ondelete="CASCADE"), index=True)
    advisor_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    student_code: Mapped[str] = mapped_column(String(20), ForeignKey("students.student_code"), index=True)
    student_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    assigned_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    advisor = relationship("Advisor", back_populates="assignments")


class AdvisorApproval(Base):
    __tablename__ = "advisor_approvals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("students.student_id", ondelete="CASCADE"), index=True
    )
    advisor_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("advisors.advisor_id"), nullable=True
    )
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=ApprovalStatus.pending.value)
    related_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    semester_code: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    advisor_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
