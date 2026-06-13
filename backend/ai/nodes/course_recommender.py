"""Course recommender node.

Triggered by `course_recommendation` intent. Parses the target semester from
the message (falls back to the next plannable term), then delegates to
services.course_recommender so the same ranking feeds chat + REST endpoints.
"""
import re

from ai.state import ChatState
from core.database import AsyncSessionLocal
from models.student import Student
from services.course_recommender import recommend_courses, render_recommendations_summary

DEFAULT_TARGET_SEMESTER = "Fall 2026"  # next main registration target


async def course_recommender(state: ChatState) -> ChatState:
    match = re.search(r"(Fall|Spring|Summer)[- ]?(\d{4})", state["message"], re.IGNORECASE)
    semester = (
        f"{match.group(1).title()} {match.group(2)}" if match else DEFAULT_TARGET_SEMESTER
    )

    async with AsyncSessionLocal() as db:
        student = await db.get(Student, state["student_id"])
        if not student:
            return {
                **state,
                "tool_output": {"kind": "course_recommendations", "summary": "Student not found."},
            }
        payload = await recommend_courses(student, semester, db)

    return {
        **state,
        "tool_output": {
            "kind": "course_recommendations",
            "summary": render_recommendations_summary(payload),
            "raw": payload,
        },
    }
