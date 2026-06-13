from langgraph.graph import END, StateGraph

from ai.nodes.context_loader import load_student_context
from ai.nodes.course_recommender import course_recommender
from ai.nodes.emergency_recovery import emergency_recovery
from ai.nodes.intent_classifier import classify_intent
from ai.nodes.rag_retriever import retrieve_docs
from ai.nodes.tool_nodes import degree_planner_tool, gpa_simulator_tool, schedule_suggester_tool
from ai.state import ChatState


_RISK_STANDINGS = {"probation", "final chance", "dismissed", "dismissal_risk"}


def _route_after_intent(state: ChatState) -> str:
    intent = state.get("intent", "general_chat")
    standing = (state.get("student_context") or {}).get("standing", "") or ""

    if intent == "probation_recovery" or standing.strip().lower() in _RISK_STANDINGS:
        return "recovery"
    if intent == "gpa_simulation":
        return "gpa_tool"
    if intent == "schedule_planning":
        return "schedule_tool"
    if intent == "graduation_planning":
        return "degree_plan_tool"
    if intent == "course_recommendation":
        return "course_recommend"
    if intent in ("policy_question", "career_guidance", "financial_query"):
        return "rag"
    # academic_info, general_chat — student profile has CGPA/standing,
    # so the LLM can answer directly without a tool call
    return "done"


def build_graph():
    g = StateGraph(ChatState)
    g.add_node("intent", classify_intent)
    g.add_node("context", load_student_context)
    g.add_node("rag", retrieve_docs)
    g.add_node("gpa_tool", gpa_simulator_tool)
    g.add_node("schedule_tool", schedule_suggester_tool)
    g.add_node("degree_plan_tool", degree_planner_tool)
    g.add_node("course_recommend", course_recommender)
    g.add_node("recovery", emergency_recovery)
    g.add_node("done", lambda s: s)

    g.set_entry_point("intent")
    g.add_edge("intent", "context")
    g.add_conditional_edges(
        "context",
        _route_after_intent,
        {
            "rag": "rag",
            "gpa_tool": "gpa_tool",
            "schedule_tool": "schedule_tool",
            "degree_plan_tool": "degree_plan_tool",
            "course_recommend": "course_recommend",
            "recovery": "recovery",
            "done": "done",
        },
    )
    g.add_edge("rag", "done")
    g.add_edge("gpa_tool", "done")
    g.add_edge("schedule_tool", "done")
    g.add_edge("degree_plan_tool", "done")
    g.add_edge("course_recommend", "done")
    g.add_edge("recovery", "done")
    g.add_edge("done", END)
    return g.compile()


_compiled = None


def get_graph():
    global _compiled
    if _compiled is None:
        _compiled = build_graph()
    return _compiled
