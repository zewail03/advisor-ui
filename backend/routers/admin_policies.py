"""Admin business-rule configuration.

Any staff may VIEW the rules; only super_admin may CHANGE them (rules govern
grades, money, and eligibility). Every change is audited with before/after.
"""
from collections import OrderedDict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_staff, require_role
from models.staff import Staff
from services.audit_service import log_action
from services.policy import all_policies, set_policy

router = APIRouter()


class PolicyUpdate(BaseModel):
    value: float


@router.get("/policies")
async def list_policies(
    staff: Staff = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    items = await all_policies(db)
    grouped: "OrderedDict[str, list]" = OrderedDict()
    for p in items:
        grouped.setdefault(p["category"], []).append(p)
    return {
        "can_edit": staff.role == "super_admin",
        "categories": [{"name": k, "policies": v} for k, v in grouped.items()],
    }


@router.patch("/policies/{key}")
async def update_policy(
    key: str,
    body: PolicyUpdate,
    staff: Staff = Depends(require_role()),  # no extra roles -> super_admin only
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await set_policy(key, body.value, db, updated_by=staff.username)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown policy '{key}'")

    await log_action(
        db,
        action="policy.update",
        entity_type="policy",
        entity_id=key,
        actor_id=str(staff.staff_id),
        actor_role=staff.role,
        before={key: result["old"]},
        after={key: result["new"]},
    )
    await db.commit()
    return {"updated": True, **result}
