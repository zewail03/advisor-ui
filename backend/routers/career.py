"""Career Path Advisor endpoint.

POST /career/plan streams (SSE) an AIU career roadmap grounded in REAL job-market
requirements fetched live from the web (DuckDuckGo over LinkedIn/Indeed/etc.),
then mapped to the student's actual AIU courses. Emits the cited sources first,
then the streamed markdown plan.
"""
import asyncio
import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.groq_client import PRIMARY_MODEL, stream
from ai.web_search import research_role
from core.database import get_db
from core.security import get_current_student
from models.course import Course
from models.student import Major, Program, Student
from services.career_service import build_messages

router = APIRouter()


class CareerRequest(BaseModel):
    goal: str


@router.post("/plan")
async def career_plan(
    req: CareerRequest,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    role = (req.goal or "").strip()[:120] or "a technology career"

    program = await db.get(Program, student.program_id) if student.program_id else None
    major = await db.get(Major, student.major_id) if student.major_id else None
    rows = (
        await db.execute(
            select(Course.code, Course.name).where(Course.credits >= 3).order_by(Course.code)
        )
    ).all()
    courses = [{"code": c, "title": n} for c, n in rows]
    student_ctx = {
        "program": (major.name if major else None) or (program.name if program else "Computer Science"),
        "cgpa": student.cgpa,
        "level": student.level,
    }

    # live web research (blocking lib → run off the event loop)
    sources = await asyncio.to_thread(research_role, role)
    messages = build_messages(role, student_ctx, courses, sources)

    async def event_stream():
        yield (
            "event: sources\ndata: "
            + json.dumps([{"title": s["title"], "url": s["url"]} for s in sources])
            + "\n\n"
        )
        async for tok in stream(messages, model=PRIMARY_MODEL, temperature=0.4, max_tokens=1100):
            yield f"event: token\ndata: {json.dumps({'t': tok})}\n\n"
        yield f"event: done\ndata: {json.dumps({'ok': True, 'sources': len(sources)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
