"""Clarification gate — decide whether to answer or ask ONE focused question.

Mirrors how a careful human advisor (and Claude) works: when a request is
genuinely ambiguous or missing a detail essential to an accurate answer, ask a
short clarifying question instead of guessing. Otherwise answer normally.

Runs on the FAST model. When it decides to clarify, the graph routes straight to
"done" so the question is streamed back directly — no RAG, no tools, nothing
invented. A deterministic guard prevents asking twice in a row.
"""
import json

from ai.groq_client import FAST_MODEL, complete
from ai.state import ChatState

GATE_SYSTEM = """You are the clarification gate of an AIU academic-advisor chatbot.
Decide whether the student's latest message can be answered as-is, or whether ONE focused clarifying question is truly needed first.

STRONG DEFAULT: choose "answer". The advisor has full access to the student's record (CGPA, GPA, standing, credits earned/remaining, current and past courses, grades, degree plan) and university policy. Only choose "clarify" when you genuinely CANNOT give a useful answer without a missing detail. When in doubt, ANSWER.

ALWAYS choose "answer" for:
- greetings, thanks, smalltalk
- any factual question about the student's own record — e.g. "what is my CGPA/GPA", "what's my standing", "am I on probation", "how many credits do I have left", "what am I taking", "what's my grade in X", "when do I graduate". (CGPA is cumulative — never ask which term.)
- policy / "how does X work" questions
- anything where a sensible default can be assumed and stated
- when the previous assistant message already asked a clarifying question (the student is now answering it)

Choose "clarify" ONLY for an ACTIONABLE request that is missing a parameter it cannot run without, e.g.:
- "plan / build my schedule" with no term given -> which term?
- "make a term lighter / cap the load" with no number -> how many credit hours?
- a vague reference with no antecedent in the conversation -> "that course"/"the plan" when nothing earlier identifies it
- a request that could mean two materially different things

Keep the question SHORT and in the student's language. Offer 2-4 brief quick-reply options ONLY when they are obvious and finite (specific terms, yes/no); otherwise use an empty list.

Return STRICT JSON, no prose, no code fences:
{"action": "answer" | "clarify", "question": "<one short question or empty>", "options": ["..."]}"""


async def clarify_gate(state: ChatState) -> ChatState:
    history = state.get("history", []) or []

    # Deterministic anti-loop: if we JUST asked a clarifying question, the
    # student's reply is the answer to it — never clarify twice in a row.
    last = history[-1] if history else None
    if last and last.get("role") == "assistant" and last.get("intent") == "clarification":
        return {**state, "clarification": None}

    recent = history[-4:]
    convo = "\n".join(f'{h.get("role")}: {h.get("content", "")}' for h in recent) or "(none)"
    user = (
        f"Language: {state.get('language', 'en')}\n"
        f"Recent conversation:\n{convo}\n\n"
        f"Student's latest message: {state['message']}\n\nDecide."
    )

    try:
        raw = await complete(
            [{"role": "system", "content": GATE_SYSTEM}, {"role": "user", "content": user}],
            model=FAST_MODEL,
            temperature=0.0,
            max_tokens=160,
            use_cache=False,
        )
        data = json.loads(raw.strip().split("```")[-1] if "```" in raw else raw)
        action = data.get("action", "answer")
        question = (data.get("question") or "").strip()
        options = [str(o).strip() for o in (data.get("options") or []) if str(o).strip()][:4]
    except Exception:
        action, question, options = "answer", "", []

    if action == "clarify" and question:
        return {**state, "clarification": {"question": question, "options": options}, "intent": "clarification"}
    return {**state, "clarification": None}
