"""Editable business-rule configuration.

The *schema* of each rule (type, label, category, default) lives in code
(services/policy.DEFAULTS); this table only stores the current value when an
admin overrides a default. Reads fall back to the code default, so the system
is always safe even with an empty table.
"""
from datetime import datetime

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class PolicyConfig(Base):
    __tablename__ = "policy_config"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(String(200), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_by: Mapped[str | None] = mapped_column(String(80), nullable=True)
