"""Emergency academic recovery node.

Triggered when student is on probation, at dismissal risk, or explicitly asks for
recovery help. Delegates plan construction to services.recovery_service so the
same plan shape powers both the chat pathway and the REST endpoint.
"""
from ai.state import ChatState
from core.database import AsyncSessionLocal
from services.recovery_service import build_recovery_plan, render_plan_summary


async def emergency_recovery(state: ChatState) -> ChatState:
    async with AsyncSessionLocal() as db:
        plan = await build_recovery_plan(state["student_id"], db)
    return {
        **state,
        "tool_output": {
            "kind": "recovery",
            "summary": render_plan_summary(plan),
            "plan": plan,
        },
    }
