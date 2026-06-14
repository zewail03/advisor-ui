import json
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.graph import get_graph
from ai.nodes.response_generator import generate_stream
from ai.state import ChatState
from core.database import get_db
from core.security import get_current_student
from models.ai_models import ChatMessage, ChatSession
from models.student import Student

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    language: Optional[str] = "en"  # UI language: the bot answers in it


def _title_from(message: str) -> str:
    t = (message or "").strip().replace("\n", " ")
    if not t:
        return "New conversation"
    return t[:57].rstrip() + "…" if len(t) > 60 else t


async def _get_or_create_session(
    db: AsyncSession, student_id: int, session_id: Optional[str], first_message: str = ""
) -> ChatSession:
    if session_id:
        s = await db.get(ChatSession, session_id)
        if s and s.student_id == student_id:
            return s
    # New session — name it after the first thing the student asked.
    s = ChatSession(id=str(uuid4()), student_id=student_id, title=_title_from(first_message))
    db.add(s)
    await db.commit()
    await db.refresh(s)
    return s


async def _load_history(db: AsyncSession, session_id: str, limit: int = 12):
    res = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    msgs = list(res.scalars().all())
    msgs.reverse()
    return [{"role": m.role, "content": m.content, "intent": m.intent} for m in msgs]


@router.post("/message")
async def chat_message(
    req: ChatRequest,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    session = await _get_or_create_session(db, student.student_id, req.session_id, req.message)
    history = await _load_history(db, session.id)

    db.add(
        ChatMessage(
            id=str(uuid4()),
            session_id=session.id,
            role="user",
            content=req.message,
        )
    )
    session.last_message_at = datetime.utcnow()
    await db.commit()

    state: ChatState = {
        "student_id": student.student_id,
        "session_id": session.id,
        "message": req.message,
        "history": history,
        "language": (req.language or "en").lower(),
    }

    graph = get_graph()
    pre_state: ChatState = await graph.ainvoke(state)

    async def event_stream():
        yield f"event: session\ndata: {json.dumps({'session_id': session.id, 'intent': pre_state.get('intent')})}\n\n"

        clar = pre_state.get("clarification")
        if clar and clar.get("question"):
            yield f"event: clarify\ndata: {json.dumps({'question': clar['question'], 'options': clar.get('options') or []})}\n\n"

        citations = [
            d.get("document") or d.get("source")
            for d in (pre_state.get("rag_docs") or [])
        ]
        if citations:
            yield f"event: citations\ndata: {json.dumps(citations)}\n\n"

        collected = []
        async for token in generate_stream(pre_state):
            collected.append(token)
            yield f"event: token\ndata: {json.dumps({'t': token})}\n\n"

        final = "".join(collected)
        db.add(
            ChatMessage(
                id=str(uuid4()),
                session_id=session.id,
                role="assistant",
                content=final,
                intent=pre_state.get("intent"),
            )
        )
        session.last_message_at = datetime.utcnow()
        await db.commit()
        yield f"event: done\ndata: {json.dumps({'ok': True})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/sessions")
async def list_sessions(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    res = await db.execute(
        select(ChatSession)
        .where(ChatSession.student_id == student.student_id)
        .order_by(ChatSession.last_message_at.desc())
        .limit(50)
    )
    return [
        {
            "id": s.id,
            "title": s.title,
            "created_at": s.created_at.isoformat(),
            "last_message_at": (s.last_message_at or s.created_at).isoformat(),
        }
        for s in res.scalars().all()
    ]


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Delete a conversation (and all its messages) — owner only."""
    session = await db.get(ChatSession, session_id)
    if not session or session.student_id != student.student_id:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await db.delete(session)  # messages cascade via the relationship
    await db.commit()
    return {"deleted": session_id}


@router.get("/sessions/{session_id}/messages")
async def session_messages(
    session_id: str,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(ChatSession, session_id)
    if not session or session.student_id != student.student_id:
        return {"messages": []}
    res = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    )
    return {
        "session_id": session_id,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "intent": m.intent,
                "created_at": m.created_at.isoformat(),
            }
            for m in res.scalars().all()
        ],
    }
