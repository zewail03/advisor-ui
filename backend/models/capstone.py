"""Field Training (§19) and Graduation Project (§20).

Eligibility gates (completed-credit %):
  * Field Training A : 60%
  * Field Training B : 75%
  * Graduation Project I : 80%
  * Graduation Project II : 90%
"""
import enum
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text, Enum, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


def _uuid() -> str:
    return str(uuid4())


FIELD_TRAINING_A_PCT = 60.0
FIELD_TRAINING_B_PCT = 75.0
GRAD_PROJECT_I_PCT = 80.0
GRAD_PROJECT_II_PCT = 90.0


class CapstoneStage(str, enum.Enum):
    field_training_a = "field_training_a"
    field_training_b = "field_training_b"
    graduation_project_i = "graduation_project_i"
    graduation_project_ii = "graduation_project_ii"


class CapstoneStatus(str, enum.Enum):
    not_started = "not_started"
    in_progress = "in_progress"
    submitted = "submitted"
    passed = "passed"
    failed = "failed"


STAGE_THRESHOLDS: dict[CapstoneStage, float] = {
    CapstoneStage.field_training_a: FIELD_TRAINING_A_PCT,
    CapstoneStage.field_training_b: FIELD_TRAINING_B_PCT,
    CapstoneStage.graduation_project_i: GRAD_PROJECT_I_PCT,
    CapstoneStage.graduation_project_ii: GRAD_PROJECT_II_PCT,
}


class CapstoneEnrollment(Base):
    """One row per student × stage."""

    __tablename__ = "capstone_enrollments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("students.student_id", ondelete="CASCADE"), index=True
    )
    stage: Mapped[CapstoneStage] = mapped_column(Enum(CapstoneStage), nullable=False)
    semester_code: Mapped[str] = mapped_column(String(30), index=True, nullable=False)
    status: Mapped[CapstoneStatus] = mapped_column(
        Enum(CapstoneStatus), default=CapstoneStatus.in_progress
    )
    supervisor_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    supervisor_email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    abstract: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    company_or_lab: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    hours_logged: Mapped[float] = mapped_column(Float, default=0.0)
    grade_letter: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    grade_points: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    final_report_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("student_id", "stage", name="uq_student_capstone_stage"),
    )


class CapstoneMilestone(Base):
    """Checkpoints inside a capstone stage (proposal, mid-review, defense…)."""

    __tablename__ = "capstone_milestones"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    capstone_enrollment_id: Mapped[str] = mapped_column(
        String, ForeignKey("capstone_enrollments.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
