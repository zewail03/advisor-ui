"""Enrollment HTTP surface.

Rewritten for the real AIU schema:
  * section_id / enrollment_id are integers now.
  * Section has no `days/time_start/time_end/room/instructor`; we look at
    SectionMeeting rows and concatenate a human summary.
  * Enrollment has no `semester_code`; we scope by Section.semester_id
    resolved from the optional `semester` query param via Semester.code.
  * Waitlist is counted from live rows (no Section.waitlist_count column).
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.database import get_db
from core.security import get_current_student
from core.websocket import ws_manager
from models.academic import Semester
from models.course import Course, Section
from models.enrollment import Enrollment, Waitlist
from models.student import Student
from schemas.enrollment import (
    BulkEnrollRequest,
    EnrollRequest,
    EnrollResult,
    WaitlistJoinRequest,
)
from services.enrollment_service import drop_enrollment, enroll_single
from services.withdrawal_service import process_drop_or_withdraw

router = APIRouter()


def _format_meetings(meetings) -> dict:
    if not meetings:
        return {"days": "", "time_start": "", "time_end": "", "room": ""}
    days = ",".join(m.day_of_week for m in meetings if m.day_of_week)
    starts = [m.start_time for m in meetings if m.start_time]
    ends = [m.end_time for m in meetings if m.end_time]
    rooms = [m.location for m in meetings if m.location]
    return {
        "days": days,
        "time_start": starts[0] if starts else "",
        "time_end": ends[0] if ends else "",
        "room": rooms[0] if rooms else "",
    }


@router.get("/me/schedule")
async def my_schedule(
    semester: Optional[str] = Query(None),
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    semester_id: Optional[int] = None
    semester_code: str = ""
    if semester:
        sem_row = await db.execute(select(Semester).where(Semester.code == semester))
        sem = sem_row.scalar_one_or_none()
        if sem:
            semester_id = sem.semester_id
            semester_code = sem.code

    stmt = (
        select(Enrollment, Section, Course, Semester)
        .join(Section, Section.section_id == Enrollment.section_id)
        .join(Course, Course.code == Section.course_code)
        .join(Semester, Semester.semester_id == Section.semester_id)
        .options(selectinload(Section.meetings))
        .where(
            and_(
                Enrollment.student_id == student.student_id,
                Enrollment.status.in_(("Enrolled", "Satisfied")),
            )
        )
    )
    if semester_id is not None:
        stmt = stmt.where(Section.semester_id == semester_id)
    rows = (await db.execute(stmt)).unique().all()

    out = []
    for enrollment, section, course, sem in rows:
        meeting_fields = _format_meetings(section.meetings)
        out.append(
            {
                "enrollment_id": enrollment.enrollment_id,
                "section_id": section.section_id,
                "course_code": course.code,
                "course_title": course.name,
                "credits": course.credits,
                "section_number": section.section_number,
                "semester": sem.code,
                "instructor": section.instructor_name or "",
                "status": enrollment.status,
                **meeting_fields,
            }
        )
    return {"schedule": out, "semester": semester_code or semester or ""}


@router.post("", response_model=EnrollResult)
async def enroll(
    req: EnrollRequest,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    result = await enroll_single(student.student_id, int(req.section_id), db)
    return EnrollResult(**result)


@router.post("/bulk")
async def bulk_enroll(
    req: BulkEnrollRequest,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    results = []
    for raw_section_id in req.section_ids:
        section_id = int(raw_section_id)
        await ws_manager.send_to_student(
            str(student.student_id),
            {"type": "enrollment_start", "section_id": section_id},
        )
        result = await enroll_single(student.student_id, section_id, db)
        await ws_manager.send_to_student(
            str(student.student_id),
            {"type": "enrollment_result", **result},
        )
        results.append(result)
    return {"results": results}


@router.post("/dry-run")
async def dry_run(
    req: BulkEnrollRequest,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Simulate bulk enrollment without committing."""
    results = []
    for raw_section_id in req.section_ids:
        result = await enroll_single(student.student_id, int(raw_section_id), db, commit=False)
        results.append(result)
    await db.rollback()
    return {"results": results}


@router.delete("/{enrollment_id}")
async def drop(
    enrollment_id: int,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Simple drop fallback for callers not using the phased workflow."""
    result = await drop_enrollment(student.student_id, enrollment_id, db)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    return result


@router.post("/{enrollment_id}/withdraw")
async def withdraw(
    enrollment_id: int,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Week-phased drop/withdrawal per §6 (assigns W grade, computes refund %)."""
    enrollment = await db.get(Enrollment, int(enrollment_id))
    freed_section_id = enrollment.section_id if enrollment else None
    result = await process_drop_or_withdraw(student.student_id, enrollment_id, db)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["message"])
    # the freed seat goes to the head of the waitlist automatically
    if freed_section_id:
        from services.waitlist_service import promote_for_section

        promoted = await promote_for_section(freed_section_id, db)
        await db.commit()
        result["waitlist_promotions"] = promoted
    return result


@router.post("/waitlist")
async def join_waitlist(
    req: WaitlistJoinRequest,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    section_id = int(req.section_id)
    section = await db.get(Section, section_id)
    if not section:
        raise HTTPException(status_code=404, detail="Section not found")
    existing = await db.execute(
        select(Waitlist).where(
            and_(Waitlist.student_id == student.student_id, Waitlist.section_id == section_id)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Already on waitlist")

    # Waitlist order is NOT first-come-first-served: students on the normal
    # study plan outrank retakes, which outrank fast-trackers (see
    # services.registration_priority for the 4-tier rule).
    from services.waitlist_service import add_to_waitlist

    info = await add_to_waitlist(student, section, db)
    await db.commit()
    return {"message": "Added to waitlist", **info}


@router.delete("/waitlist/{waitlist_id}")
async def leave_waitlist(
    waitlist_id: int,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    entry = await db.get(Waitlist, int(waitlist_id))
    if not entry or entry.student_id != student.student_id:
        raise HTTPException(status_code=404, detail="Waitlist entry not found")
    await db.delete(entry)
    await db.commit()
    return {"message": "Removed from waitlist"}
