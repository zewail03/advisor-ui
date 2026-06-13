import json
import re

from sqlalchemy import select

from ai.groq_client import FAST_MODEL, complete
from ai.state import ChatState
from core.database import AsyncSessionLocal
from models.course import Course, Section
from models.enrollment import Enrollment
from services.gpa_calculator import required_grades_for_target, simulate_cgpa
from services.schedule_generator import generate_schedules
from models.student import Student


async def _in_progress_course_codes(student_id: int, db) -> list[str]:
    """Course codes the student is actively enrolled in (in-progress, ungraded)."""
    rows = await db.execute(
        select(Section.course_code)
        .join(Enrollment, Enrollment.section_id == Section.section_id)
        .where(
            Enrollment.student_id == student_id,
            Enrollment.status == "Enrolled",
        )
    )
    return [r[0] for r in rows.all()]


async def gpa_simulator_tool(state: ChatState) -> ChatState:
    extract_prompt = f"""Extract GPA simulation parameters from the student message.
Return STRICT JSON:
{{"mode": "simulate"|"required", "target_cgpa": float|null, "course_codes": [<str>], "grades": [<letter>]}}

Message: {state["message"]}"""
    raw = await complete(
        [{"role": "user", "content": extract_prompt}],
        model=FAST_MODEL,
        temperature=0.0,
        max_tokens=200,
    )
    cleaned = raw.strip()
    if "```" in cleaned:
        parts = cleaned.split("```")
        cleaned = parts[1] if len(parts) >= 2 else cleaned
        if cleaned.lstrip().lower().startswith("json"):
            cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else ""
    try:
        data = json.loads(cleaned.strip())
    except Exception:
        return {**state, "tool_output": {"kind": "gpa", "summary": "Could not parse GPA request parameters."}}

    async with AsyncSessionLocal() as db:
        codes = data.get("course_codes") or []
        known_codes: list = []
        if codes:
            rows = await db.execute(select(Course.code).where(Course.code.in_(codes)))
            known_codes = [r[0] for r in rows.all()]

        if data.get("mode") == "required" and data.get("target_cgpa"):
            result = await required_grades_for_target(
                student_id=state["student_id"],
                target_cgpa=float(data["target_cgpa"]),
                course_codes=known_codes,
                db=db,
            )
            summary = f"To reach CGPA {data['target_cgpa']}: {json.dumps(result)}"
        else:
            grades = data.get("grades") or []
            scenarios = [
                {"course_code": c, "predicted_grade": g}
                for c, g in zip(codes, grades)
                if c in known_codes
            ]
            # User referenced "all my current courses" without naming them:
            # resolve to the student's real in-progress enrollments and apply
            # the single mentioned grade to each.
            if not scenarios and grades:
                in_progress = await _in_progress_course_codes(state["student_id"], db)
                if in_progress:
                    blanket_grade = grades[0]
                    scenarios = [
                        {"course_code": c, "predicted_grade": blanket_grade}
                        for c in in_progress
                    ]
                else:
                    base = await simulate_cgpa(
                        student_id=state["student_id"], scenarios=[], db=db
                    )
                    return {
                        **state,
                        "tool_output": {
                            "kind": "gpa",
                            "summary": (
                                f"You have no in-progress courses this semester, so "
                                f"there's nothing to project grades onto. Your current "
                                f"CGPA is {base.get('current_cgpa')}. Tell me specific "
                                f"course codes and target grades and I'll simulate the impact."
                            ),
                            "raw": base,
                        },
                    }
            result = await simulate_cgpa(
                student_id=state["student_id"], scenarios=scenarios, db=db
            )
            current = result.get("current_cgpa")
            projected = result.get("projected_cgpa")
            parts = [f"Current CGPA: {current}", f"Projected CGPA: {projected}"]
            if current is not None and projected is not None:
                delta = float(projected) - float(current)
                direction = "increase" if delta >= 0 else "decrease"
                parts.append(f"Change: {direction} of {abs(delta):.3f}")
            courses_detail = ", ".join(
                f"{s['course_code']}={s['predicted_grade']}" for s in scenarios
            )
            if courses_detail:
                parts.append(f"Courses: {courses_detail}")
            summary = " | ".join(parts)

    return {**state, "tool_output": {"kind": "gpa", "summary": summary, "raw": result}}


# strong signals ask to lighten a term by themselves; weak ones ("only 12",
# "max 14") count only next to an explicit hours number — otherwise phrases
# like "is it easier to graduate in Fall 2027?" would wrongly cap that term
_STRONG_LIGHTEN_RE = re.compile(
    r"\b(light\w*|lighten\w*|reduc\w*|fewer|less|lower|decreas\w*|cap|capped)\b",
    re.IGNORECASE,
)
_WEAK_LIGHTEN_RE = re.compile(r"\b(only|max|maximum|limit)\b", re.IGNORECASE)
_TERM_RE = re.compile(r"\b(Fall|Spring|Summer)[- ]?(20\d{2})\b", re.IGNORECASE)
_HOURS_RE = re.compile(r"\b(\d{1,2})\b\s*(?:ch|cr|credits?|hours?|hrs)?")
_DEFAULT_LIGHT_LOAD = 12  # lightest full-time load when no number is given


def _extract_term_caps(message: str) -> dict[str, int]:
    """Deterministic parse of plan-revision requests like 'make Fall 2027
    lighter' or 'cap Spring 2027 at 14 hours'. Returns {} when the message
    isn't asking to lighten a specific term."""
    terms = [f"{s.title()} {y}" for s, y in _TERM_RE.findall(message)]
    if not terms:
        return {}
    nums = [int(n) for n in _HOURS_RE.findall(message) if 3 <= int(n) <= 22]
    if not (_STRONG_LIGHTEN_RE.search(message)
            or (_WEAK_LIGHTEN_RE.search(message) and nums)):
        return {}
    cap = nums[0] if nums else _DEFAULT_LIGHT_LOAD
    return {t: cap for t in terms}


async def degree_planner_tool(state: ChatState) -> ChatState:
    """Roadmap-to-graduation tool: normal vs fastest (summers + overload).
    Plan revisions ('make Fall 2027 lighter') re-run the engine with a
    per-term cap so every shown plan is rules-validated — the LLM never
    rearranges courses itself."""
    from services.degree_planner import compare_degree_plans, render_degree_plan_summary

    term_caps = _extract_term_caps(state["message"])
    async with AsyncSessionLocal() as db:
        student = await db.get(Student, state["student_id"])
        if not student:
            return {**state, "tool_output": {"kind": "degree_plan", "summary": "Student not found."}}
        payload = await compare_degree_plans(student, db, term_caps=term_caps or None)
    return {
        **state,
        "tool_output": {
            "kind": "degree_plan",
            "summary": render_degree_plan_summary(payload),
            "raw": payload,
        },
    }


async def schedule_suggester_tool(state: ChatState) -> ChatState:
    match = re.search(r"(Fall|Spring|Summer)[- ]?(\d{4})", state["message"], re.IGNORECASE)
    semester = f"{match.group(1).title()} {match.group(2)}" if match else "Fall 2026"

    async with AsyncSessionLocal() as db:
        student = await db.get(Student, state["student_id"])
        if not student:
            return {**state, "tool_output": {"kind": "schedule", "summary": "Student not found."}}
        options = await generate_schedules(student=student, semester_code=semester, db=db)
    if not options:
        summary = f"No schedule options available for {semester}. The semester may not exist or no sections are open."
    else:
        parts = [f"Generated {len(options)} schedule options for {semester}:\n"]
        for i, o in enumerate(options, 1):
            parts.append(f"Option {i} — {o['label']} ({o['total_credits']} credits, {o['load_score']} load):")
            if o.get("note"):
                parts.append(f"  NOTE: {o['note']}")
            for s in o.get("sections", []):
                meetings_str = ""
                for m in s.get("meetings", []):
                    meetings_str += f" {m.get('day_of_week', '')} {m.get('start_time', '')}-{m.get('end_time', '')}"
                flags = []
                status = s.get("plan_status", "on plan")
                if status == "retake":
                    flags.append("RETAKE of failed course")
                elif status == "ahead of plan":
                    flags.append("AHEAD OF PLAN — needs advisor approval to register")
                pers = s.get("personal_difficulty")
                if pers in ("Hard for you", "Easier for you"):
                    flags.append(f"{pers} ({s.get('personal_reason', '')})")
                if s.get("registration_priority") == "High":
                    flags.append(
                        f"register FIRST — {s.get('students_needing', 0)} students need it, "
                        f"only {s.get('open_seats', 0)} seats"
                    )
                parts.append(
                    f"  - {s['course_code']}: {s.get('course_title', '')} ({s.get('credits', 3)}cr)"
                    f" | Sec {s.get('section_number', '?')} | {s.get('instructor', 'TBD')}"
                    f" | Difficulty: {s.get('difficulty', 'Unknown')}"
                    f"{' |' + meetings_str if meetings_str.strip() else ''}"
                    f"{' | ' + '; '.join(flags) if flags else ''}"
                )
            parts.append("")
        parts.append(
            "Guidance for the answer: render Option 1 as a markdown table "
            "(| Course | Title | CH | Day & Time | Notes |). Options share many courses — "
            "after the table, state ONLY the differences for the other options in one line "
            "each (give them their own table only if they differ substantially). Mention "
            "advisor-approval needs and register-first priorities in the Notes column."
        )
        summary = "\n".join(parts)
    return {**state, "tool_output": {"kind": "schedule", "summary": summary, "raw": options}}
