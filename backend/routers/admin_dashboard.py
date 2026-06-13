"""Admin overview dashboard — read-only aggregates from real data.

Any authenticated staff (incl. read-only) may view.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_staff
from models.advisor import AdvisorApproval
from models.course import Section
from models.financial import FinancialAccount
from models.petitions import Petition
from models.staff import Staff
from models.student import Student
from services.policy import get_policy

router = APIRouter()


async def _scalar(db: AsyncSession, stmt) -> int:
    return int((await db.execute(stmt)).scalar() or 0)


@router.get("/overview")
async def overview(
    staff: Staff = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    at_risk_cgpa = await get_policy("standing.at_risk_cgpa", db)
    total_students = await _scalar(db, select(func.count()).select_from(Student))
    active_students = await _scalar(
        db, select(func.count()).select_from(Student).where(Student.status == "Active")
    )
    at_risk = await _scalar(
        db, select(func.count()).select_from(Student).where(Student.cgpa < at_risk_cgpa)
    )
    open_sections = await _scalar(
        db, select(func.count()).select_from(Section).where(Section.status == "Open")
    )
    outstanding = await _scalar(
        db,
        select(func.coalesce(func.sum(FinancialAccount.current_balance), 0)).where(
            FinancialAccount.current_balance > 0
        ),
    )
    pending_petitions = await _scalar(
        db,
        select(func.count()).select_from(Petition).where(Petition.status == "submitted"),
    )
    pending_approvals = await _scalar(
        db,
        select(func.count())
        .select_from(AdvisorApproval)
        .where(AdvisorApproval.status == "pending"),
    )

    return {
        "students": {"total": total_students, "active": active_students, "at_risk": at_risk},
        "sections": {"open": open_sections},
        "financial": {"total_outstanding": outstanding, "currency": "EGP"},
        "queues": {
            "pending_petitions": pending_petitions,
            "pending_advisor_approvals": pending_approvals,
        },
        "viewer": {"name": staff.full_name, "role": staff.role},
    }


@router.get("/students/at-risk")
async def at_risk_students(
    limit: int = 50,
    staff: Staff = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    """List the lowest-CGPA students — the registrar's intervention queue."""
    at_risk_cgpa = await get_policy("standing.at_risk_cgpa", db)
    rows = (
        await db.execute(
            select(
                Student.student_id,
                Student.student_code,
                Student.full_name,
                Student.cgpa,
                Student.status,
            )
            .where(Student.cgpa < at_risk_cgpa)
            .order_by(Student.cgpa.asc())
            .limit(min(limit, 200))
        )
    ).all()
    return {
        "count": len(rows),
        "students": [
            {
                "student_id": sid,
                "student_code": code,
                "full_name": name,
                "cgpa": round(cgpa, 3) if cgpa is not None else None,
                "status": st,
            }
            for (sid, code, name, cgpa, st) in rows
        ],
    }
