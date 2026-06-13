"""Schedule-generation endpoints.

Demo build uses an in-memory session store instead of Redis so the backend
is single-process runnable. Sessions expire 30 minutes after creation.
"""
import time
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_student
from models.student import Student
from schemas.enrollment import ScheduleGenerateRequest
from services.schedule_generator import generate_schedules

router = APIRouter()

_SESSION_TTL = 30 * 60
_sessions: dict[str, tuple[float, list]] = {}


def _prune() -> None:
    now = time.time()
    expired = [sid for sid, (exp, _) in _sessions.items() if exp < now]
    for sid in expired:
        _sessions.pop(sid, None)


@router.post("/generate")
async def generate(
    req: ScheduleGenerateRequest,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    options = await generate_schedules(
        student=student,
        semester_code=req.semester_code,
        db=db,
        max_credits_preference=req.max_credits,
    )
    session_id = str(uuid4())
    _prune()
    _sessions[session_id] = (time.time() + _SESSION_TTL, options)
    return {"session_id": session_id, "options": options}


@router.get("/options/{session_id}")
async def get_options(session_id: str):
    _prune()
    entry = _sessions.get(session_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Schedule session expired or not found")
    return {"session_id": session_id, "options": entry[1]}
