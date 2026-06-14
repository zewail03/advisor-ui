from typing import List, Optional, TypedDict


class ChatState(TypedDict, total=False):
    student_id: str
    session_id: Optional[str]
    message: str
    history: List[dict]
    language: str  # "en" | "ar" — the student's UI language

    intent: str
    confidence: float

    clarification: Optional[dict]  # {"question": str, "options": [str]} when the bot needs to ask back

    student_context: dict
    rag_docs: List[dict]
    tool_output: dict

    response: str
    citations: List[str]
