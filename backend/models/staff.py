"""Admin/staff principals for the admin portal.

Staff are distinct from students: they authenticate separately and carry a
role that gates every admin endpoint. Keep this table append-only-ish — set
is_active=False rather than deleting, so audit references stay intact.
"""
from datetime import datetime
from enum import Enum

from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class StaffRole(str, Enum):
    super_admin = "super_admin"   # full control, incl. managing other staff + rules
    registrar = "registrar"       # day-to-day academic + financial operations
    readonly = "readonly"         # dashboards/reports only, no mutations


# roles allowed to perform any write operation (read-only excluded)
WRITE_ROLES = (StaffRole.super_admin, StaffRole.registrar)


class Staff(Base):
    __tablename__ = "staff"

    staff_id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(30), default=StaffRole.readonly.value, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
