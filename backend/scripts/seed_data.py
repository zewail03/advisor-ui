"""Seed Postgres with demo data.

Run from backend/:  python -m scripts.seed_data
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta

# Ensure `backend/` is on path whether run directly or via -m
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from sqlalchemy import select

from core.database import AsyncSessionLocal, engine, Base
from core.security import get_password_hash
from models import (  # noqa: F401 registers all models
    Program,
    Student,
    StudentProfile,
    AcademicStanding,
    StandingEnum,
    Course,
    Section,
    Prerequisite,
    DegreeRequirement,
    RequirementCourse,
    StudentRequirementProgress,
    TranscriptRecord,
    RegistrationPeriod,
    Semester,
    FinancialAccount,
    FinancialTransaction,
    Scholarship,
    Enrollment,
    Grade,
    GradeEnum,
    GRADE_POINTS,
)


CURRENT_SEMESTER = "Fall-2025"
NEXT_SEMESTER = "Spring-2026"


PROGRAMS = [
    {"code": "AIE", "name": "Artificial Intelligence Engineering", "faculty": "Computing"},
    {"code": "CSE", "name": "Computer Science & Engineering", "faculty": "Computing"},
    {"code": "IT",  "name": "Information Technology",            "faculty": "Computing"},
]


# (code, title, credit_hours, department, prereq_codes)
COURSES = [
    # First year
    ("MATH101", "Calculus I", 3, "Math", []),
    ("MATH102", "Calculus II", 3, "Math", ["MATH101"]),
    ("PHYS101", "Physics I", 3, "Science", []),
    ("CSE101",  "Intro to Computing", 3, "CSE", []),
    ("CSE102",  "Programming Fundamentals", 3, "CSE", ["CSE101"]),
    ("ENG101",  "Academic English", 2, "Humanities", []),
    # Second year
    ("CSE201",  "Data Structures", 3, "CSE", ["CSE102"]),
    ("CSE202",  "Algorithms", 3, "CSE", ["CSE201"]),
    ("CSE203",  "Discrete Math", 3, "Math", ["MATH101"]),
    ("CSE204",  "Computer Organization", 3, "CSE", ["CSE101"]),
    ("MATH201", "Linear Algebra", 3, "Math", ["MATH101"]),
    ("MATH202", "Probability & Statistics", 3, "Math", ["MATH102"]),
    # Third year
    ("CSE301",  "Operating Systems", 3, "CSE", ["CSE204", "CSE201"]),
    ("CSE302",  "Databases", 3, "CSE", ["CSE201"]),
    ("CSE303",  "Software Engineering", 3, "CSE", ["CSE201"]),
    ("CSE304",  "Computer Networks", 3, "CSE", ["CSE301"]),
    ("AIE301",  "Intro to AI", 3, "AIE", ["CSE201", "MATH202"]),
    ("AIE302",  "Machine Learning", 3, "AIE", ["AIE301"]),
    ("AIE303",  "Deep Learning", 3, "AIE", ["AIE302"]),
    ("AIE304",  "Natural Language Processing", 3, "AIE", ["AIE302"]),
    # Fourth year
    ("CSE401",  "Digital Image Processing", 3, "CSE", ["AIE302"]),
    ("AIE401",  "Reinforcement Learning", 3, "AIE", ["AIE302"]),
    ("AIE402",  "Computer Vision", 3, "AIE", ["AIE303"]),
    ("AIE403",  "AI Ethics", 2, "AIE", []),
    ("CSE402",  "Capstone Project I", 3, "CSE", ["CSE303"]),
    ("CSE403",  "Capstone Project II", 3, "CSE", ["CSE402"]),
    # Humanities / electives
    ("HUM101",  "Critical Thinking", 2, "Humanities", []),
    ("HUM102",  "Innovation & Entrepreneurship", 2, "Humanities", []),
    ("HUM201",  "Arabic Communication", 2, "Humanities", []),
    ("HUM202",  "Ethics in Technology", 2, "Humanities", []),
]


# 12 requirement categories per program (simplified)
def _requirements_for_program(program_code: str):
    return [
        ("University Core", 6, True),
        ("College Core", 9, True),
        ("Mathematics", 12, True),
        ("Science", 6, True),
        ("Programming Foundations", 9, True),
        ("Systems", 9, True),
        ("AI / Theory", 12, True),
        ("Software Engineering", 6, True),
        ("Capstone", 6, True),
        ("Humanities", 8, True),
        ("Technical Electives", 12, False),
        ("Free Electives", 6, False),
    ]


def _build_section(course_id: str, idx: int, semester: str, instructor: str, days: str, t_start: str, t_end: str, room: str):
    return Section(
        course_id=course_id,
        section_number=f"{idx:02d}",
        semester_code=semester,
        instructor=instructor,
        days=days,
        time_start=t_start,
        time_end=t_end,
        room=room,
        capacity=35,
        enrolled_count=0,
        status="Opened",
    )


TIMES = [
    ("08:00", "09:30"),
    ("09:45", "11:15"),
    ("11:30", "13:00"),
    ("13:15", "14:45"),
    ("15:00", "16:30"),
]
DAY_PAIRS = ["Mon,Wed", "Tue,Thu", "Sun,Tue", "Mon,Wed,Fri"]


async def already_seeded(db) -> bool:
    result = await db.execute(select(Student).limit(1))
    return result.scalar_one_or_none() is not None


async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        if await already_seeded(db):
            print("Database already seeded. Skipping.")
            return

        # --- Programs ---
        programs = {}
        for p in PROGRAMS:
            prog = Program(code=p["code"], name=p["name"], faculty=p["faculty"], total_credits_required=140)
            db.add(prog)
            programs[p["code"]] = prog
        await db.flush()

        # --- Courses ---
        courses_by_code = {}
        for code, title, cr, dept, _prereqs in COURSES:
            c = Course(
                code=code,
                title=title,
                description=f"{title} \u2014 course offered in the {dept} department.",
                credit_hours=cr,
                department=dept,
                program_id=programs["AIE"].id,
                grading_type="Graded",
            )
            db.add(c)
            courses_by_code[code] = c
        await db.flush()

        # --- Prerequisites ---
        for code, _title, _cr, _dept, prereqs in COURSES:
            for pcode in prereqs:
                if pcode in courses_by_code:
                    db.add(
                        Prerequisite(
                            course_id=courses_by_code[code].id,
                            prerequisite_course_id=courses_by_code[pcode].id,
                            minimum_grade="D",
                        )
                    )
        await db.flush()

        # --- Sections for current + next semester ---
        for semester in (CURRENT_SEMESTER, NEXT_SEMESTER):
            for i, (code, c) in enumerate(courses_by_code.items()):
                days = DAY_PAIRS[i % len(DAY_PAIRS)]
                t_start, t_end = TIMES[i % len(TIMES)]
                sec = _build_section(
                    course_id=c.id,
                    idx=1,
                    semester=semester,
                    instructor=f"Dr. Instructor {i + 1}",
                    days=days,
                    t_start=t_start,
                    t_end=t_end,
                    room=f"Hall {100 + (i % 20)}",
                )
                db.add(sec)
        await db.flush()

        # --- Degree requirements ---
        for prog_code, prog in programs.items():
            for order, (cat, units, is_core) in enumerate(_requirements_for_program(prog_code), start=1):
                db.add(
                    DegreeRequirement(
                        program_id=prog.id,
                        category=cat,
                        category_order=order,
                        total_units_required=units,
                        is_core=is_core,
                    )
                )
        await db.flush()

        # --- Registration period (open now) ---
        now = datetime.utcnow()
        db.add(
            RegistrationPeriod(
                semester_code=NEXT_SEMESTER,
                start_date=now - timedelta(days=2),
                end_date=now + timedelta(days=30),
                drop_deadline=now + timedelta(days=60),
                is_active=True,
            )
        )
        current_start = now - timedelta(days=45)
        next_start = now + timedelta(days=70)
        db.add(
            Semester(
                code=CURRENT_SEMESTER,
                name="Fall 2025/2026",
                start_date=current_start,
                end_date=now + timedelta(days=60),
                drop_deadline=now + timedelta(days=30),
                week_2_end=current_start + timedelta(weeks=2),
                week_4_end=current_start + timedelta(weeks=4),
                week_13_end=current_start + timedelta(weeks=13),
                is_current=True,
                is_summer=False,
            )
        )
        db.add(
            Semester(
                code=NEXT_SEMESTER,
                name="Spring 2025/2026",
                start_date=next_start,
                end_date=now + timedelta(days=190),
                drop_deadline=now + timedelta(days=160),
                week_2_end=next_start + timedelta(weeks=2),
                week_4_end=next_start + timedelta(weeks=4),
                week_13_end=next_start + timedelta(weeks=13),
                is_current=False,
                is_summer=False,
            )
        )

        # --- Demo student ---
        demo = Student(
            student_number="20220001",
            first_name="Adham",
            last_name="Demo",
            email="20220001@aiu.edu.eg",
            hashed_password=get_password_hash("demo123"),
            program_id=programs["AIE"].id,
            academic_level=3,
        )
        db.add(demo)
        await db.flush()

        db.add(
            StudentProfile(
                student_id=demo.id,
                major="Artificial Intelligence Engineering",
                academic_year="Third Year",
                expected_graduation="Spring 2027",
                phone="",
                notif_email=1,
                notif_sms=1,
                notif_advisor=1,
                public_profile=0,
            )
        )

        # Academic standing
        db.add(
            AcademicStanding(
                student_id=demo.id,
                cgpa=3.42,
                sgpa_current=3.60,
                standing=StandingEnum.good,
                total_credit_hours=140,
                completed_credit_hours=72,
                consecutive_probation_semesters=0,
            )
        )

        # Transcript history (4 semesters)
        transcript_rows = [
            # Fall-2023
            ("Fall-2023", "MATH101", "Calculus I", 3, "A-", 3.7),
            ("Fall-2023", "PHYS101", "Physics I", 3, "B+", 3.3),
            ("Fall-2023", "CSE101", "Intro to Computing", 3, "A", 4.0),
            ("Fall-2023", "ENG101", "Academic English", 2, "B", 3.0),
            ("Fall-2023", "HUM101", "Critical Thinking", 2, "A-", 3.7),
            # Spring-2024
            ("Spring-2024", "MATH102", "Calculus II", 3, "B+", 3.3),
            ("Spring-2024", "CSE102", "Programming Fundamentals", 3, "A", 4.0),
            ("Spring-2024", "MATH201", "Linear Algebra", 3, "A-", 3.7),
            ("Spring-2024", "HUM102", "Innovation & Entrepreneurship", 2, "A", 4.0),
            # Fall-2024
            ("Fall-2024", "CSE201", "Data Structures", 3, "A", 4.0),
            ("Fall-2024", "CSE203", "Discrete Math", 3, "B+", 3.3),
            ("Fall-2024", "CSE204", "Computer Organization", 3, "B", 3.0),
            ("Fall-2024", "MATH202", "Probability & Statistics", 3, "A-", 3.7),
            # Spring-2025
            ("Spring-2025", "CSE202", "Algorithms", 3, "A-", 3.7),
            ("Spring-2025", "CSE301", "Operating Systems", 3, "B+", 3.3),
            ("Spring-2025", "CSE302", "Databases", 3, "A", 4.0),
            ("Spring-2025", "AIE301", "Intro to AI", 3, "A", 4.0),
            ("Spring-2025", "HUM201", "Arabic Communication", 2, "A-", 3.7),
        ]
        for sem, code, name, cr, letter, pts in transcript_rows:
            db.add(
                TranscriptRecord(
                    student_id=demo.id,
                    semester_code=sem,
                    course_code=code,
                    course_name=name,
                    credits=cr,
                    grade_letter=letter,
                    grade_points=pts,
                    status="Completed",
                )
            )

        # Financial account (current semester)
        db.add(
            FinancialAccount(
                student_id=demo.id,
                semester_code=CURRENT_SEMESTER,
                term_credits=15,
                tuition_fee=60000,
                transportation_fee=3000,
                fines=0,
                total_charges=63000,
                scholarship_credit=10000,
                payments_made=30000,
                current_balance=23000,
                payment_due_date="2025-12-01",
                payment_status="Due",
                currency="EGP",
            )
        )

        db.add(
            Scholarship(
                student_id=demo.id,
                scholarship_ref="SCH-2025-001",
                semester_code=CURRENT_SEMESTER,
                scholarship_type="Academic Merit",
                percentage=15,
                amount=10000,
                status="Active",
                criteria_basis="CGPA >= 3.3",
                cgpa_at_award=3.42,
            )
        )

        for i, (date, desc, amount, ttype) in enumerate(
            [
                ("2025-09-05", "Tuition charge Fall-2025", 60000, "invoice"),
                ("2025-09-05", "Transportation Fall-2025", 3000, "invoice"),
                ("2025-09-10", "Scholarship credit",       10000, "credit"),
                ("2025-10-15", "Cash payment",             30000, "payment"),
            ],
            start=1,
        ):
            db.add(
                FinancialTransaction(
                    student_id=demo.id,
                    transaction_ref=f"TXN-2025-{i:04d}",
                    semester_code=CURRENT_SEMESTER,
                    date=date,
                    type=ttype,
                    category="Tuition" if "Tuition" in desc else "Other",
                    description=desc,
                    amount=amount,
                    currency="EGP",
                    status="Posted",
                    reference="",
                )
            )

        await db.commit()
        print("Seed complete. Demo student: 20220001 / demo123")


if __name__ == "__main__":
    asyncio.run(seed())
