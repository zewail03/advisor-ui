"""Admin student management — list/search, view, edit, reset password.

Reads are open to any authenticated staff; writes require a write role
(super_admin / registrar) and are recorded in the audit log with before/after.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_staff, get_password_hash, require_role
from models.staff import Staff, StaffRole
from models.student import Major, Program, Student
from services.audit_service import log_action

router = APIRouter()

EDITABLE_FIELDS = ("full_name", "email", "phone", "status", "level", "program_id", "major_id")


class StudentUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    status: Optional[str] = None
    level: Optional[int] = None
    program_id: Optional[int] = None
    major_id: Optional[int] = None


class PasswordReset(BaseModel):
    new_password: Optional[str] = None  # defaults to the standard temp password


def _row(s: Student) -> dict:
    return {
        "student_id": s.student_id,
        "student_code": s.student_code,
        "full_name": s.full_name,
        "email": s.email,
        "phone": s.phone,
        "status": s.status,
        "level": s.level,
        "cgpa": round(s.cgpa, 3) if s.cgpa is not None else None,
        "program_id": s.program_id,
        "major_id": s.major_id,
    }


@router.get("/students")
async def list_students(
    q: Optional[str] = Query(None, description="search code or name"),
    status: Optional[str] = Query(None),
    limit: int = Query(25, le=100),
    offset: int = Query(0, ge=0),
    staff: Staff = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if q:
        like = f"%{q.strip()}%"
        filters.append(or_(Student.student_code.ilike(like), Student.full_name.ilike(like)))
    if status:
        filters.append(Student.status == status)

    total = int(
        (await db.execute(select(func.count()).select_from(Student).where(*filters))).scalar() or 0
    )
    rows = (
        await db.execute(
            select(Student).where(*filters).order_by(Student.student_code).limit(limit).offset(offset)
        )
    ).scalars().all()
    return {"total": total, "limit": limit, "offset": offset, "students": [_row(s) for s in rows]}


@router.get("/students/{student_id}")
async def get_student(
    student_id: int,
    staff: Staff = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    s = await db.get(Student, student_id)
    if not s:
        raise HTTPException(status_code=404, detail="Student not found")
    program = await db.get(Program, s.program_id) if s.program_id else None
    major = await db.get(Major, s.major_id) if s.major_id else None
    data = _row(s)
    data["program_name"] = program.name if program else None
    data["major_name"] = major.name if major else None
    return data


@router.patch("/students/{student_id}")
async def update_student(
    student_id: int,
    patch: StudentUpdate,
    staff: Staff = Depends(require_role(StaffRole.registrar)),
    db: AsyncSession = Depends(get_db),
):
    s = await db.get(Student, student_id)
    if not s:
        raise HTTPException(status_code=404, detail="Student not found")

    changes = patch.model_dump(exclude_unset=True)
    before, after = {}, {}
    for field, value in changes.items():
        if field not in EDITABLE_FIELDS:
            continue
        old = getattr(s, field)
        if old != value:
            before[field] = old
            after[field] = value
            setattr(s, field, value)

    if not after:
        return {"updated": False, "message": "No changes", "student": _row(s)}

    await log_action(
        db,
        action="student.update",
        entity_type="student",
        entity_id=str(student_id),
        actor_id=str(staff.staff_id),
        actor_role=staff.role,
        subject_student_id=str(student_id),
        before=before,
        after=after,
    )
    await db.commit()
    await db.refresh(s)
    return {"updated": True, "changed": list(after.keys()), "student": _row(s)}


@router.post("/students/{student_id}/reset-password")
async def reset_password(
    student_id: int,
    body: PasswordReset,
    staff: Staff = Depends(require_role(StaffRole.registrar)),
    db: AsyncSession = Depends(get_db),
):
    s = await db.get(Student, student_id)
    if not s:
        raise HTTPException(status_code=404, detail="Student not found")
    new_password = (body.new_password or "changeme123").strip() or "changeme123"
    s.hashed_password = get_password_hash(new_password)
    await log_action(
        db,
        action="student.reset_password",
        entity_type="student",
        entity_id=str(student_id),
        actor_id=str(staff.staff_id),
        actor_role=staff.role,
        subject_student_id=str(student_id),
        after={"password_reset": True},
    )
    await db.commit()
    return {"success": True, "student_code": s.student_code, "temporary_password": new_password}
