"""Career Path Advisor — turns a student's goal into an AIU plan grounded in
REAL job-market requirements pulled from the web (LinkedIn / Indeed / Glassdoor /
career guides) rather than the model's imagination. The LLM only (a) extracts the
real requirements from the retrieved snippets and (b) maps them to the student's
actual AIU courses — no invented requirements, no invented course codes.
"""
from typing import Dict, List

CAREER_SYSTEM = """You are AIU's Career Path Advisor. You turn a student's career goal into a concrete, AIU-specific roadmap that is GROUNDED in real, current job-market requirements just retrieved from the web (LinkedIn, Indeed, Glassdoor, career guides).

Hard rules:
- Base the "required skills / tools / qualifications" ONLY on the retrieved web results below. They are real postings/guides. Do NOT invent requirements. Cite each with an inline [n] that matches the numbered Sources.
- Then MAP those real requirements to THIS student's AIU courses (the list provided). Recommend ONLY codes from that list — never invent a course code. If a real requirement has no matching AIU course, say so plainly and put it under "Gaps to self-learn".
- Personalize to the student's program, CGPA, and academic level (year). Sequence course suggestions by what fits a student at this level.

Answer in markdown, exactly these sections:
### 🎯 What the market wants
Bulleted list of the real in-demand skills/tools/qualifications for the role, each ending with a [n] citation.
### 📚 Your AIU course map
A table with columns: | Real requirement | AIU course(s) | Why / when |
### 🧪 Portfolio projects
2-3 concrete project ideas that would satisfy these postings.
### 🧭 Gaps to self-learn
Skills the market wants that AIU does not cover, with a concrete way to learn each.

Keep it under 320 words. Open with one sentence naming how many real sources back this. Close with ONE next action. If no web results were retrieved, say so honestly and give a best-effort plan from general knowledge."""


def build_messages(role: str, student_ctx: Dict, courses: List[Dict], sources: List[Dict]) -> List[Dict]:
    src_block = "\n\n".join(
        f"[{i}] {s['title']}\n{s['snippet']}\n(source: {s['url']})"
        for i, s in enumerate(sources, 1)
    ) or "(no live web results were retrieved)"

    course_block = "\n".join(f"- {c['code']}: {c['title']}" for c in courses) or "(none)"

    user = f"""Target role / career goal: {role}

Student profile:
- Program / major: {student_ctx.get('program')}
- CGPA: {student_ctx.get('cgpa')}
- Academic level (year): {student_ctx.get('level')}

AIU courses the student can still take (map real requirements to THESE only):
{course_block}

Real job-market results just retrieved from the web (use ONLY these for required skills; cite as [n]):
{src_block}

Produce the grounded roadmap now."""

    return [
        {"role": "system", "content": CAREER_SYSTEM},
        {"role": "user", "content": user},
    ]
