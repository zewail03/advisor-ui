"""Staff management — super-admin-only CRUD over admin accounts.

Create, edit (role / details), activate-deactivate, and reset passwords for
other staff. The table is never hard-deleted (audit references stay intact) —
deactivation is `is_active=False`. Every mutation requires super_admin
(`require_role()` with no args) and is recorded in the audit log.

Self-protection: a super-admin cannot demote or deactivate their own account,
so they can never lock themselves (or the system) out by accident.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_password_hash, require_role
from models.staff import Staff, StaffRole
from services.audit_service import log_action

router = APIRouter()

VALID_ROLES = [r.value for r in StaffRole]
DEFAULT_TEMP_PASSWORD = "changeme123"


def _row(s: Staff) -> dict:
    return {
        "id": s.staff_id,
        "username": s.username,
        "full_name": s.full_name,
        "email": s.email,
        "role": s.role,
        "is_active": s.is_active,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "last_login_at": s.last_login_at.isoformat() if s.last_login_at else None,
    }


class StaffCreate(BaseModel):
    username: str
    full_name: str
    email: str
    role: str = StaffRole.readonly.value
    password: Optional[str] = None  # blank -> standard temp password


class StaffUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class PasswordReset(BaseModel):
    new_password: Optional[str] = None


@router.get("/staff")
async def list_staff(
    actor: Staff = Depends(require_role()),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(select(Staff).order_by(Staff.staff_id))).scalars().all()
    return {"staff": [_row(s) for s in rows], "roles": VALID_ROLES, "me": actor.staff_id}


@router.post("/staff")
async def create_staff(
    body: StaffCreate,
    actor: Staff = Depends(require_role()),
    db: AsyncSession = Depends(get_db),
):
    username = body.username.strip().lower()
    email = body.email.strip().lower()
    if not username or not body.full_name.strip() or not email:
        raise HTTPException(status_code=422, detail="username, full name and email are required")
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=422, detail=f"role must be one of {VALID_ROLES}")

    clash = (
        await db.execute(
            select(Staff).where(or_(Staff.username == username, Staff.email == email))
        )
    ).scalar_one_or_none()
    if clash:
        field = "username" if clash.username == username else "email"
        raise HTTPException(status_code=409, detail=f"That {field} is already taken")

    password = (body.password or "").strip() or DEFAULT_TEMP_PASSWORD
    staff = Staff(
        username=username,
        full_name=body.full_name.strip(),
        email=email,
        hashed_password=get_password_hash(password),
        role=body.role,
        is_active=True,
    )
    db.add(staff)
    await db.flush()

    await log_action(
        db,
        action="staff.create",
        entity_type="staff",
        entity_id=str(staff.staff_id),
        actor_id=str(actor.staff_id),
        actor_role=actor.role,
        after={"username": username, "full_name": staff.full_name, "email": email, "role": staff.role},
    )
    await db.commit()
    return {
        "created": True,
        "staff": _row(staff),
        "temporary_password": password if not (body.password or "").strip() else None,
    }


@router.patch("/staff/{staff_id}")
async def update_staff(
    staff_id: int,
    body: StaffUpdate,
    actor: Staff = Depends(require_role()),
    db: AsyncSession = Depends(get_db),
):
    target = await db.get(Staff, staff_id)
    if not target:
        raise HTTPException(status_code=404, detail="Staff not found")

    is_self = target.staff_id == actor.staff_id
    before = _row(target)
    changed: list[str] = []

    if body.full_name is not None and body.full_name.strip():
        target.full_name = body.full_name.strip()
        changed.append("full_name")

    if body.email is not None:
        email = body.email.strip().lower()
        if email and email != target.email:
            clash = (
                await db.execute(select(Staff).where(Staff.email == email, Staff.staff_id != staff_id))
            ).scalar_one_or_none()
            if clash:
                raise HTTPException(status_code=409, detail="That email is already taken")
            target.email = email
            changed.append("email")

    if body.role is not None and body.role != target.role:
        if body.role not in VALID_ROLES:
            raise HTTPException(status_code=422, detail=f"role must be one of {VALID_ROLES}")
        if is_self:
            raise HTTPException(status_code=400, detail="You cannot change your own role")
        target.role = body.role
        changed.append("role")

    if body.is_active is not None and body.is_active != target.is_active:
        if is_self and body.is_active is False:
            raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
        target.is_active = body.is_active
        changed.append("is_active")

    if not changed:
        return {"updated": False, "changed": [], "staff": _row(target)}

    await log_action(
        db,
        action="staff.update",
        entity_type="staff",
        entity_id=str(staff_id),
        actor_id=str(actor.staff_id),
        actor_role=actor.role,
        before={k: before[k] for k in changed},
        after={k: _row(target)[k] for k in changed},
    )
    await db.commit()
    return {"updated": True, "changed": changed, "staff": _row(target)}


@router.post("/staff/{staff_id}/reset-password")
async def reset_staff_password(
    staff_id: int,
    body: PasswordReset,
    actor: Staff = Depends(require_role()),
    db: AsyncSession = Depends(get_db),
):
    target = await db.get(Staff, staff_id)
    if not target:
        raise HTTPException(status_code=404, detail="Staff not found")

    new_password = (body.new_password or "").strip() or DEFAULT_TEMP_PASSWORD
    target.hashed_password = get_password_hash(new_password)

    await log_action(
        db,
        action="staff.password_reset",
        entity_type="staff",
        entity_id=str(staff_id),
        actor_id=str(actor.staff_id),
        actor_role=actor.role,
    )
    await db.commit()
    return {"reset": True, "username": target.username, "temporary_password": new_password}
