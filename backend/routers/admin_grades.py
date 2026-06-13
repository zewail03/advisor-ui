"""Admin grade management — view a student's grades and edit a grade.

Editing a grade is the highest-stakes action in the system: it recomputes
grade points + the student's cumulative CGPA and is fully audited (before/after
letter, points, and CGPA). Writes require a write role.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_staff, require_role
from models.academic import Semester
from models.course import Course, Section
from models.enrollment import Enrollment, GRADE_POINTS, Grade
from models.staff import Staff, StaffRole
from models.student import Student
from services.audit_service import log_action
from services.gpa_calculator import recompute_and_store_cgpa

router = APIRouter()

# letters an admin may assign (order = best→worst, for UI dropdowns)
VALID_LETTERS = ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "F", "FW", "W", "I", "S", "U"]


class GradeUpdate(BaseModel):
    grade_letter: str


@router.get("/students/{student_id}/grades")
async def student_grades(
    student_id: int,
    staff: Staff = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    student = await db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    rows = (
        await db.execute(
            select(
                Grade.grade_id,
                Grade.grade_letter,
                Grade.grade_points,
                Grade.percentage,
                Grade.counts_in_gpa,
                Course.code,
                Course.name,
                Course.credits,
                Semester.code,
            )
            .select_from(Grade)
            .join(Enrollment, Enrollment.enrollment_id == Grade.enrollment_id)
            .join(Section, Section.section_id == Enrollment.section_id)
            .join(Course, Course.code == Section.course_code)
            .join(Semester, Semester.semester_id == Section.semester_id)
            .where(Enrollment.student_id == student_id)
            .order_by(Semester.semester_id.desc(), Course.code)
        )
    ).all()

    return {
        "student": {
            "student_id": student.student_id,
            "student_code": student.student_code,
            "full_name": student.full_name,
            "cgpa": round(student.cgpa, 3) if student.cgpa is not None else None,
        },
        "grades": [
            {
                "grade_id": gid,
                "course_code": ccode,
                "course_title": cname,
                "credits": credits,
                "semester": sem,
                "grade_letter": letter,
                "grade_points": pts,
                "percentage": pct,
                "counts_in_gpa": bool(counts),
            }
            for (gid, letter, pts, pct, counts, ccode, cname, credits, sem) in rows
        ],
    }


@router.patch("/grades/{grade_id}")
async def update_grade(
    grade_id: int,
    body: GradeUpdate,
    staff: Staff = Depends(require_role(StaffRole.registrar)),
    db: AsyncSession = Depends(get_db),
):
    letter = body.grade_letter.strip().upper()
    if letter not in GRADE_POINTS:
        raise HTTPException(status_code=400, detail=f"Invalid grade letter '{letter}'")

    grade = await db.get(Grade, grade_id)
    if not grade:
        raise HTTPException(status_code=404, detail="Grade not found")

    enrollment = await db.get(Enrollment, grade.enrollment_id)
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    student_id = enrollment.student_id

    student = await db.get(Student, student_id)
    old = {
        "grade_letter": grade.grade_letter,
        "grade_points": grade.grade_points,
        "cgpa": round(student.cgpa, 3) if student and student.cgpa is not None else None,
    }

    new_points = GRADE_POINTS[letter]
    grade.grade_letter = letter
    grade.grade_points = new_points
    grade.counts_in_gpa = new_points is not None  # W/I/S/U don't count
    grade.grade_date = datetime.utcnow()

    new_cgpa = await recompute_and_store_cgpa(student_id, db)

    after = {"grade_letter": letter, "grade_points": new_points, "cgpa": new_cgpa}
    await log_action(
        db,
        action="grade.update",
        entity_type="grade",
        entity_id=str(grade_id),
        actor_id=str(staff.staff_id),
        actor_role=staff.role,
        subject_student_id=str(student_id),
        before=old,
        after=after,
    )
    await db.commit()
    return {
        "updated": True,
        "grade_id": grade_id,
        "student_id": student_id,
        "old_letter": old["grade_letter"],
        "new_letter": letter,
        "old_cgpa": old["cgpa"],
        "new_cgpa": new_cgpa,
    }
