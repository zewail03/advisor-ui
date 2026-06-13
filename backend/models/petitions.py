"""Student petitions (§14 Final Chance, §15 Freeze, §16 Transfer, §27 Grade Appeal).

A single polymorphic table holds all petition types; each carries a JSON
payload specific to its kind so routers can stay thin.
"""
import enum
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import String, Integer, DateTime, Text, Enum, ForeignKey, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


def _uuid() -> str:
    return str(uuid4())


# §14 final-chance (≥80% completion, once per student), §15 freeze caps
# (consecutive/total), and §16 transfer CGPA all live in the policy engine
# (petition.* keys in services/policy.py).
TRANSFER_MIN_CGPA = 2.00         # §16 fallback documented value
APPEAL_WINDOW_DAYS = 15          # §27: grade appeal within 15 days of posting


class PetitionType(str, enum.Enum):
    final_chance = "final_chance"
    freeze = "freeze"
    transfer_in = "transfer_in"
    transfer_between_programs = "transfer_between_programs"
    grade_appeal = "grade_appeal"


class PetitionStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    under_review = "under_review"
    approved = "approved"
    rejected = "rejected"
    withdrawn = "withdrawn"


class Petition(Base):
    __tablename__ = "petitions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("students.student_id", ondelete="CASCADE"), index=True
    )
    type: Mapped[PetitionType] = mapped_column(Enum(PetitionType), nullable=False, index=True)
    status: Mapped[PetitionStatus] = mapped_column(
        Enum(PetitionStatus), default=PetitionStatus.submitted, index=True
    )

    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Grade-appeal specifics (loose ref; enrollments PK is integer in live schema)
    enrollment_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    current_grade: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    requested_grade: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)

    # Review
    reviewer_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    reviewer_role: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    decision_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Freeze-specific
    freeze_semester_code: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    # Transfer-specific
    source_program_code: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    target_program_code: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    transfer_cgpa_snapshot: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    effect_applied: Mapped[bool] = mapped_column(Boolean, default=False)
