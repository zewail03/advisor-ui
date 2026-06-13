from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class Semester(Base):
    __tablename__ = "semesters"

    semester_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)  # "Fall 2025"
    type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # Fall/Spring/Summer
    year_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    year_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    weeks: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False)


class RegistrationPeriod(Base):
    __tablename__ = "registration_periods"

    registration_period_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    semester_id: Mapped[int] = mapped_column(Integer, ForeignKey("semesters.semester_id"), nullable=False)
    priority_group: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    open_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    close_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AcademicStanding(Base):
    """Per-semester row. Look up latest by student_code ORDER BY semester_id DESC."""

    __tablename__ = "academic_standing"

    academic_standing_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    semester_id: Mapped[int] = mapped_column(Integer, ForeignKey("semesters.semester_id"), nullable=False, index=True)
    student_code: Mapped[str] = mapped_column(
        String(20), ForeignKey("students.student_code"), nullable=False, index=True
    )
    semester_code: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    semester_gpa: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    cgpa: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="Good Standing")
    # Consecutive-warning ladder (Dr. Ashraf §2): warning_count = consecutive
    # warnings (dismissal at 4); severe streak (CGPA < 1.0, dismissal at 3) is
    # tracked in probation_semesters for backward compat — see services.standing.
    warning_count: Mapped[int] = mapped_column(Integer, default=0)
    probation_semesters: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    __table_args__ = (
        UniqueConstraint("student_code", "semester_id", name="uq_standing_student_semester"),
    )


class RequirementCategory(Base):
    __tablename__ = "requirement_categories"

    # NOTE: CSV has a typo — real column is "caregory_id". We map the Python attribute to
    # a clean name but keep the DB column name matching the CSV for seed compatibility.
    category_id: Mapped[int] = mapped_column("caregory_id", Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class RequirementGroup(Base):
    __tablename__ = "requirement_groups"

    group_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_id: Mapped[int] = mapped_column(Integer, ForeignKey("programs.program_id"), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    course_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    course_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    min_courses: Mapped[int] = mapped_column(Integer, default=0)
    min_credits: Mapped[int] = mapped_column(Integer, default=0)
    major_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("majors.major_id"), nullable=True)


class RequirementGroupCourse(Base):
    __tablename__ = "requirement_group_courses"

    rgc_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_id: Mapped[int] = mapped_column(Integer, ForeignKey("programs.program_id"), nullable=False)
    major_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("majors.major_id"), nullable=True)
    major_code: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    group_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    course_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    course_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    required_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    required_semester: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
