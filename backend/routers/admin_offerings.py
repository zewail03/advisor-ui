"""Admin course offerings / schedule builder.

Lets the registrar decide which courses are offered in a given semester and
build each section's schedule (lecture/lab/tutorial meetings with day + time).
Reads open to any staff; writes role-guarded + audited.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_staff, require_role
from models.academic import Semester
from models.course import Course, Section, SectionMeeting
from models.enrollment import Enrollment
from models.room import Room
from models.staff import Staff, StaffRole
from services.audit_service import log_action

router = APIRouter()

_ENROLLED = ("Enrolled", "Satisfied")


class MeetingIn(BaseModel):
    meeting_type: str = "Lecture"  # Lecture | Lab | Tutorial
    day_of_week: str
    start_time: str
    end_time: str
    location: Optional[str] = None


class OfferingIn(BaseModel):
    semester_id: int
    course_id: int
    section_number: str
    instructor_name: Optional[str] = None
    capacity: int = 30
    status: str = "Open"
    meetings: List[MeetingIn] = []


class MeetingsUpdate(BaseModel):
    meetings: List[MeetingIn] = []


class SemesterIn(BaseModel):
    code: str
    type: Optional[str] = None
    year_start: Optional[int] = None
    year_end: Optional[int] = None


class RoomIn(BaseModel):
    name: str
    room_type: str = "lecture"  # lab | lecture
    capacity: Optional[int] = None


async def _meetings_for(section_id: int, db: AsyncSession) -> list:
    rows = (
        await db.execute(
            select(SectionMeeting).where(SectionMeeting.section_id == section_id).order_by(SectionMeeting.meeting_id)
        )
    ).scalars().all()
    return [
        {"meeting_id": m.meeting_id, "meeting_type": m.meeting_type, "day_of_week": m.day_of_week,
         "start_time": m.start_time, "end_time": m.end_time, "location": m.location}
        for m in rows
    ]


async def _enrolled(section_id: int, db: AsyncSession) -> int:
    return int((await db.execute(
        select(func.count()).select_from(Enrollment)
        .where(Enrollment.section_id == section_id, Enrollment.status.in_(_ENROLLED))
    )).scalar() or 0)


@router.get("/course-options")
async def course_options(
    staff: Staff = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(select(Course.course_id, Course.code, Course.name).order_by(Course.code))).all()
    return {"courses": [{"course_id": cid, "code": code, "name": name} for (cid, code, name) in rows]}


@router.get("/rooms")
async def list_rooms(
    staff: Staff = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(Room).where(Room.is_active == True).order_by(Room.room_type, Room.name)  # noqa: E712
        )
    ).scalars().all()
    return {
        "rooms": [
            {"room_id": r.room_id, "name": r.name, "room_type": r.room_type, "capacity": r.capacity}
            for r in rows
        ]
    }


@router.post("/rooms")
async def create_room(
    body: RoomIn,
    staff: Staff = Depends(require_role(StaffRole.registrar)),
    db: AsyncSession = Depends(get_db),
):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Room name is required")
    exists = (await db.execute(select(Room).where(Room.name == name))).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="A room with that name already exists")
    room = Room(name=name, room_type=body.room_type, capacity=body.capacity, is_active=True)
    db.add(room)
    await db.flush()
    await log_action(db, action="room.create", entity_type="room", entity_id=str(room.room_id),
                     actor_id=str(staff.staff_id), actor_role=staff.role,
                     after={"name": name, "room_type": body.room_type})
    await db.commit()
    return {"created": True, "room_id": room.room_id, "name": room.name}


@router.get("/offerings")
async def list_offerings(
    semester_id: int = Query(...),
    staff: Staff = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    sem = await db.get(Semester, semester_id)
    if not sem:
        raise HTTPException(status_code=404, detail="Semester not found")
    rows = (
        await db.execute(
            select(Section, Course.name)
            .join(Course, Course.code == Section.course_code)
            .where(Section.semester_id == semester_id)
            .order_by(Section.course_code, Section.section_number)
        )
    ).all()
    offerings = []
    for s, cname in rows:
        offerings.append({
            "section_id": s.section_id, "course_code": s.course_code, "course_title": cname,
            "section_number": s.section_number, "instructor_name": s.instructor_name,
            "capacity": s.capacity, "status": s.status,
            "enrolled": await _enrolled(s.section_id, db),
            "meetings": await _meetings_for(s.section_id, db),
        })
    return {"semester": {"semester_id": sem.semester_id, "code": sem.code}, "offerings": offerings}


@router.post("/semesters")
async def create_semester(
    body: SemesterIn,
    staff: Staff = Depends(require_role(StaffRole.registrar)),
    db: AsyncSession = Depends(get_db),
):
    exists = (await db.execute(select(Semester).where(Semester.code == body.code.strip()))).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="A semester with that code already exists")
    sem = Semester(code=body.code.strip(), type=body.type, year_start=body.year_start, year_end=body.year_end)
    db.add(sem)
    await db.flush()
    await log_action(db, action="semester.create", entity_type="semester", entity_id=str(sem.semester_id),
                     actor_id=str(staff.staff_id), actor_role=staff.role, after={"code": sem.code})
    await db.commit()
    return {"created": True, "semester_id": sem.semester_id, "code": sem.code}


@router.post("/offerings")
async def create_offering(
    body: OfferingIn,
    staff: Staff = Depends(require_role(StaffRole.registrar)),
    db: AsyncSession = Depends(get_db),
):
    course = await db.get(Course, body.course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    if not await db.get(Semester, body.semester_id):
        raise HTTPException(status_code=400, detail="Unknown semester")

    s = Section(
        semester_id=body.semester_id, section_number=body.section_number,
        capacity=body.capacity, status=body.status,
        course_code=course.code, instructor_name=body.instructor_name,
    )
    db.add(s)
    await db.flush()
    for m in body.meetings:
        db.add(SectionMeeting(
            section_id=s.section_id, meeting_type=m.meeting_type, day_of_week=m.day_of_week,
            start_time=m.start_time, end_time=m.end_time, location=m.location,
        ))
    await log_action(db, action="offering.create", entity_type="section", entity_id=str(s.section_id),
                     actor_id=str(staff.staff_id), actor_role=staff.role,
                     after={"course": course.code, "section": body.section_number,
                            "semester_id": body.semester_id, "meetings": len(body.meetings)})
    await db.commit()
    return {"created": True, "section_id": s.section_id}


@router.put("/sections/{section_id}/meetings")
async def set_meetings(
    section_id: int,
    body: MeetingsUpdate,
    staff: Staff = Depends(require_role(StaffRole.registrar)),
    db: AsyncSession = Depends(get_db),
):
    s = await db.get(Section, section_id)
    if not s:
        raise HTTPException(status_code=404, detail="Section not found")
    existing = (await db.execute(select(SectionMeeting).where(SectionMeeting.section_id == section_id))).scalars().all()
    for m in existing:
        await db.delete(m)
    for m in body.meetings:
        db.add(SectionMeeting(
            section_id=section_id, meeting_type=m.meeting_type, day_of_week=m.day_of_week,
            start_time=m.start_time, end_time=m.end_time, location=m.location,
        ))
    await log_action(db, action="section.meetings_update", entity_type="section", entity_id=str(section_id),
                     actor_id=str(staff.staff_id), actor_role=staff.role,
                     after={"meetings": len(body.meetings)})
    await db.commit()
    return {"updated": True, "meetings": len(body.meetings)}


@router.delete("/offerings/{section_id}")
async def delete_offering(
    section_id: int,
    staff: Staff = Depends(require_role(StaffRole.registrar)),
    db: AsyncSession = Depends(get_db),
):
    s = await db.get(Section, section_id)
    if not s:
        raise HTTPException(status_code=404, detail="Section not found")
    n = await _enrolled(section_id, db)
    if n > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete — {n} students enrolled. Set status to Cancelled instead.")
    await db.delete(s)  # cascades meetings
    await log_action(db, action="offering.delete", entity_type="section", entity_id=str(section_id),
                     actor_id=str(staff.staff_id), actor_role=staff.role,
                     before={"course": s.course_code, "section": s.section_number})
    await db.commit()
    return {"deleted": True}
