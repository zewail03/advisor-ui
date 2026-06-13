from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.config import settings
from core.database import Base

# Real pgvector column on Postgres; JSON-encoded TEXT on the SQLite fallback.
if settings.database_url.startswith("postgresql"):
    from pgvector.sqlalchemy import Vector

    _EMBEDDING_TYPE = Vector(settings.embedding_dim)
else:
    _EMBEDDING_TYPE = Text


class Course(Base):
    __tablename__ = "courses"

    course_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    credits: Mapped[int] = mapped_column(Integer, default=3)
    lab_hours: Mapped[int] = mapped_column(Integer, default=0)
    lecture_hours: Mapped[int] = mapped_column(Integer, default=0)
    tutorial_hours: Mapped[int] = mapped_column(Integer, default=0)
    other_hours: Mapped[int] = mapped_column(Integer, default=0)
    swl_hours: Mapped[int] = mapped_column(Integer, default=0)
    category_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    major_code: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    sections = relationship("Section", back_populates="course", cascade="all, delete-orphan")

    @property
    def credit_hours(self) -> int:
        return self.credits

    @property
    def title(self) -> str:
        return self.name


class Section(Base):
    __tablename__ = "sections"

    section_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    semester_id: Mapped[int] = mapped_column(Integer, ForeignKey("semesters.semester_id"), nullable=False, index=True)
    section_number: Mapped[str] = mapped_column(String(50), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, default=30)
    status: Mapped[str] = mapped_column(String(20), default="Open", index=True)  # Open/Closed/Cancelled
    course_code: Mapped[str] = mapped_column(String(20), ForeignKey("courses.code"), nullable=False, index=True)
    instructor_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    course = relationship("Course", back_populates="sections", foreign_keys=[course_code])
    meetings = relationship("SectionMeeting", back_populates="section", cascade="all, delete-orphan")
    enrollments = relationship("Enrollment", back_populates="section", cascade="all, delete-orphan")
    waitlist_entries = relationship("Waitlist", back_populates="section", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_sections_course_semester", "course_code", "semester_id"),
    )


class SectionMeeting(Base):
    __tablename__ = "section_meetings"

    meeting_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    section_id: Mapped[int] = mapped_column(Integer, ForeignKey("sections.section_id", ondelete="CASCADE"), nullable=False, index=True)
    meeting_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    day_of_week: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    start_time: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    end_time: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    section = relationship("Section", back_populates="meetings")


class Prerequisite(Base):
    __tablename__ = "prerequisites"

    prerequisite_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_code: Mapped[str] = mapped_column(
        String(20), ForeignKey("courses.code"), index=True, nullable=False
    )
    course_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    prerequisite_course_code: Mapped[str] = mapped_column(
        String(20), ForeignKey("courses.code"), index=True, nullable=False
    )
    prerequisite_course_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    __table_args__ = (
        UniqueConstraint("course_code", "prerequisite_course_code", name="uq_prereq_pair"),
    )


class CourseEmbedding(Base):
    """pgvector store. Vector(dim) on Postgres; JSON TEXT on the SQLite fallback."""

    __tablename__ = "course_embeddings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(_EMBEDDING_TYPE, nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="course_catalog")
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    document_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
