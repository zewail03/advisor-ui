"""Course quality assurance (§31).

Students evaluate each course they're enrolled in at end of term along six
Likert (1-5) axes. Results aggregate into per-section and per-course scores
that the registrar uses for teaching-quality review.
"""
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import String, Integer, Float, DateTime, Boolean, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


def _uuid() -> str:
    return str(uuid4())


LIKERT_FIELDS = (
    "rating_content",
    "rating_teaching",
    "rating_materials",
    "rating_assessment",
    "rating_engagement",
    "rating_overall",
)


class CourseEvaluation(Base):
    __tablename__ = "course_evaluations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    enrollment_id: Mapped[str] = mapped_column(String, index=True)
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("students.student_id", ondelete="CASCADE"), index=True
    )
    section_id: Mapped[str] = mapped_column(String, index=True)
    course_id: Mapped[str] = mapped_column(String, index=True)
    semester_code: Mapped[str] = mapped_column(String(30), index=True, nullable=False)

    rating_content: Mapped[int] = mapped_column(Integer, default=0)
    rating_teaching: Mapped[int] = mapped_column(Integer, default=0)
    rating_materials: Mapped[int] = mapped_column(Integer, default=0)
    rating_assessment: Mapped[int] = mapped_column(Integer, default=0)
    rating_engagement: Mapped[int] = mapped_column(Integer, default=0)
    rating_overall: Mapped[int] = mapped_column(Integer, default=0)

    best_aspect: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    improvement_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    anonymous: Mapped[bool] = mapped_column(Boolean, default=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("enrollment_id", name="uq_enrollment_evaluation"),
    )


class CourseEvaluationSummary(Base):
    """Pre-aggregated per (section, semester) — re-computed when evaluations
    are submitted or by a registrar rollup task."""

    __tablename__ = "course_evaluation_summaries"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    section_id: Mapped[str] = mapped_column(String, index=True)
    course_id: Mapped[str] = mapped_column(String, index=True)
    semester_code: Mapped[str] = mapped_column(String(30), index=True, nullable=False)

    respondents: Mapped[int] = mapped_column(Integer, default=0)
    avg_content: Mapped[float] = mapped_column(Float, default=0.0)
    avg_teaching: Mapped[float] = mapped_column(Float, default=0.0)
    avg_materials: Mapped[float] = mapped_column(Float, default=0.0)
    avg_assessment: Mapped[float] = mapped_column(Float, default=0.0)
    avg_engagement: Mapped[float] = mapped_column(Float, default=0.0)
    avg_overall: Mapped[float] = mapped_column(Float, default=0.0)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("section_id", "semester_code", name="uq_section_semester_eval"),
    )
