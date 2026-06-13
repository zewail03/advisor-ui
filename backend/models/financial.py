from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import String, Integer, Float, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


def _uuid() -> str:
    return str(uuid4())


class FinancialAccount(Base):
    __tablename__ = "financial_accounts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.student_id", ondelete="CASCADE"), index=True)
    semester_code: Mapped[str] = mapped_column(String(30), default="")
    term_credits: Mapped[int] = mapped_column(Integer, default=0)

    tuition_fee: Mapped[int] = mapped_column(Integer, default=0)
    transportation_fee: Mapped[int] = mapped_column(Integer, default=0)
    fines: Mapped[int] = mapped_column(Integer, default=0)

    total_charges: Mapped[int] = mapped_column(Integer, default=0)
    scholarship_credit: Mapped[int] = mapped_column(Integer, default=0)
    payments_made: Mapped[int] = mapped_column(Integer, default=0)
    current_balance: Mapped[int] = mapped_column(Integer, default=0)

    payment_due_date: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    payment_status: Mapped[str] = mapped_column(String(20), default="Due")
    currency: Mapped[str] = mapped_column(String(10), default="EGP")
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("student_id", "semester_code", name="uq_student_semester_account"),
    )


class FinancialTransaction(Base):
    __tablename__ = "financial_transactions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.student_id", ondelete="CASCADE"), index=True)
    transaction_ref: Mapped[str] = mapped_column(String(50), default="", index=True)

    semester_code: Mapped[str] = mapped_column(String(30), default="")
    date: Mapped[str] = mapped_column(String(30), default="")

    type: Mapped[str] = mapped_column(String(30), default="")  # invoice | payment | fine | refund
    category: Mapped[str] = mapped_column(String(50), default="")
    description: Mapped[str] = mapped_column(String(300), default="")

    amount: Mapped[int] = mapped_column(Integer, default=0)
    currency: Mapped[str] = mapped_column(String(10), default="EGP")

    status: Mapped[str] = mapped_column(String(20), default="Posted")
    reference: Mapped[str] = mapped_column(String(100), default="")

    __table_args__ = (
        UniqueConstraint("student_id", "transaction_ref", name="uq_student_transaction_ref"),
    )


class Scholarship(Base):
    __tablename__ = "scholarships"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.student_id", ondelete="CASCADE"), index=True)
    scholarship_ref: Mapped[str] = mapped_column(String(50), default="", index=True)

    semester_code: Mapped[str] = mapped_column(String(30), default="")
    scholarship_type: Mapped[str] = mapped_column(String(50), default="")
    percentage: Mapped[int] = mapped_column(Integer, default=0)
    amount: Mapped[int] = mapped_column(Integer, default=0)

    status: Mapped[str] = mapped_column(String(20), default="Active")
    criteria_basis: Mapped[str] = mapped_column(String(100), default="")
    cgpa_at_award: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[str] = mapped_column(String(300), default="")

    __table_args__ = (
        UniqueConstraint("student_id", "scholarship_ref", name="uq_student_scholarship_ref"),
    )
