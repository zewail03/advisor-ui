from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Float, Boolean, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


GRADE_POINTS = {
    "A+": 4.0, "A": 4.0, "A-": 3.7,
    "B+": 3.3, "B": 3.0, "B-": 2.7,
    "C+": 2.3, "C": 2.0, "C-": 1.7,
    "D+": 1.3, "D": 1.0,
    "F": 0.0, "FW": 0.0,
    "W": None, "I": None, "S": None, "U": None,
}


class Enrollment(Base):
    __tablename__ = "enrollments"

    enrollment_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False, index=True)
    section_id: Mapped[int] = mapped_column(Integer, ForeignKey("sections.section_id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="Enrolled", index=True)  # Enrolled/Dropped/Withdrawn/Satisfied/Failed
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    is_retake: Mapped[bool] = mapped_column(Boolean, default=False)
    enrollment_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    drop_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    withdrawal_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("student_id", "section_id", name="uq_enrollment_student_section"),
    )

    student = relationship("Student", back_populates="enrollments")
    section = relationship("Section", back_populates="enrollments")
    grade = relationship("Grade", back_populates="enrollment", uselist=False, cascade="all, delete-orphan")


class Grade(Base):
    __tablename__ = "grades"

    grade_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enrollment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("enrollments.enrollment_id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    grade_letter: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    grade_points: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    percentage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    counts_in_gpa: Mapped[bool] = mapped_column(Boolean, default=True)
    is_improvement: Mapped[bool] = mapped_column(Boolean, default=False)
    grade_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    enrollment = relationship("Enrollment", back_populates="grade")


class Waitlist(Base):
    __tablename__ = "waitlist"

    waitlist_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.student_id", ondelete="CASCADE"), nullable=False, index=True)
    section_id: Mapped[int] = mapped_column(Integer, ForeignKey("sections.section_id", ondelete="CASCADE"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="Waiting")  # Waiting/Registered/Expired/Cancelled
    joined_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    registered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("student_id", "section_id", name="uq_student_section_waitlist"),
    )

    student = relationship("Student", back_populates="waitlist")
    section = relationship("Section", back_populates="waitlist_entries")
