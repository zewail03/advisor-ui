from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Float, ForeignKey, UniqueConstraint, DECIMAL, Boolean, TIMESTAMP, DATE, TIME, Text
from typing import Optional
from datetime import datetime


class Base(DeclarativeBase):
    pass


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[str] = mapped_column(String)
    password: Mapped[str] = mapped_column(String)

    summary = relationship(
        "AcademicSummary",
        back_populates="student",
        uselist=False,
        cascade="all, delete-orphan",
    )
    courses = relationship(
        "Course",
        back_populates="student",
        cascade="all, delete-orphan",
    )
    profile = relationship(
        "StudentProfile",
        back_populates="student",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # Transcript courses (Academic Records)
    transcript_courses = relationship(
        "TranscriptCourse",
        back_populates="student",
        cascade="all, delete-orphan",
    )

    # ============================
    # Financial Account
    # ============================
    financial_accounts = relationship(
        "FinancialAccount",
        back_populates="student",
        cascade="all, delete-orphan",
    )
    financial_transactions = relationship(
        "FinancialTransaction",
        back_populates="student",
        cascade="all, delete-orphan",
    )
    scholarships = relationship(
        "Scholarship",
        back_populates="student",
        cascade="all, delete-orphan",
    )

    # ============================
    # Manage Classes (NEW)
    # ============================
    enrollments = relationship(
        "Enrollment",
        back_populates="student",
        cascade="all, delete-orphan",
    )
    requirement_progress = relationship(
        "StudentRequirementProgress",
        back_populates="student",
        cascade="all, delete-orphan",
    )
    enrollment_stats = relationship(
        "EnrollmentStats",
        back_populates="student",
        cascade="all, delete-orphan",
    )
    waitlist = relationship(
        "CourseWaitlist",
        back_populates="student",
        cascade="all, delete-orphan",
    )


class AcademicSummary(Base):
    __tablename__ = "academic_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id_fk: Mapped[int] = mapped_column(
        ForeignKey("students.id"), unique=True, index=True
    )

    # Excel fields
    gpa: Mapped[float] = mapped_column(Float)  # (cgpa from excel)
    total_credit_hours: Mapped[int] = mapped_column(Integer)

    # Derived / optional fields (frontend may expect these)
    remaining_hours: Mapped[int] = mapped_column(Integer, default=0)
    class_rank: Mapped[str] = mapped_column(String, default="-")
    total_students: Mapped[int] = mapped_column(Integer, default=0)

    student = relationship("Student", back_populates="summary")


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id_fk: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)

    code: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String)

    student = relationship("Student", back_populates="courses")

    # prevent duplicates per student
    __table_args__ = (
        UniqueConstraint("student_id_fk", "code", name="uq_student_course_code"),
    )


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id_fk: Mapped[int] = mapped_column(
        ForeignKey("students.id"), unique=True, index=True
    )

    # Personal
    full_name: Mapped[str] = mapped_column(String, default="")
    student_id: Mapped[str] = mapped_column(String, default="")
    date_of_birth: Mapped[str] = mapped_column(String, default="")
    gender: Mapped[str] = mapped_column(String, default="")
    nationality: Mapped[str] = mapped_column(String, default="")
    school_id: Mapped[str] = mapped_column(String, default="")
    username: Mapped[str] = mapped_column(String, default="")

    # Contact
    email: Mapped[str] = mapped_column(String, default="")
    phone: Mapped[str] = mapped_column(String, default="")
    home_address: Mapped[str] = mapped_column(String, default="")
    city: Mapped[str] = mapped_column(String, default="")
    postal_code: Mapped[str] = mapped_column(String, default="")

    # Emergency
    emergency_contact_name: Mapped[str] = mapped_column(String, default="")
    emergency_relationship: Mapped[str] = mapped_column(String, default="")
    emergency_phone: Mapped[str] = mapped_column(String, default="")
    emergency_email: Mapped[str] = mapped_column(String, default="")

    # Academic
    program: Mapped[str] = mapped_column(String, default="")
    major: Mapped[str] = mapped_column(String, default="")
    academic_year: Mapped[str] = mapped_column(String, default="")
    expected_graduation: Mapped[str] = mapped_column(String, default="")
    academic_advisor: Mapped[str] = mapped_column(String, default="")

    # Account Settings (toggles)
    notif_email: Mapped[int] = mapped_column(Integer, default=1)
    notif_sms: Mapped[int] = mapped_column(Integer, default=1)
    notif_advisor: Mapped[int] = mapped_column(Integer, default=1)
    public_profile: Mapped[int] = mapped_column(Integer, default=0)

    student = relationship("Student", back_populates="profile")


class TranscriptCourse(Base):
    __tablename__ = "transcript_courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id_fk: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)

    term: Mapped[str] = mapped_column(String)
    course_code: Mapped[str] = mapped_column(String)
    course_name: Mapped[str] = mapped_column(String)
    credits: Mapped[int] = mapped_column(Integer)

    grade_letter: Mapped[str] = mapped_column(String)
    grade_points: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String)

    student = relationship("Student", back_populates="transcript_courses")


# ==========================================================
# Financial Account Models
# ==========================================================

class FinancialAccount(Base):
    __tablename__ = "financial_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id_fk: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)

    term: Mapped[str] = mapped_column(String, default="")
    term_credits: Mapped[int] = mapped_column(Integer, default=0)

    tuition_fee: Mapped[int] = mapped_column(Integer, default=0)
    transportation_fee: Mapped[int] = mapped_column(Integer, default=0)
    fines: Mapped[int] = mapped_column(Integer, default=0)

    total_charges: Mapped[int] = mapped_column(Integer, default=0)
    scholarship_credit: Mapped[int] = mapped_column(Integer, default=0)
    payments_made: Mapped[int] = mapped_column(Integer, default=0)
    current_balance: Mapped[int] = mapped_column(Integer, default=0)

    payment_due_date: Mapped[str] = mapped_column(String, default="")
    payment_status: Mapped[str] = mapped_column(String, default="Due")

    currency: Mapped[str] = mapped_column(String, default="EGP")
    last_updated: Mapped[str] = mapped_column(String, default="")

    student = relationship("Student", back_populates="financial_accounts")

    __table_args__ = (
        UniqueConstraint("student_id_fk", "term", name="uq_student_term_financial_account"),
    )


class FinancialTransaction(Base):
    __tablename__ = "financial_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id_fk: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)

    transaction_id: Mapped[str] = mapped_column(String, default="", index=True)

    term: Mapped[str] = mapped_column(String, default="")
    date: Mapped[str] = mapped_column(String, default="")

    type: Mapped[str] = mapped_column(String, default="")
    category: Mapped[str] = mapped_column(String, default="")
    description: Mapped[str] = mapped_column(String, default="")

    amount: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String, default="EGP")

    status: Mapped[str] = mapped_column(String, default="Posted")
    reference: Mapped[str] = mapped_column(String, default="")

    student = relationship("Student", back_populates="financial_transactions")

    __table_args__ = (
        UniqueConstraint("student_id_fk", "transaction_id", name="uq_student_transaction_id"),
    )


class Scholarship(Base):
    __tablename__ = "scholarships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    student_id_fk: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)

    scholarship_id: Mapped[str] = mapped_column(String, default="", index=True)

    term: Mapped[str] = mapped_column(String, default="")

    scholarship_type: Mapped[str] = mapped_column(String, default="")
    percentage: Mapped[int] = mapped_column(Integer, default=0)
    amount: Mapped[int] = mapped_column(Integer, default=0)

    status: Mapped[str] = mapped_column(String, default="Active")
    criteria_basis: Mapped[str] = mapped_column(String, default="")
    cgpa_at_award: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[str] = mapped_column(String, default="")

    student = relationship("Student", back_populates="scholarships")

    __table_args__ = (
        UniqueConstraint("student_id_fk", "scholarship_id", name="uq_student_scholarship_id"),
    )


# ==========================================================
# Manage Classes Models (NEW)
# ==========================================================

class CoursesCatalog(Base):
    __tablename__ = "courses_catalog"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    course_title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    units: Mapped[float] = mapped_column(DECIMAL(3, 2), default=3.00)
    grading_type: Mapped[str] = mapped_column(String(20), default="Graded")
    components: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    career: Mapped[str] = mapped_column(String(50), default="Undergraduate")
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    prerequisites: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    corequisites: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    typically_offered: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.utcnow)
    
    sections = relationship("CourseSection", back_populates="course")
    enrollments = relationship("Enrollment", back_populates="course")


class CourseSection(Base):
    __tablename__ = "course_sections"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    course_code: Mapped[str] = mapped_column(String(20), ForeignKey("courses_catalog.course_code"), nullable=False)
    section_number: Mapped[int] = mapped_column(Integer, nullable=False)
    term: Mapped[str] = mapped_column(String(50), nullable=False)
    session_type: Mapped[str] = mapped_column(String(50), default="Regular Academic Session")
    status: Mapped[str] = mapped_column(String(20), default="Opened", index=True)
    total_seats: Mapped[int] = mapped_column(Integer, default=60)
    enrolled_seats: Mapped[int] = mapped_column(Integer, default=0)
    waitlist_seats: Mapped[int] = mapped_column(Integer, default=0)
    start_date: Mapped[Optional[str]] = mapped_column(DATE, nullable=True)
    end_date: Mapped[Optional[str]] = mapped_column(DATE, nullable=True)
    
    # Lecture details
    lecture_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    lecture_days: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    lecture_time_start: Mapped[Optional[str]] = mapped_column(TIME, nullable=True)
    lecture_time_end: Mapped[Optional[str]] = mapped_column(TIME, nullable=True)
    lecture_room: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    lecture_instructor: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Tutorial details
    tutorial_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    tutorial_days: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    tutorial_time_start: Mapped[Optional[str]] = mapped_column(TIME, nullable=True)
    tutorial_time_end: Mapped[Optional[str]] = mapped_column(TIME, nullable=True)
    tutorial_room: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    tutorial_instructor: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    # Laboratory details
    lab_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    lab_days: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    lab_time_start: Mapped[Optional[str]] = mapped_column(TIME, nullable=True)
    lab_time_end: Mapped[Optional[str]] = mapped_column(TIME, nullable=True)
    lab_room: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    lab_instructor: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('course_code', 'section_number', 'term', name='uq_section'),
    )
    
    course = relationship("CoursesCatalog", back_populates="sections")
    enrollments = relationship("Enrollment", back_populates="section")


class Enrollment(Base):
    __tablename__ = "enrollments"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id_fk: Mapped[int] = mapped_column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    section_id: Mapped[int] = mapped_column(Integer, ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
    course_code: Mapped[str] = mapped_column(String(20), ForeignKey("courses_catalog.course_code"), nullable=False)
    term: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="Enrolled", index=True)
    enrollment_date: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.utcnow)
    drop_date: Mapped[Optional[datetime]] = mapped_column(TIMESTAMP, nullable=True)
    grade: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    units_earned: Mapped[Optional[float]] = mapped_column(DECIMAL(3, 2), nullable=True)
    
    student = relationship("Student", back_populates="enrollments")
    section = relationship("CourseSection", back_populates="enrollments")
    course = relationship("CoursesCatalog", back_populates="enrollments")


class DegreeRequirements(Base):
    __tablename__ = "degree_requirements"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    program: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    major: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    requirement_category: Mapped[str] = mapped_column(String(200), nullable=False)
    category_order: Mapped[int] = mapped_column(Integer, default=1)
    total_units_required: Mapped[float] = mapped_column(DECIMAL(5, 2), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_core: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.utcnow)
    
    courses = relationship("RequirementCourse", back_populates="requirement")
    student_progress = relationship("StudentRequirementProgress", back_populates="requirement")


class RequirementCourse(Base):
    __tablename__ = "requirement_courses"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    requirement_id: Mapped[int] = mapped_column(Integer, ForeignKey("degree_requirements.id", ondelete="CASCADE"), nullable=False)
    course_code: Mapped[str] = mapped_column(String(20), ForeignKey("courses_catalog.course_code"), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    
    requirement = relationship("DegreeRequirements", back_populates="courses")


class StudentRequirementProgress(Base):
    __tablename__ = "student_requirement_progress"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id_fk: Mapped[int] = mapped_column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    requirement_id: Mapped[int] = mapped_column(Integer, ForeignKey("degree_requirements.id", ondelete="CASCADE"), nullable=False)
    units_completed: Mapped[float] = mapped_column(DECIMAL(5, 2), default=0.00)
    units_in_progress: Mapped[float] = mapped_column(DECIMAL(5, 2), default=0.00)
    status: Mapped[str] = mapped_column(String(20), default="Not Started")
    last_updated: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('student_id_fk', 'requirement_id', name='uq_student_requirement'),
    )
    
    student = relationship("Student", back_populates="requirement_progress")
    requirement = relationship("DegreeRequirements", back_populates="student_progress")


class EnrollmentStats(Base):
    __tablename__ = "enrollment_stats"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id_fk: Mapped[int] = mapped_column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    term: Mapped[str] = mapped_column(String(50), nullable=False)
    enrolled_classes: Mapped[int] = mapped_column(Integer, default=0)
    total_units: Mapped[int] = mapped_column(Integer, default=0)
    units_completed: Mapped[int] = mapped_column(Integer, default=0)
    units_in_progress: Mapped[int] = mapped_column(Integer, default=0)
    completion_percentage: Mapped[float] = mapped_column(DECIMAL(5, 2), default=0.00)
    available_to_enroll: Mapped[int] = mapped_column(Integer, default=0)
    enrollment_deadline: Mapped[Optional[str]] = mapped_column(DATE, nullable=True)
    last_updated: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.utcnow)
    
    __table_args__ = (
        UniqueConstraint('student_id_fk', 'term', name='uq_student_term_stats'),
    )
    
    student = relationship("Student", back_populates="enrollment_stats")


class CourseWaitlist(Base):
    __tablename__ = "course_waitlist"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id_fk: Mapped[int] = mapped_column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    section_id: Mapped[int] = mapped_column(Integer, ForeignKey("course_sections.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    added_date: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.utcnow)
    notified: Mapped[bool] = mapped_column(Boolean, default=False)
    
    __table_args__ = (
        UniqueConstraint('student_id_fk', 'section_id', name='uq_student_section_waitlist'),
    )
    
    student = relationship("Student", back_populates="waitlist")
    section = relationship("CourseSection")