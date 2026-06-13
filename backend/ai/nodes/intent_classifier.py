import json

from ai.groq_client import FAST_MODEL, complete
from ai.state import ChatState

INTENTS = [
    "academic_info",
    "course_recommendation",
    "gpa_simulation",
    "schedule_planning",
    "graduation_planning",  # roadmap to graduation / graduate early / fast-track
    "probation_recovery",
    "career_guidance",
    "financial_query",
    "policy_question",
    "general_chat",
]

SYSTEM = f"""You classify student-advisor messages into one of these intents:
{", ".join(INTENTS)}

Disambiguation hints:
- "graduation_planning": multi-term degree roadmaps — graduate early/fast-track,
  "when can I graduate", AND any request to MODIFY a degree plan, e.g.
  "make Fall 2027 lighter", "reduce the load in Spring 2027", "cap that term
  at 12 hours", "move courses out of a term".
- "schedule_planning": building ONE upcoming term's weekly timetable
  (sections, days, times, instructors) — not multi-term roadmaps.

Return STRICT JSON: {{"intent": "<one of above>", "confidence": 0.0-1.0}}
No prose, no code fences."""


async def classify_intent(state: ChatState) -> ChatState:
    msg = state["message"]
    raw = await complete(
        [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": msg},
        ],
        model=FAST_MODEL,
        temperature=0.0,
        max_tokens=60,
    )
    try:
        data = json.loads(raw.strip().split("```")[-1] if "```" in raw else raw)
        intent = data.get("intent", "general_chat")
        if intent not in INTENTS:
            intent = "general_chat"
        confidence = float(data.get("confidence", 0.5))
    except Exception:
        intent = "general_chat"
        confidence = 0.3

    return {**state, "intent": intent, "confidence": confidence}
