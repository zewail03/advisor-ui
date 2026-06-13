"""AI admin assistant — natural-language data queries + anomaly detection.

Design principle (committee-defensible): the LLM never invents numbers. It only
(a) PLANS which real query to run from a fixed catalog, and (b) PHRASES the
result. Every figure returned comes from a live SQL query against the DB, and
each answer ships with the `source` (the query that produced it) for audit.

Read-only — any authenticated staff (including the read-only role) may use it.
"""
import json
import re
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ai.groq_client import FAST_MODEL, PRIMARY_MODEL, complete
from core.database import get_db
from core.security import get_current_staff
from models.course import Course, Section
from models.enrollment import Enrollment, Grade
from models.financial import FinancialAccount
from models.staff import Staff
from models.student import Student
from services.audit_service import log_action
from services.policy import get_policy

router = APIRouter()

FAIL_LETTERS = ("F", "FW")
COURSE_RE = re.compile(r"\b([A-Za-z]{2,4})\s?-?\s?(\d{3})\b")


def _course_code(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    m = COURSE_RE.search(raw)
    if m:
        return (m.group(1) + m.group(2)).upper()
    return raw.upper().replace(" ", "").replace("-", "") or None


def _enrolled_subq():
    """Active-enrollment counts per section."""
    return (
        select(Enrollment.section_id.label("sid"), func.count().label("enrolled"))
        .where(Enrollment.status == "Enrolled")
        .group_by(Enrollment.section_id)
        .subquery()
    )


def _result(summary: str, *, metric=None, columns=None, rows=None, source: str = "") -> dict:
    return {
        "summary": summary,
        "metric": metric,
        "columns": columns or [],
        "rows": rows or [],
        "source": source,
    }


# --------------------------------------------------------------------------- #
# Real-data tools — each returns a uniform dict the responder phrases.
# --------------------------------------------------------------------------- #
async def t_at_risk(db: AsyncSession, **_) -> dict:
    thr = await get_policy("standing.at_risk_cgpa", db)
    total = int((await db.execute(
        select(func.count()).select_from(Student).where(Student.cgpa < thr)
    )).scalar() or 0)
    rows = (await db.execute(
        select(Student.student_code, Student.full_name, Student.cgpa)
        .where(Student.cgpa < thr).order_by(Student.cgpa.asc()).limit(10)
    )).all()
    return _result(
        f"{total} students are below the at-risk CGPA threshold of {thr}.",
        metric=total,
        columns=["Code", "Name", "CGPA"],
        rows=[[c, n, round(g, 2) if g is not None else None] for c, n, g in rows],
        source=f"students WHERE cgpa < {thr}  (threshold from business rules)",
    )


async def t_count_students(db: AsyncSession, status: Optional[str] = None, **_) -> dict:
    q = select(func.count()).select_from(Student)
    if status:
        q = q.where(Student.status == status)
    total = int((await db.execute(q)).scalar() or 0)
    breakdown = (await db.execute(
        select(Student.status, func.count()).group_by(Student.status)
    )).all()
    label = f"with status '{status}'" if status else "in total"
    return _result(
        f"There are {total} students {label}.",
        metric=total,
        columns=["Status", "Count"],
        rows=[[s, int(c)] for s, c in breakdown],
        source="students GROUP BY status",
    )


async def t_failing_in_course(db: AsyncSession, course_code: Optional[str] = None, **_) -> dict:
    code = _course_code(course_code)
    if not code:
        return _result("Please name a course, e.g. \"failing CSE233\".")
    rows = (await db.execute(
        select(Student.student_code, Student.full_name, Grade.grade_letter)
        .select_from(Grade)
        .join(Enrollment, Grade.enrollment_id == Enrollment.enrollment_id)
        .join(Section, Enrollment.section_id == Section.section_id)
        .join(Student, Enrollment.student_id == Student.student_id)
        .where(func.upper(Section.course_code) == code)
        .where(Grade.grade_letter.in_(FAIL_LETTERS))
        .order_by(Student.student_code)
    )).all()
    return _result(
        f"{len(rows)} students have a failing grade (F/FW) in {code}.",
        metric=len(rows),
        columns=["Code", "Name", "Grade"],
        rows=[[c, n, g] for c, n, g in rows],
        source=f"grades JOIN enrollments JOIN sections WHERE course_code='{code}' AND grade_letter IN ('F','FW')",
    )


async def t_course_enrollment(db: AsyncSession, course_code: Optional[str] = None, **_) -> dict:
    code = _course_code(course_code)
    if not code:
        return _result("Please name a course, e.g. \"enrolled in CSE233\".")
    total = int((await db.execute(
        select(func.count()).select_from(Enrollment)
        .join(Section, Enrollment.section_id == Section.section_id)
        .where(func.upper(Section.course_code) == code)
        .where(Enrollment.status == "Enrolled")
    )).scalar() or 0)
    sub = _enrolled_subq()
    rows = (await db.execute(
        select(Section.section_number, Section.capacity, func.coalesce(sub.c.enrolled, 0))
        .select_from(Section)
        .outerjoin(sub, sub.c.sid == Section.section_id)
        .where(func.upper(Section.course_code) == code)
        .order_by(Section.section_number)
    )).all()
    return _result(
        f"{total} students are currently enrolled in {code} across {len(rows)} section(s).",
        metric=total,
        columns=["Section", "Capacity", "Enrolled"],
        rows=[[sn, cap, int(en)] for sn, cap, en in rows],
        source=f"enrollments JOIN sections WHERE course_code='{code}' AND status='Enrolled'",
    )


async def t_top_students(db: AsyncSession, limit: Any = 5, **_) -> dict:
    n = min(max(int(limit or 5), 1), 25)
    rows = (await db.execute(
        select(Student.student_code, Student.full_name, Student.cgpa)
        .order_by(Student.cgpa.desc()).limit(n)
    )).all()
    return _result(
        f"Top {len(rows)} students by CGPA.",
        metric=len(rows),
        columns=["Code", "Name", "CGPA"],
        rows=[[c, nm, round(g, 2) if g is not None else None] for c, nm, g in rows],
        source=f"students ORDER BY cgpa DESC LIMIT {n}",
    )


async def t_bottom_students(db: AsyncSession, limit: Any = 5, **_) -> dict:
    n = min(max(int(limit or 5), 1), 25)
    rows = (await db.execute(
        select(Student.student_code, Student.full_name, Student.cgpa)
        .where(Student.cgpa > 0).order_by(Student.cgpa.asc()).limit(n)
    )).all()
    return _result(
        f"Lowest {len(rows)} students by CGPA (excluding 0.0).",
        metric=len(rows),
        columns=["Code", "Name", "CGPA"],
        rows=[[c, nm, round(g, 2) if g is not None else None] for c, nm, g in rows],
        source=f"students WHERE cgpa > 0 ORDER BY cgpa ASC LIMIT {n}",
    )


async def t_outstanding(db: AsyncSession, **_) -> dict:
    total = int((await db.execute(
        select(func.coalesce(func.sum(FinancialAccount.current_balance), 0))
        .where(FinancialAccount.current_balance > 0)
    )).scalar() or 0)
    cnt = int((await db.execute(
        select(func.count()).select_from(FinancialAccount)
        .where(FinancialAccount.current_balance > 0)
    )).scalar() or 0)
    rows = (await db.execute(
        select(Student.student_code, Student.full_name, FinancialAccount.current_balance)
        .join(Student, Student.student_id == FinancialAccount.student_id)
        .where(FinancialAccount.current_balance > 0)
        .order_by(FinancialAccount.current_balance.desc()).limit(10)
    )).all()
    return _result(
        f"{cnt} students owe a combined {total:,} EGP in outstanding balances.",
        metric=total,
        columns=["Code", "Name", "Balance (EGP)"],
        rows=[[c, n, int(b)] for c, n, b in rows],
        source="financial_accounts WHERE current_balance > 0",
    )


async def t_overcapacity(db: AsyncSession, **_) -> dict:
    sub = _enrolled_subq()
    rows = (await db.execute(
        select(Course.code, Section.section_number, Section.capacity, sub.c.enrolled)
        .select_from(Section)
        .join(sub, sub.c.sid == Section.section_id)
        .join(Course, Section.course_code == Course.code)
        .where(sub.c.enrolled > Section.capacity)
        .order_by((sub.c.enrolled - Section.capacity).desc())
    )).all()
    return _result(
        f"{len(rows)} section(s) are enrolled beyond capacity.",
        metric=len(rows),
        columns=["Course", "Section", "Capacity", "Enrolled"],
        rows=[[code, sn, cap, int(en)] for code, sn, cap, en in rows],
        source="sections JOIN (enrolled counts) WHERE enrolled > capacity",
    )


async def t_cgpa_distribution(db: AsyncSession, **_) -> dict:
    bands = [(0.0, 1.0), (1.0, 2.0), (2.0, 2.5), (2.5, 3.0), (3.0, 3.5), (3.5, 4.01)]
    rows = []
    for lo, hi in bands:
        c = int((await db.execute(
            select(func.count()).select_from(Student)
            .where(Student.cgpa >= lo).where(Student.cgpa < hi)
        )).scalar() or 0)
        hi_label = "4.0" if hi > 4 else f"{hi:g}"
        rows.append([f"{lo:g}–{hi_label}", c])
    total = sum(r[1] for r in rows)
    return _result(
        f"CGPA distribution across {total} students.",
        metric=total,
        columns=["CGPA band", "Students"],
        rows=rows,
        source="students grouped into CGPA bands",
    )


TOOLS = {
    "at_risk_students": t_at_risk,
    "count_students": t_count_students,
    "failing_in_course": t_failing_in_course,
    "course_enrollment": t_course_enrollment,
    "top_students": t_top_students,
    "bottom_students": t_bottom_students,
    "outstanding_balance": t_outstanding,
    "overcapacity_sections": t_overcapacity,
    "cgpa_distribution": t_cgpa_distribution,
}

SUGGESTIONS = [
    "How many students are at risk?",
    "How many students are failing CSE233?",
    "Who are the top 5 students by CGPA?",
    "How much tuition is outstanding?",
    "Which sections are over capacity?",
    "Show the CGPA distribution.",
]

PLANNER_SYS = """You route an admin's question to ONE data tool. Respond with ONLY a JSON object:
{"tool": "<name>", "params": {...}}

Tools and params:
- at_risk_students {} — how many / which students have low CGPA / are at risk.
- count_students {"status"?: string} — total students, or count for a status like "Active".
- failing_in_course {"course_code": string} — students failing a specific course.
- course_enrollment {"course_code": string} — how many are enrolled in a course.
- top_students {"limit"?: int} — highest-CGPA students.
- bottom_students {"limit"?: int} — lowest-CGPA students.
- outstanding_balance {} — unpaid tuition / who owes money.
- overcapacity_sections {} — sections enrolled beyond capacity.
- cgpa_distribution {} — spread of students across CGPA bands.

Normalise course codes like "CSE 233" to "CSE233". If nothing fits, use {"tool":"none","params":{}}.
Output JSON only, no prose."""

RESPONDER_SYS = """You are the AIU admin data assistant. Answer the admin's question in 1–3 short sentences
using ONLY the provided query result (it is ground truth from the live database). Be exact with numbers.
Use light **markdown**. You may cite one or two notable rows. Never invent data beyond the result."""


def _keyword_plan(question: str) -> tuple[str, dict]:
    ql = question.lower()
    code = _course_code(question) if COURSE_RE.search(question) else None
    if any(w in ql for w in ("fail", "failing", "failed")) and code:
        return "failing_in_course", {"course_code": code}
    if any(w in ql for w in ("enroll", "registered", "taking", "signed up")) and code:
        return "course_enrollment", {"course_code": code}
    if "at risk" in ql or "at-risk" in ql or "probation" in ql or "struggling" in ql:
        return "at_risk_students", {}
    if any(w in ql for w in ("owe", "outstanding", "unpaid", "balance", "tuition", "debt")):
        return "outstanding_balance", {}
    if any(w in ql for w in ("top", "highest", "best")):
        return "top_students", {}
    if any(w in ql for w in ("bottom", "lowest", "worst")):
        return "bottom_students", {}
    if "capacity" in ql or "overfull" in ql or "over capacity" in ql or "overbooked" in ql:
        return "overcapacity_sections", {}
    if "distribution" in ql or "spread" in ql or "bands" in ql or "histogram" in ql:
        return "cgpa_distribution", {}
    if any(w in ql for w in ("how many student", "total student", "number of student", "count of student")):
        return "count_students", {}
    if code:
        return "course_enrollment", {"course_code": code}
    return "none", {}


async def _plan(question: str) -> tuple[str, dict]:
    try:
        raw = await complete(
            [{"role": "system", "content": PLANNER_SYS}, {"role": "user", "content": question}],
            model=FAST_MODEL,
            temperature=0.0,
            max_tokens=120,
        )
        m = re.search(r"\{.*\}", raw, re.S)
        if m:
            obj = json.loads(m.group(0))
            tool = obj.get("tool")
            if tool in TOOLS:
                return tool, (obj.get("params") or {})
    except Exception:
        pass
    return _keyword_plan(question)


async def _phrase(question: str, result: dict) -> str:
    grounding = {
        "summary": result.get("summary"),
        "metric": result.get("metric"),
        "columns": result.get("columns"),
        "rows": (result.get("rows") or [])[:15],
    }
    try:
        return (await complete(
            [
                {"role": "system", "content": RESPONDER_SYS},
                {
                    "role": "user",
                    "content": f"Question: {question}\n\nQuery result (ground truth):\n{json.dumps(grounding, ensure_ascii=False)}",
                },
            ],
            model=PRIMARY_MODEL,
            temperature=0.3,
            max_tokens=400,
        )).strip() or result.get("summary", "")
    except Exception:
        # LLM down — the deterministic summary is still a correct answer.
        return result.get("summary", "I couldn't compute that.")


class AskBody(BaseModel):
    question: str


@router.get("/assistant/suggestions")
async def suggestions(staff: Staff = Depends(get_current_staff)):
    return {"suggestions": SUGGESTIONS}


@router.post("/assistant/query")
async def assistant_query(
    body: AskBody,
    staff: Staff = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    question = (body.question or "").strip()
    if not question:
        return {"answer": "Ask me something about the student data.", "tool": "none",
                "columns": [], "rows": [], "source": "", "metric": None}

    tool, params = await _plan(question)
    fn = TOOLS.get(tool)
    if not fn:
        return {
            "answer": "I can answer questions about at-risk students, course failures, enrollment, "
                      "outstanding balances, top/bottom students, section capacity, and CGPA distribution. "
                      "Try: **\"How many students are failing CSE233?\"**",
            "tool": "none", "columns": [], "rows": [], "source": "", "metric": None,
        }

    result = await fn(db, **(params or {}))
    answer = await _phrase(question, result)

    await log_action(
        db,
        action="assistant.query",
        entity_type="assistant",
        actor_id=str(staff.staff_id),
        actor_role=staff.role,
        metadata={"question": question, "tool": tool},
        commit=True,
    )

    return {
        "answer": answer,
        "tool": tool,
        "source": result.get("source", ""),
        "columns": result.get("columns", []),
        "rows": result.get("rows", []),
        "metric": result.get("metric"),
    }


@router.get("/assistant/anomalies")
async def anomalies(
    staff: Staff = Depends(get_current_staff),
    db: AsyncSession = Depends(get_db),
):
    """Scan live data for integrity / operational anomalies. All checks are real SQL."""
    checks: list[dict] = []
    sub = _enrolled_subq()

    def add(key, title, severity_on_hit, count, detail, sample):
        checks.append({
            "key": key,
            "title": title,
            "severity": severity_on_hit if count else "ok",
            "count": count,
            "detail": detail,
            "sample": sample[:5],
        })

    # 1) Sections enrolled beyond capacity
    oc = (await db.execute(
        select(Course.code, Section.section_number, Section.capacity, sub.c.enrolled)
        .select_from(Section)
        .join(sub, sub.c.sid == Section.section_id)
        .join(Course, Section.course_code == Course.code)
        .where(sub.c.enrolled > Section.capacity)
        .order_by((sub.c.enrolled - Section.capacity).desc())
    )).all()
    add("overcapacity", "Sections over capacity", "high", len(oc),
        "Active enrollment exceeds the section's stated capacity.",
        [f"{c} {sn} — {int(en)}/{cap}" for c, sn, cap, en in oc])

    # 2) Financial balance invariant violations
    inv = (await db.execute(
        select(Student.student_code, FinancialAccount.current_balance,
               FinancialAccount.total_charges, FinancialAccount.scholarship_credit,
               FinancialAccount.payments_made)
        .join(Student, Student.student_id == FinancialAccount.student_id)
        .where(FinancialAccount.current_balance != (
            FinancialAccount.total_charges - FinancialAccount.scholarship_credit - FinancialAccount.payments_made))
    )).all()
    add("balance_invariant", "Financial balance mismatches", "high", len(inv),
        "current_balance ≠ total_charges − scholarship_credit − payments_made.",
        [f"{code}: {int(bal):,} ≠ {int(ch - sch - paid):,}" for code, bal, ch, sch, paid in inv])

    # 3) Negative balances (overpayment / credit)
    neg = (await db.execute(
        select(Student.student_code, FinancialAccount.current_balance)
        .join(Student, Student.student_id == FinancialAccount.student_id)
        .where(FinancialAccount.current_balance < 0)
        .order_by(FinancialAccount.current_balance.asc())
    )).all()
    add("negative_balance", "Negative balances (overpaid)", "medium", len(neg),
        "Students whose account is in credit — verify refunds / mis-postings.",
        [f"{code}: {int(bal):,} EGP" for code, bal in neg])

    # 4) CGPA out of the valid 0–4 range
    bad_cgpa = (await db.execute(
        select(Student.student_code, Student.cgpa)
        .where((Student.cgpa < 0) | (Student.cgpa > 4.0))
    )).all()
    add("cgpa_range", "CGPA out of range", "high", len(bad_cgpa),
        "Stored CGPA falls outside the valid 0.00–4.00 scale.",
        [f"{code}: {g}" for code, g in bad_cgpa])

    # 5) Active students with a 0.0 CGPA (possible missing/unposted grades)
    zero = (await db.execute(
        select(Student.student_code, Student.full_name)
        .where(Student.status == "Active").where(Student.cgpa == 0)
    )).all()
    add("active_zero_cgpa", "Active students with 0.0 CGPA", "medium", len(zero),
        "Active students with no computed CGPA — grades may be missing.",
        [f"{code} — {name}" for code, name in zero])

    # 6) Open sections with nobody enrolled
    empty = (await db.execute(
        select(Course.code, Section.section_number)
        .select_from(Section)
        .outerjoin(sub, sub.c.sid == Section.section_id)
        .join(Course, Section.course_code == Course.code)
        .where(Section.status == "Open")
        .where(Section.capacity > 0)
        .where(func.coalesce(sub.c.enrolled, 0) == 0)
    )).all()
    add("empty_open", "Open sections with no enrollment", "low", len(empty),
        "Sections marked Open that currently have zero students.",
        [f"{c} {sn}" for c, sn in empty])

    flagged = sum(1 for c in checks if c["count"] > 0)
    return {
        "generated_for": staff.full_name,
        "total_checks": len(checks),
        "flagged": flagged,
        "checks": checks,
    }
