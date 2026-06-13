"""Admin course catalog + section management.

Reads open to any staff; writes (edit course, edit/create section) require a
write role and are audited.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_staff, require_role
from models.academic import Semester
from models.course import Course, Section
from models.enrollment import Enrollment
from models.staff import Staff, StaffRole
from services.audit_service import log_action

router = APIRouter()

_ENROLLED = ("Enrolled", "Satisfied")


class CourseUpdate(BaseModel):
    name: Optional[str] = None
    credits: Optional[int] = None
    description: Optional[str] = None
    major_code: Optional[str] = None


class SectionUpdate(BaseModel):
    instructor_name: Optional[str] = None
    capacity: Optional[int] = None
    status: Optional[str] = None


class SectionCreate(BaseModel):
    semester_id: int
    section_number: str
    instructor_name: Optional[str] = None
    capacity: int = 30
    status: str = "Open"


async def _enrolled_count(section_id: int, db: AsyncSession) -> int:
    return int(
        (
            await db.execute(
                select(func.count())
                .select_from(Enrollment)
                .where(Enrollment.section_id == section_id, Enrollment.status.in_(_ENROLLED))
            )
        ).scalar()
        or 0
    )


@router.get("/courses")
async def list_courses(
    q: Optional[str] = Query(None),
    limit: int = Query(25, le=100),
    offset: int = Query(0, ge=0),
    staff: Staff = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if q:
        like = f"%{q.strip()}%"
        filters.append(or_(Course.code.ilike(like), Course.name.ilike(like)))
    total = int((await db.execute(select(func.count()).select_from(Course).where(*filters))).scalar() or 0)

    rows = (
        await db.execute(select(Course).where(*filters).order_by(Course.code).limit(limit).offset(offset))
    ).scalars().all()
    # section counts per course
    out = []
    for c in rows:
        n_sec = int(
            (await db.execute(select(func.count()).select_from(Section).where(Section.course_code == c.code))).scalar()
            or 0
        )
        out.append({
            "course_id": c.course_id, "code": c.code, "name": c.name,
            "credits": c.credits, "major_code": c.major_code, "sections": n_sec,
        })
    return {"total": total, "limit": limit, "offset": offset, "courses": out}


@router.get("/courses/{course_id}")
async def get_course(
    course_id: int,
    staff: Staff = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    c = await db.get(Course, course_id)
    if not c:
        raise HTTPException(status_code=404, detail="Course not found")

    rows = (
        await db.execute(
            select(Section, Semester.code)
            .join(Semester, Semester.semester_id == Section.semester_id)
            .where(Section.course_code == c.code)
            .order_by(Semester.semester_id.desc(), Section.section_number)
        )
    ).all()
    sections = []
    for s, sem in rows:
        sections.append({
            "section_id": s.section_id, "section_number": s.section_number,
            "semester": sem, "instructor_name": s.instructor_name,
            "capacity": s.capacity, "status": s.status,
            "enrolled": await _enrolled_count(s.section_id, db),
        })
    return {
        "course_id": c.course_id, "code": c.code, "name": c.name, "credits": c.credits,
        "description": c.description, "major_code": c.major_code,
        "lecture_hours": c.lecture_hours, "lab_hours": c.lab_hours,
        "sections": sections,
    }


@router.patch("/courses/{course_id}")
async def update_course(
    course_id: int,
    patch: CourseUpdate,
    staff: Staff = Depends(require_role(StaffRole.registrar)),
    db: AsyncSession = Depends(get_db),
):
    c = await db.get(Course, course_id)
    if not c:
        raise HTTPException(status_code=404, detail="Course not found")
    before, after = {}, {}
    for field, value in patch.model_dump(exclude_unset=True).items():
        old = getattr(c, field)
        if old != value:
            before[field], after[field] = old, value
            setattr(c, field, value)
    if not after:
        return {"updated": False, "message": "No changes"}
    await log_action(
        db, action="course.update", entity_type="course", entity_id=str(course_id),
        actor_id=str(staff.staff_id), actor_role=staff.role, before=before, after=after,
    )
    await db.commit()
    return {"updated": True, "changed": list(after.keys())}


@router.patch("/sections/{section_id}")
async def update_section(
    section_id: int,
    patch: SectionUpdate,
    staff: Staff = Depends(require_role(StaffRole.registrar)),
    db: AsyncSession = Depends(get_db),
):
    s = await db.get(Section, section_id)
    if not s:
        raise HTTPException(status_code=404, detail="Section not found")
    before, after = {}, {}
    for field, value in patch.model_dump(exclude_unset=True).items():
        old = getattr(s, field)
        if old != value:
            before[field], after[field] = old, value
            setattr(s, field, value)
    if not after:
        return {"updated": False, "message": "No changes"}
    await log_action(
        db, action="section.update", entity_type="section", entity_id=str(section_id),
        actor_id=str(staff.staff_id), actor_role=staff.role, before=before, after=after,
    )
    await db.commit()
    return {"updated": True, "changed": list(after.keys())}


@router.post("/courses/{course_id}/sections")
async def create_section(
    course_id: int,
    body: SectionCreate,
    staff: Staff = Depends(require_role(StaffRole.registrar)),
    db: AsyncSession = Depends(get_db),
):
    c = await db.get(Course, course_id)
    if not c:
        raise HTTPException(status_code=404, detail="Course not found")
    if not await db.get(Semester, body.semester_id):
        raise HTTPException(status_code=400, detail="Unknown semester")

    s = Section(
        semester_id=body.semester_id, section_number=body.section_number,
        capacity=body.capacity, status=body.status,
        course_code=c.code, instructor_name=body.instructor_name,
    )
    db.add(s)
    await db.flush()
    await log_action(
        db, action="section.create", entity_type="section", entity_id=str(s.section_id),
        actor_id=str(staff.staff_id), actor_role=staff.role,
        after={"course_code": c.code, "section_number": body.section_number, "semester_id": body.semester_id},
    )
    await db.commit()
    return {"created": True, "section_id": s.section_id}


@router.get("/semesters")
async def list_semesters(
    staff: Staff = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(select(Semester).order_by(Semester.semester_id.desc()))
    ).scalars().all()
    return {"semesters": [{"semester_id": s.semester_id, "code": s.code} for s in rows]}
