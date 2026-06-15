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
from services.risk_model import model_info, predict_risk

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


@router.get("/risk-model")
async def risk_model_card(
    staff: Staff = Depends(get_current_staff),
):
    """Metadata + held-out metrics for the trained early-warning model."""
    info = model_info()
    return {"available": info is not None, "model": info}


@router.get("/students/risk-predictions")
async def risk_predictions(
    limit: int = 25,
    staff: Staff = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    """ML-ranked intervention queue: predicted academic risk for every student
    still in the program (Active/Probation), highest first. Unlike the CGPA list
    this surfaces students whose *current* CGPA may still look acceptable but
    whose first-year signals predict trouble — i.e. it catches them earlier."""
    info = model_info()
    if info is None:
        return {"available": False, "model": None, "students": [], "band_counts": {}}

    rows = (
        await db.execute(
            select(
                Student.student_id,
                Student.student_code,
                Student.full_name,
                Student.cgpa,
                Student.status,
                Student.level,
            ).where(Student.status.in_(["Active", "Probation"]))
        )
    ).all()

    preds = []
    band_counts = {"high": 0, "moderate": 0, "low": 0}
    for sid, code, name, cgpa, status, level in rows:
        r = await predict_risk(sid, db)
        if not r:
            continue
        band_counts[r["risk_band"]] = band_counts.get(r["risk_band"], 0) + 1
        top = r["factors"][0]["label"] if r["factors"] else "—"
        preds.append({
            "student_id": sid,
            "student_code": code,
            "full_name": name,
            "cgpa": round(cgpa, 3) if cgpa is not None else None,
            "status": status,
            "level": level,
            "risk_score": r["risk_score"],
            "risk_band": r["risk_band"],
            "horizon": r["horizon"],
            "top_factor": top,
        })

    preds.sort(key=lambda d: -d["risk_score"])
    return {
        "available": True,
        "model": info,
        "scored": len(preds),
        "band_counts": band_counts,
        "students": preds[: min(limit, 100)],
    }
