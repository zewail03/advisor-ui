from datetime import datetime, date
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, String, Integer, Float, ForeignKey, Date, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.database import Base


class Program(Base):
    __tablename__ = "programs"

    program_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    total_credits: Mapped[int] = mapped_column(Integer, default=140)
    duration_years: Mapped[int] = mapped_column(Integer, default=4)
    department: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    students = relationship("Student", back_populates="program")
    majors = relationship("Major", back_populates="program")


class Major(Base):
    __tablename__ = "majors"

    major_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program_id: Mapped[int] = mapped_column(Integer, ForeignKey("programs.program_id"), nullable=False)
    code: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)

    program = relationship("Program", back_populates="majors")
    students = relationship("Student", back_populates="major")


class Student(Base):
    __tablename__ = "students"

    student_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    program_id: Mapped[int] = mapped_column(Integer, ForeignKey("programs.program_id"), nullable=False)
    major_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("majors.major_id"), nullable=True)
    level: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30), default="Active")
    enrollment_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expected_graduation: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    cgpa: Mapped[float] = mapped_column(Float, default=0.0)
    # Math 0 placement exam result — sets the semester-1 credit load
    # (Dr. Ashraf §1.1). NULL = unknown (treated as passed).
    math0_passed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("cgpa >= 0 AND cgpa <= 4", name="ck_students_cgpa_range"),
    )

    # Self-service profile fields (student-entered via the profile page;
    # not part of the registrar dataset, so all nullable).
    date_of_birth: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    nationality: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    school_id: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    home_address: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    emergency_contact_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    emergency_relationship: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    emergency_phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    emergency_email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    program = relationship("Program", back_populates="students")
    major = relationship("Major", back_populates="students")
    enrollments = relationship("Enrollment", back_populates="student", cascade="all, delete-orphan")
    waitlist = relationship("Waitlist", back_populates="student", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="student", cascade="all, delete-orphan")
