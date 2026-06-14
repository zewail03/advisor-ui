import asyncio
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_db
from core.security import get_current_student
from models.financial import FinancialAccount, FinancialTransaction, Scholarship
from models.student import Student
from services.audit_service import log_action
from services.stripe_gateway import (
    create_checkout_session,
    retrieve_session,
    stripe_enabled,
)

router = APIRouter()


def _recompute(acc: FinancialAccount) -> None:
    """Same balance invariant the admin flow enforces."""
    acc.total_charges = (acc.tuition_fee or 0) + (acc.transportation_fee or 0) + (acc.fines or 0)
    acc.current_balance = acc.total_charges - (acc.scholarship_credit or 0) - (acc.payments_made or 0)
    acc.payment_status = "Paid" if acc.current_balance <= 0 else "Due"
    acc.last_updated = datetime.utcnow()


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


# ----------------------------- online payment (Stripe) ----------------------------- #

class ConfirmIn(BaseModel):
    session_id: str


@router.get("/payment-config")
async def payment_config(student: Student = Depends(get_current_student)):
    """Tells the UI whether a real gateway is wired up (test mode)."""
    return {"enabled": stripe_enabled(), "mode": "test"}


@router.post("/checkout")
async def create_checkout(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Create a Stripe Checkout Session for the student's outstanding balance and
    return the hosted-checkout URL to redirect to."""
    if not stripe_enabled():
        raise HTTPException(status_code=503, detail="Online payment is not configured yet.")
    acc = await _latest_account(student.student_id, db)
    if not acc or (acc.current_balance or 0) <= 0:
        raise HTTPException(status_code=400, detail="You have no outstanding balance to pay.")

    currency = (settings.stripe_currency or acc.currency or "egp").lower()
    amount_minor = int(round((acc.current_balance or 0) * 100))  # piasters
    base = settings.frontend_base_url.rstrip("/")

    try:
        session = await asyncio.to_thread(
            create_checkout_session,
            amount_minor=amount_minor,
            currency=currency,
            product_name=f"AIU Tuition — {acc.semester_code or 'Current term'}",
            description=f"{student.full_name} · {student.student_code}",
            success_url=f"{base}/financial-account?paid=1&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{base}/financial-account?canceled=1",
            metadata={
                "student_id": str(student.student_id),
                "student_code": student.student_code,
                "semester": acc.semester_code or "",
                "balance": str(acc.current_balance),
            },
            customer_email=getattr(student, "email", None),
        )
    except Exception as e:  # pragma: no cover - surfaces gateway/config errors to the UI
        raise HTTPException(status_code=502, detail=f"Payment gateway error: {e}")

    return {"url": session.url, "session_id": session.id, "amount": acc.current_balance, "currency": currency}


@router.post("/checkout/confirm")
async def confirm_checkout(
    body: ConfirmIn,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Verify a returned Checkout Session was paid, then record the payment ONCE
    and re-apply the balance invariant. Idempotent on the Stripe session id."""
    if not stripe_enabled():
        raise HTTPException(status_code=503, detail="Online payment is not configured yet.")
    session_id = (body.session_id or "").strip()
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing session id.")

    acc = await _latest_account(student.student_id, db)

    # already recorded? (idempotency — Stripe id stored as the txn reference)
    existing = (
        await db.execute(
            select(FinancialTransaction).where(FinancialTransaction.reference == session_id)
        )
    ).scalars().first()
    if existing:
        return {
            "paid": True,
            "already_recorded": True,
            "new_balance": acc.current_balance if acc else 0,
            "status": acc.payment_status if acc else None,
        }

    try:
        session = await asyncio.to_thread(retrieve_session, session_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Could not verify payment: {e}")

    if str((session.get("metadata") or {}).get("student_id")) != str(student.student_id):
        raise HTTPException(status_code=403, detail="This payment session does not belong to you.")
    if session.get("payment_status") != "paid":
        return {"paid": False, "status": session.get("payment_status")}
    if not acc:
        raise HTTPException(status_code=404, detail="No financial account found.")

    amount = int(round((session.get("amount_total") or 0) / 100))
    before = acc.current_balance
    acc.payments_made = (acc.payments_made or 0) + amount
    _recompute(acc)
    db.add(FinancialTransaction(
        id=str(uuid4()), student_id=student.student_id,
        transaction_ref=f"PAY-{session_id[-10:].upper()}",
        semester_code=acc.semester_code, date=datetime.utcnow().strftime("%Y-%m-%d"),
        type="payment", category="Card (Stripe)", description="Online card payment via Stripe",
        amount=amount, currency=acc.currency, status="Posted", reference=session_id,
    ))
    await log_action(
        db, action="financial.payment", entity_type="financial_account",
        entity_id=str(student.student_id), actor_id=str(student.student_id), actor_role="student",
        subject_student_id=str(student.student_id),
        before={"balance": before},
        after={"balance": acc.current_balance, "amount": amount, "gateway": "stripe"},
    )
    await db.commit()
    return {"paid": True, "amount": amount, "new_balance": acc.current_balance, "status": acc.payment_status}
