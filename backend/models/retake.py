"""Retake tracking (§10).

Rules enforced by services/retake_service.py (all caps live in the policy engine):
  * A retake after F is capped (default B+ / 3.3, `retake.cap_after_fail`);
    the LATEST grade replaces the F in CGPA (§10.1).
  * Improvement retakes (prior grade C- or higher) cap lifetime CH by program
    duration (§10.2): 9 CH for 4-year, 12 CH for 5-year programs
    (`retake.improvement_cap_4yr` / `_5yr`).
  * Within the cap the HIGHER attempt counts; beyond it ALL attempts are
    AVERAGED in the CGPA (§10.3).
  * Retakes must be of the SAME course as the original enrollment.
"""
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


def _uuid() -> str:
    return str(uuid4())


IMPROVEMENT_PRIOR_MIN_POINTS = 1.7  # C-


class RetakeRecord(Base):
    __tablename__ = "retake_records"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.student_id", ondelete="CASCADE"), index=True)
    course_id: Mapped[str] = mapped_column(String, index=True)

    original_enrollment_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    retake_enrollment_id: Mapped[str] = mapped_column(String, index=True)

    original_letter: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    original_points: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    credit_hours: Mapped[int] = mapped_column(Integer, default=0)

    is_improvement: Mapped[bool] = mapped_column(Boolean, default=False)
    is_after_fail: Mapped[bool] = mapped_column(Boolean, default=False)
    was_summer: Mapped[bool] = mapped_column(Boolean, default=False)

    new_letter: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    new_points: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    capped_points: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    effective_points: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
