"""Seed §17 six-program structure and §18 university requirements.

Idempotent — safe to re-run. Creates:
  * 6 programs: CE, AIE, CSEC (157 CH), CS, AIS, SE (133 CH)
  * 7 university-requirement core courses (LAN011/LAN114/MGT301/LAN112/GEO217/PSC101/LIB116)
  * 7 university-requirement elective categories with a pool of 35 courses
  * DegreeRequirement rows linking the pool to each program
"""
import asyncio

from sqlalchemy import select

from core.database import AsyncSessionLocal
from models.course import Course
from models.academic import DegreeRequirement, RequirementCourse
from models.student import Program


PROGRAMS = [
    ("CE", "Computer Engineering", "Engineering", 157),
    ("AIE", "AI Engineering", "Engineering", 157),
    ("CSEC", "Cybersecurity Engineering", "Engineering", 157),
    ("CS", "Computer Science", "Computing", 133),
    ("AIS", "AI Science", "Computing", 133),
    ("SE", "Software Engineering", "Computing", 133),
]


UNIVERSITY_CORE = [
    ("LAN011", "Academic English I", 3),
    ("LAN114", "Academic English II", 3),
    ("LAN112", "Arabic Language & Literature", 3),
    ("MGT301", "Principles of Management", 3),
    ("GEO217", "Geography of Egypt", 3),
    ("PSC101", "Political Science", 3),
    ("LIB116", "Library & Research Skills", 1),
]


# §18.2 Seven elective categories — five courses each
ELECTIVES = {
    "Humanities": [
        ("HUM201", "Introduction to Philosophy", 3),
        ("HUM202", "Ethics in Technology", 3),
        ("HUM203", "World Literature", 3),
        ("HUM204", "History of Science", 3),
        ("HUM205", "Critical Thinking", 3),
    ],
    "Social Sciences": [
        ("SOC201", "Introduction to Sociology", 3),
        ("SOC202", "Psychology of Learning", 3),
        ("SOC203", "Modern Egyptian Society", 3),
        ("SOC204", "Cross-Cultural Communication", 3),
        ("SOC205", "Media & Society", 3),
    ],
    "Business & Entrepreneurship": [
        ("BUS201", "Entrepreneurship Basics", 3),
        ("BUS202", "Marketing Fundamentals", 3),
        ("BUS203", "Financial Literacy", 3),
        ("BUS204", "Project Management", 3),
        ("BUS205", "Innovation Management", 3),
    ],
    "Arts & Design": [
        ("ART201", "Visual Design Principles", 3),
        ("ART202", "Digital Photography", 3),
        ("ART203", "Music Appreciation", 3),
        ("ART204", "Creative Writing", 3),
        ("ART205", "Theatre & Performance", 3),
    ],
    "Health & Wellness": [
        ("HLT201", "Nutrition Fundamentals", 3),
        ("HLT202", "Physical Fitness", 3),
        ("HLT203", "Mental Health Awareness", 3),
        ("HLT204", "First Aid & Safety", 3),
        ("HLT205", "Sports & Recreation", 3),
    ],
    "Environment & Sustainability": [
        ("ENV201", "Environmental Science", 3),
        ("ENV202", "Climate Change", 3),
        ("ENV203", "Renewable Energy Basics", 3),
        ("ENV204", "Sustainable Cities", 3),
        ("ENV205", "Conservation & Biodiversity", 3),
    ],
    "Languages": [
        ("LAN301", "French I", 3),
        ("LAN302", "German I", 3),
        ("LAN303", "Spanish I", 3),
        ("LAN304", "Mandarin I", 3),
        ("LAN305", "Japanese I", 3),
    ],
}


async def _ensure_course(db, code: str, title: str, credits: int, category: str) -> Course:
    existing = (
        await db.execute(select(Course).where(Course.code == code))
    ).scalar_one_or_none()
    if existing:
        return existing
    course = Course(
        code=code,
        title=title,
        credit_hours=credits,
        department=category,
        grading_type="Graded",
        career="Undergraduate",
    )
    db.add(course)
    await db.flush()
    return course


async def _ensure_requirement(
    db, program_id: str, category: str, order: int, units: float, is_core: bool
) -> DegreeRequirement:
    existing = (
        await db.execute(
            select(DegreeRequirement)
            .where(DegreeRequirement.program_id == program_id)
            .where(DegreeRequirement.category == category)
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    req = DegreeRequirement(
        program_id=program_id,
        category=category,
        category_order=order,
        total_units_required=units,
        is_core=is_core,
    )
    db.add(req)
    await db.flush()
    return req


async def _ensure_requirement_course(db, requirement_id: str, course_id: str) -> None:
    existing = (
        await db.execute(
            select(RequirementCourse)
            .where(RequirementCourse.requirement_id == requirement_id)
            .where(RequirementCourse.course_id == course_id)
        )
    ).scalar_one_or_none()
    if existing:
        return
    db.add(RequirementCourse(requirement_id=requirement_id, course_id=course_id, is_required=True))


async def _ensure_program(db, code: str, name: str, faculty: str, credits: int) -> Program:
    existing = (
        await db.execute(select(Program).where(Program.code == code))
    ).scalar_one_or_none()
    if existing:
        existing.name = name
        existing.faculty = faculty
        existing.total_credits_required = credits
        return existing
    prog = Program(
        code=code, name=name, faculty=faculty, total_credits_required=credits
    )
    db.add(prog)
    await db.flush()
    return prog


async def run():
    async with AsyncSessionLocal() as db:
        # Programs
        programs = []
        for code, name, faculty, credits in PROGRAMS:
            programs.append(await _ensure_program(db, code, name, faculty, credits))

        # University core courses
        core_courses = []
        for code, title, credits in UNIVERSITY_CORE:
            core_courses.append(
                await _ensure_course(db, code, title, credits, "University Core")
            )

        # Elective pool
        elective_by_category: dict[str, list[Course]] = {}
        for category, courses in ELECTIVES.items():
            elective_by_category[category] = []
            for code, title, credits in courses:
                elective_by_category[category].append(
                    await _ensure_course(db, code, title, credits, f"Elective: {category}")
                )

        # Wire each program
        for prog in programs:
            # University core (19 CH total)
            core_req = await _ensure_requirement(
                db, prog.id, "University Core Requirements", 1,
                units=sum(c.credit_hours for c in core_courses),
                is_core=True,
            )
            for c in core_courses:
                await _ensure_requirement_course(db, core_req.id, c.id)

            # University electives (3 courses × 3 CH = 9 CH pool, pick 3)
            order = 2
            for category, courses in elective_by_category.items():
                req = await _ensure_requirement(
                    db, prog.id, f"University Elective — {category}", order,
                    units=3.0, is_core=False,
                )
                order += 1
                for c in courses:
                    await _ensure_requirement_course(db, req.id, c.id)

        await db.commit()

        print(f"Seeded {len(programs)} programs, "
              f"{len(core_courses)} core courses, "
              f"{sum(len(v) for v in elective_by_category.values())} elective courses.")


if __name__ == "__main__":
    asyncio.run(run())
