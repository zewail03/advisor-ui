"""Immutable audit trail (§30).

Every sensitive state change (enrollments, grades, approvals, attendance FW,
retakes, petitions, payments, advisor assignment, role changes…) should
record a row here. We keep before/after JSON snapshots so reviewers can
reconstruct exact history without consulting backups.
"""
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import String, DateTime, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


def _uuid() -> str:
    return str(uuid4())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    actor_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    actor_role: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    subject_student_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)

    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)

    before_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    after_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)

    __table_args__ = (
        Index("ix_audit_entity", "entity_type", "entity_id"),
        Index("ix_audit_subject_action", "subject_student_id", "action"),
    )
