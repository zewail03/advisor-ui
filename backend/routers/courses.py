"""Courses / sections / prereq endpoints.

Rewritten for the real AIU schema:
  * Courses are keyed by integer course_id but exposed via the natural `code`.
  * Prerequisites are stored by course_code string (no integer FK).
  * Sections track meetings via `SectionMeeting`; we summarise the first
    meeting into days/time_start/time_end/room to match the frontend contract.
  * Seat counts are computed from live Enrollment rows (no enrolled_count col).
  * Course has no `department` column — we expose `major_code` in its place.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.database import get_db
from models.academic import Semester
from models.course import Course, Prerequisite, Section
from models.enrollment import Enrollment

router = APIRouter()


_ENROLLED = ("Enrolled", "Satisfied")


def _first_meeting(section: Section) -> dict:
    meetings = section.meetings or []
    if not meetings:
        return {"days": "", "time_start": "", "time_end": "", "room": ""}
    days = ",".join(m.day_of_week for m in meetings if m.day_of_week)
    return {
        "days": days,
        "time_start": meetings[0].start_time or "",
        "time_end": meetings[0].end_time or "",
        "room": meetings[0].location or "",
    }


async def _section_enrolled_map(section_ids: list[int], db: AsyncSession) -> dict[int, int]:
    if not section_ids:
        return {}
    rows = await db.execute(
        select(Enrollment.section_id, func.count(Enrollment.enrollment_id))
        .where(
            and_(
                Enrollment.section_id.in_(section_ids),
                Enrollment.status.in_(_ENROLLED),
            )
        )
        .group_by(Enrollment.section_id)
    )
    return {sid: cnt for sid, cnt in rows.all()}


@router.get("")
async def list_courses(
    semester: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Course)
    if department:
        stmt = stmt.where(Course.major_code == department)
    if q:
        stmt = stmt.where(or_(Course.code.ilike(f"%{q}%"), Course.name.ilike(f"%{q}%")))
    result = await db.execute(stmt.limit(200))
    courses = result.scalars().all()
    return [
        {
            "id": c.course_id,
            "code": c.code,
            "title": c.name,
            "credits": c.credits,
            "department": c.major_code or "",
        }
        for c in courses
    ]


async def _resolve_course(course_key: str, db: AsyncSession) -> Optional[Course]:
    """Look up a course by integer id or code."""
    try:
        cid = int(course_key)
    except (TypeError, ValueError):
        cid = None
    if cid is not None:
        c = await db.get(Course, cid)
        if c:
            return c
    row = await db.execute(select(Course).where(Course.code == course_key))
    return row.scalar_one_or_none()


@router.get("/{course_key}")
async def get_course(course_key: str, db: AsyncSession = Depends(get_db)):
    course = await _resolve_course(course_key, db)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    sections_result = await db.execute(
        select(Section, Semester.code)
        .join(Semester, Semester.semester_id == Section.semester_id)
        .options(selectinload(Section.meetings))
        .where(Section.course_code == course.code)
    )
    section_rows = sections_result.unique().all()
    section_ids = [s.section_id for s, _ in section_rows]
    enrolled_map = await _section_enrolled_map(section_ids, db)

    prereq_rows = await db.execute(
        select(Prerequisite).where(Prerequisite.course_code == course.code)
    )
    prereqs = []
    for p in prereq_rows.scalars().all():
        prereqs.append(
            {
                "code": p.prerequisite_course_code,
                "title": p.prerequisite_course_name or p.prerequisite_course_code,
                "minimum_grade": "D",
            }
        )

    return {
        "id": course.course_id,
        "code": course.code,
        "title": course.name,
        "description": course.description,
        "credits": course.credits,
        "department": course.major_code or "",
        "prerequisites": prereqs,
        "sections": [
            {
                "section_id": s.section_id,
                "section_number": s.section_number,
                "semester": semester_code,
                "instructor": s.instructor_name or "",
                "capacity": s.capacity,
                "enrolled_count": enrolled_map.get(s.section_id, 0),
                "status": s.status,
                **_first_meeting(s),
            }
            for s, semester_code in section_rows
        ],
    }


async def _prereq_tree(course_code: str, db: AsyncSession, seen: Optional[set] = None):
    seen = seen or set()
    if course_code in seen:
        return None
    seen.add(course_code)
    course = (
        await db.execute(select(Course).where(Course.code == course_code))
    ).scalar_one_or_none()
    if not course:
        return None
    prereq_rows = await db.execute(
        select(Prerequisite.prerequisite_course_code).where(
            Prerequisite.course_code == course_code
        )
    )
    children = []
    for (child_code,) in prereq_rows.all():
        child = await _prereq_tree(child_code, db, seen)
        if child:
            children.append(child)
    return {
        "course_id": course.course_id,
        "code": course.code,
        "title": course.name,
        "prerequisites": children,
    }


@router.get("/{course_key}/prereq-tree")
async def get_prereq_tree(course_key: str, db: AsyncSession = Depends(get_db)):
    course = await _resolve_course(course_key, db)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    tree = await _prereq_tree(course.code, db)
    if not tree:
        raise HTTPException(status_code=404, detail="Course not found")
    return tree


@router.get("/sections/search")
async def search_sections(
    course_id: Optional[str] = Query(None),
    semester: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Section, Course, Semester)
        .join(Course, Course.code == Section.course_code)
        .join(Semester, Semester.semester_id == Section.semester_id)
        .options(selectinload(Section.meetings))
    )
    if course_id:
        course = await _resolve_course(course_id, db)
        if course:
            stmt = stmt.where(Section.course_code == course.code)
        else:
            return []
    if semester:
        stmt = stmt.where(Semester.code == semester)
    rows = (await db.execute(stmt.limit(200))).unique().all()
    section_ids = [s.section_id for s, _, _ in rows]
    enrolled_map = await _section_enrolled_map(section_ids, db)

    out = []
    for section, course, sem in rows:
        enrolled = enrolled_map.get(section.section_id, 0)
        out.append(
            {
                "section_id": section.section_id,
                "course_code": course.code,
                "course_title": course.name,
                "section_number": section.section_number,
                "semester": sem.code,
                "instructor": section.instructor_name or "",
                "capacity": section.capacity,
                "enrolled_count": enrolled,
                "available_seats": max(0, section.capacity - enrolled),
                "status": section.status,
                **_first_meeting(section),
            }
        )
    return out
