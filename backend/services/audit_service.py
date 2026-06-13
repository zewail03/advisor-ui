"""Write-once audit log helper (§30)."""
import json
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from models.audit import AuditLog


def _jsonify(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return json.dumps(value, default=str)
    except TypeError:
        return json.dumps(str(value))


async def log_action(
    db: AsyncSession,
    action: str,
    entity_type: str,
    *,
    entity_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    actor_role: Optional[str] = None,
    subject_student_id: Optional[str] = None,
    before: Any = None,
    after: Any = None,
    metadata: Any = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    commit: bool = False,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor_id,
        actor_role=actor_role,
        subject_student_id=subject_student_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_json=_jsonify(before),
        after_json=_jsonify(after),
        metadata_json=_jsonify(metadata),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(entry)
    if commit:
        await db.commit()
        await db.refresh(entry)
    return entry
