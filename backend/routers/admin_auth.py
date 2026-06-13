"""Admin/staff authentication for the admin portal."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import (
    create_admin_token,
    get_current_staff,
    verify_password,
)
from models.staff import Staff
from services.audit_service import log_action

router = APIRouter()


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: str


def _staff_dict(s: Staff) -> dict:
    return {
        "id": s.staff_id,
        "username": s.username,
        "full_name": s.full_name,
        "email": s.email,
        "role": s.role,
        "is_active": s.is_active,
        "last_login_at": s.last_login_at.isoformat() if s.last_login_at else None,
    }


@router.post("/login", response_model=AdminTokenResponse)
async def admin_login(req: AdminLoginRequest, db: AsyncSession = Depends(get_db)):
    staff = (
        await db.execute(select(Staff).where(Staff.username == req.username))
    ).scalar_one_or_none()
    if not staff or not staff.is_active or not verify_password(req.password, staff.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    staff.last_login_at = datetime.utcnow()
    await log_action(
        db,
        action="admin.login",
        entity_type="staff",
        entity_id=str(staff.staff_id),
        actor_id=str(staff.staff_id),
        actor_role=staff.role,
    )
    await db.commit()

    token = create_admin_token(
        {"sub": str(staff.staff_id), "role": staff.role, "username": staff.username}
    )
    return AdminTokenResponse(access_token=token, role=staff.role, full_name=staff.full_name)


@router.get("/me")
async def admin_me(staff: Staff = Depends(get_current_staff)):
    return _staff_dict(staff)
