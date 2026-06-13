from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_student
from models.financial import FinancialAccount, FinancialTransaction, Scholarship
from models.student import Student

router = APIRouter()


async def _latest_account(student_id: int, db: AsyncSession, semester: Optional[str] = None):
    stmt = select(FinancialAccount).where(FinancialAccount.student_id == student_id)
    if semester:
        stmt = stmt.where(FinancialAccount.semester_code == semester)
    stmt = stmt.order_by(FinancialAccount.last_updated.desc())
    result = await db.execute(stmt)
    return result.scalars().first()


@router.get("/balance")
async def get_balance(
    semester: Optional[str] = Query(None),
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    acc = await _latest_account(student.student_id, db, semester)
    if not acc:
        return {"balance": 0, "semester": None, "due_date": None, "payment_status": None, "currency": "EGP"}
    return {
        "balance": acc.current_balance,
        "semester": acc.semester_code,
        "due_date": acc.payment_due_date,
        "payment_status": acc.payment_status,
        "currency": acc.currency,
        "total_charges": acc.total_charges,
        "payments_made": acc.payments_made,
        "scholarship_credit": acc.scholarship_credit,
        "tuition_fee": acc.tuition_fee,
        "transportation_fee": acc.transportation_fee,
        "fines": acc.fines,
    }


@router.get("/invoices")
async def get_invoices(
    semester: Optional[str] = Query(None),
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(FinancialTransaction).where(
        and_(
            FinancialTransaction.student_id == student.student_id,
            FinancialTransaction.type.in_(("charge", "fine", "scholarship")),
        )
    )
    if semester:
        stmt = stmt.where(FinancialTransaction.semester_code == semester)
    result = await db.execute(stmt.order_by(FinancialTransaction.date.desc()))
    return [
        {
            "id": t.id,
            "reference": t.transaction_ref,
            "semester": t.semester_code,
            "date": t.date,
            "description": t.description,
            "category": t.category,
            "type": t.type,
            "amount": t.amount,
            "currency": t.currency,
            "status": t.status,
        }
        for t in result.scalars().all()
    ]


@router.get("/payment-history")
async def payment_history(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(FinancialTransaction).where(
            and_(
                FinancialTransaction.student_id == student.student_id,
                FinancialTransaction.type == "payment",
            )
        ).order_by(FinancialTransaction.date.desc())
    )
    return [
        {
            "id": t.id,
            "date": t.date,
            "amount": t.amount,
            "currency": t.currency,
            "method": t.category or "Cash",
            "reference": t.reference or t.transaction_ref,
            "status": t.status,
        }
        for t in result.scalars().all()
    ]


@router.get("/scholarships")
async def get_scholarships(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Scholarship).where(Scholarship.student_id == student.student_id)
    )
    return [
        {
            "id": s.id,
            "reference": s.scholarship_ref,
            "semester": s.semester_code,
            "type": s.scholarship_type,
            "percentage": s.percentage,
            "amount": s.amount,
            "status": s.status,
            "criteria_basis": s.criteria_basis,
            "cgpa_at_award": s.cgpa_at_award,
        }
        for s in result.scalars().all()
    ]
