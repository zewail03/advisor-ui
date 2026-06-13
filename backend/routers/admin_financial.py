"""Admin financial management — view account, post payments, add fines,
grant/revoke scholarships.

The account invariant is enforced on every write:
    current_balance = total_charges - scholarship_credit - payments_made
…and payment_status is recomputed. All writes are role-guarded and audited.
"""
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import func

from core.database import get_db
from core.security import get_current_staff, require_role
from models.course import Course, Section
from models.enrollment import Enrollment
from models.financial import FinancialAccount, FinancialTransaction, Scholarship
from models.staff import Staff, StaffRole
from models.student import Student
from services.audit_service import log_action
from services.policy import get_policy

router = APIRouter()


class PaymentIn(BaseModel):
    amount: int
    method: str = "Cash"
    reference: Optional[str] = None


class FineIn(BaseModel):
    amount: int  # positive = extra charge (fine), negative = waiver/discount
    description: str = "Manual adjustment"


class ScholarshipIn(BaseModel):
    scholarship_type: str
    amount: int
    notes: Optional[str] = None


def _ref(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8].upper()}"


def _recompute(acc: FinancialAccount) -> None:
    acc.total_charges = (acc.tuition_fee or 0) + (acc.transportation_fee or 0) + (acc.fines or 0)
    acc.current_balance = acc.total_charges - (acc.scholarship_credit or 0) - (acc.payments_made or 0)
    acc.payment_status = "Paid" if acc.current_balance <= 0 else "Due"
    acc.last_updated = datetime.utcnow()


async def _latest_account(student_id: int, db: AsyncSession) -> Optional[FinancialAccount]:
    return (
        await db.execute(
            select(FinancialAccount)
            .where(FinancialAccount.student_id == student_id)
            .order_by(FinancialAccount.last_updated.desc())
        )
    ).scalars().first()


def _acc_dict(a: FinancialAccount) -> dict:
    return {
        "semester": a.semester_code, "currency": a.currency,
        "tuition_fee": a.tuition_fee, "transportation_fee": a.transportation_fee,
        "fines": a.fines, "total_charges": a.total_charges,
        "scholarship_credit": a.scholarship_credit, "payments_made": a.payments_made,
        "current_balance": a.current_balance, "payment_status": a.payment_status,
        "payment_due_date": a.payment_due_date,
    }


@router.get("/students/{student_id}/financial")
async def get_financial(
    student_id: int,
    staff: Staff = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    student = await db.get(Student, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    acc = await _latest_account(student_id, db)
    txns = (
        await db.execute(
            select(FinancialTransaction)
            .where(FinancialTransaction.student_id == student_id)
            .order_by(FinancialTransaction.date.desc())
            .limit(50)
        )
    ).scalars().all()
    schols = (
        await db.execute(
            select(Scholarship).where(Scholarship.student_id == student_id)
        )
    ).scalars().all()
    return {
        "student": {"student_id": student.student_id, "student_code": student.student_code, "full_name": student.full_name},
        "account": _acc_dict(acc) if acc else None,
        "transactions": [
            {"id": t.id, "date": t.date, "type": t.type, "category": t.category,
             "description": t.description, "amount": t.amount, "status": t.status, "reference": t.reference}
            for t in txns
        ],
        "scholarships": [
            {"id": s.id, "type": s.scholarship_type, "percentage": s.percentage,
             "amount": s.amount, "status": s.status, "notes": s.notes}
            for s in schols
        ],
    }


async def _require_account(student_id: int, db: AsyncSession) -> FinancialAccount:
    acc = await _latest_account(student_id, db)
    if not acc:
        raise HTTPException(status_code=404, detail="No financial account for this student")
    return acc


@router.post("/students/{student_id}/financial/payment")
async def post_payment(
    student_id: int,
    body: PaymentIn,
    staff: Staff = Depends(require_role(StaffRole.registrar)),
    db: AsyncSession = Depends(get_db),
):
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    acc = await _require_account(student_id, db)
    before = acc.current_balance
    acc.payments_made = (acc.payments_made or 0) + body.amount
    _recompute(acc)
    db.add(FinancialTransaction(
        id=str(uuid4()), student_id=student_id, transaction_ref=_ref("PAY"),
        semester_code=acc.semester_code, date=datetime.utcnow().strftime("%Y-%m-%d"),
        type="payment", category=body.method, description=f"Payment via {body.method}",
        amount=body.amount, currency=acc.currency, status="Posted", reference=body.reference or "",
    ))
    await log_action(db, action="financial.payment", entity_type="financial_account",
        entity_id=str(student_id), actor_id=str(staff.staff_id), actor_role=staff.role,
        subject_student_id=str(student_id),
        before={"balance": before}, after={"balance": acc.current_balance, "amount": body.amount})
    await db.commit()
    return {"posted": True, "new_balance": acc.current_balance, "status": acc.payment_status}


@router.post("/students/{student_id}/financial/fine")
async def add_fine(
    student_id: int,
    body: FineIn,
    staff: Staff = Depends(require_role(StaffRole.registrar)),
    db: AsyncSession = Depends(get_db),
):
    acc = await _require_account(student_id, db)
    before = acc.current_balance
    acc.fines = (acc.fines or 0) + body.amount
    _recompute(acc)
    kind = "Fine" if body.amount >= 0 else "Waiver"
    db.add(FinancialTransaction(
        id=str(uuid4()), student_id=student_id, transaction_ref=_ref("ADJ"),
        semester_code=acc.semester_code, date=datetime.utcnow().strftime("%Y-%m-%d"),
        type="charge" if body.amount >= 0 else "credit", category=kind,
        description=body.description, amount=abs(body.amount), currency=acc.currency, status="Posted",
    ))
    await log_action(db, action="financial.adjustment", entity_type="financial_account",
        entity_id=str(student_id), actor_id=str(staff.staff_id), actor_role=staff.role,
        subject_student_id=str(student_id),
        before={"balance": before, "fines": acc.fines - body.amount},
        after={"balance": acc.current_balance, "fines": acc.fines, "kind": kind})
    await db.commit()
    return {"posted": True, "new_balance": acc.current_balance, "status": acc.payment_status}


@router.post("/students/{student_id}/financial/scholarship")
async def grant_scholarship(
    student_id: int,
    body: ScholarshipIn,
    staff: Staff = Depends(require_role(StaffRole.registrar)),
    db: AsyncSession = Depends(get_db),
):
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    acc = await _require_account(student_id, db)
    before = acc.current_balance
    ref = _ref("SCH")
    db.add(Scholarship(
        id=str(uuid4()), student_id=student_id, scholarship_ref=ref,
        semester_code=acc.semester_code, scholarship_type=body.scholarship_type,
        percentage=0, amount=body.amount, status="Active",
        criteria_basis="Admin grant", notes=body.notes or "",
    ))
    acc.scholarship_credit = (acc.scholarship_credit or 0) + body.amount
    _recompute(acc)
    db.add(FinancialTransaction(
        id=str(uuid4()), student_id=student_id, transaction_ref=ref + "-TXN",
        semester_code=acc.semester_code, date=datetime.utcnow().strftime("%Y-%m-%d"),
        type="scholarship", category="Scholarship", description=f"{body.scholarship_type} applied",
        amount=body.amount, currency=acc.currency, status="Posted", reference=ref,
    ))
    await log_action(db, action="financial.scholarship_grant", entity_type="financial_account",
        entity_id=str(student_id), actor_id=str(staff.staff_id), actor_role=staff.role,
        subject_student_id=str(student_id),
        before={"balance": before}, after={"balance": acc.current_balance, "scholarship": body.amount, "type": body.scholarship_type})
    await db.commit()
    return {"granted": True, "new_balance": acc.current_balance, "status": acc.payment_status}


@router.post("/students/{student_id}/financial/rebill")
async def rebill_from_policy(
    student_id: int,
    staff: Staff = Depends(require_role(StaffRole.registrar)),
    db: AsyncSession = Depends(get_db),
):
    """Recompute the term's tuition/transport charges from the student's REAL
    enrolled credits x the LIVE finance policy rates. Payments, fines, and
    scholarships are preserved; the balance invariant is re-applied."""
    acc = await _require_account(student_id, db)

    tuition_per_credit = int(await get_policy("finance.tuition_per_credit", db))
    transport_fee = int(await get_policy("finance.transport_fee", db))

    credits = int((
        await db.execute(
            select(func.coalesce(func.sum(Course.credits), 0))
            .select_from(Enrollment)
            .join(Section, Section.section_id == Enrollment.section_id)
            .join(Course, Course.code == Section.course_code)
            .where(
                Enrollment.student_id == student_id,
                Enrollment.status == "Enrolled",
            )
        )
    ).scalar() or 0)

    before = {
        "tuition_fee": acc.tuition_fee, "transportation_fee": acc.transportation_fee,
        "term_credits": acc.term_credits, "balance": acc.current_balance,
    }
    acc.term_credits = credits
    acc.tuition_fee = credits * tuition_per_credit
    acc.transportation_fee = transport_fee if credits > 0 else 0
    _recompute(acc)

    db.add(FinancialTransaction(
        id=str(uuid4()), student_id=student_id, transaction_ref=_ref("RBL"),
        semester_code=acc.semester_code, date=datetime.utcnow().strftime("%Y-%m-%d"),
        type="charge", category="Rebill",
        description=(
            f"Rebilled: {credits} credits x {tuition_per_credit} "
            f"+ transport {acc.transportation_fee}"
        ),
        amount=acc.total_charges, currency=acc.currency, status="Posted",
    ))
    await log_action(db, action="financial.rebill", entity_type="financial_account",
        entity_id=str(student_id), actor_id=str(staff.staff_id), actor_role=staff.role,
        subject_student_id=str(student_id),
        before=before,
        after={"tuition_fee": acc.tuition_fee, "transportation_fee": acc.transportation_fee,
               "term_credits": credits, "balance": acc.current_balance,
               "tuition_per_credit": tuition_per_credit})
    await db.commit()
    return {
        "rebilled": True, "term_credits": credits,
        "tuition_per_credit": tuition_per_credit,
        "tuition_fee": acc.tuition_fee, "transportation_fee": acc.transportation_fee,
        "new_balance": acc.current_balance, "status": acc.payment_status,
    }


@router.delete("/scholarships/{scholarship_id}")
async def revoke_scholarship(
    scholarship_id: str,
    staff: Staff = Depends(require_role(StaffRole.registrar)),
    db: AsyncSession = Depends(get_db),
):
    sch = await db.get(Scholarship, scholarship_id)
    if not sch:
        raise HTTPException(status_code=404, detail="Scholarship not found")
    if sch.status == "Revoked":
        raise HTTPException(status_code=400, detail="Already revoked")
    acc = await _latest_account(sch.student_id, db)
    sch.status = "Revoked"
    if acc:
        acc.scholarship_credit = max(0, (acc.scholarship_credit or 0) - (sch.amount or 0))
        _recompute(acc)
    await log_action(db, action="financial.scholarship_revoke", entity_type="scholarship",
        entity_id=scholarship_id, actor_id=str(staff.staff_id), actor_role=staff.role,
        subject_student_id=str(sch.student_id),
        after={"revoked_amount": sch.amount, "new_balance": acc.current_balance if acc else None})
    await db.commit()
    return {"revoked": True, "new_balance": acc.current_balance if acc else None}
