from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_student
from models.student import Student
from schemas.enrollment import GpaRequiredRequest, GpaSimulateRequest
from services.gpa_calculator import required_grades_for_target, simulate_cgpa

router = APIRouter()


@router.post("/simulate")
async def simulate(
    req: GpaSimulateRequest,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    return await simulate_cgpa(
        student_id=student.student_id,
        scenarios=[s.model_dump() for s in req.scenarios],
        db=db,
    )


@router.post("/required")
async def required_grades(
    req: GpaRequiredRequest,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    return await required_grades_for_target(
        student_id=student.student_id,
        target_cgpa=req.target_cgpa,
        course_codes=req.course_codes,
        db=db,
    )
