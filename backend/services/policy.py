"""Business-rule configuration service.

DEFAULTS is the single source of truth for every editable rule: its type,
category, label, unit, and code default. The DB (policy_config) only stores
overrides. `get_policy` returns the live value (override or default), typed,
from an in-process cache that's refreshed when a value is changed.
"""
from datetime import datetime
from typing import Any, Dict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.policy import PolicyConfig

# key -> metadata + default. type ∈ {int, float, bool}
DEFAULTS: Dict[str, dict] = {
    # ---- Academic standing ----
    "standing.at_risk_cgpa": {"default": 2.0, "type": "float", "category": "Academic Standing",
        "label": "At-risk CGPA threshold", "unit": "CGPA",
        "description": "Students with CGPA below this are flagged at-risk."},
    "standing.probation_cgpa": {"default": 2.0, "type": "float", "category": "Academic Standing",
        "label": "Probation CGPA threshold", "unit": "CGPA",
        "description": "CGPA below which a student is placed on probation (semester 3 onward, §12.1)."},
    "standing.probation_cgpa_early": {"default": 1.667, "type": "float", "category": "Academic Standing",
        "label": "Warning CGPA threshold — semester 3", "unit": "CGPA",
        "description": "CGPA bar applied at the end of semester 3, when warnings start. No CGPA bar applies in semesters 1–2 (Dr. Ashraf §1.2–1.3, §2.1)."},
    "standing.warning_start_semester": {"default": 3, "type": "int", "category": "Academic Standing",
        "label": "Warnings start at semester", "unit": "semester",
        "description": "First main semester after which a low CGPA earns a warning; before this CGPA does not affect standing (Dr. Ashraf §1.2, §2.1)."},
    "standing.dismissal_warnings": {"default": 4, "type": "int", "category": "Academic Standing",
        "label": "Dismissal — consecutive warnings", "unit": "warnings",
        "description": "Consecutive warnings (CGPA 1.0–2.0) that trigger dismissal; non-consecutive warnings reset the count (Dr. Ashraf §2.2, §2.4)."},
    "standing.dismissal_warnings_severe": {"default": 3, "type": "int", "category": "Academic Standing",
        "label": "Dismissal — consecutive severe warnings", "unit": "warnings",
        "description": "Consecutive semesters with CGPA below the severe bar that trigger dismissal (Dr. Ashraf §2.3)."},
    "standing.severe_cgpa": {"default": 1.0, "type": "float", "category": "Academic Standing",
        "label": "Severe-warning CGPA threshold", "unit": "CGPA",
        "description": "CGPA below this counts on the faster 3-warning dismissal track (Dr. Ashraf §2.3)."},
    "standing.summer_recovery": {"default": True, "type": "bool", "category": "Academic Standing",
        "label": "Summer clears warning status", "unit": "",
        "description": "If a summer term lifts CGPA to/above the applicable bar, the student returns to good standing and the warning streak resets (Dr. Ashraf §3)."},
    # ---- Finance (applied at billing/seed time) ----
    "finance.tuition_per_credit": {"default": 2750, "type": "int", "category": "Finance",
        "label": "Tuition per credit hour", "unit": "EGP",
        "description": "Charged per registered credit hour."},
    "finance.transport_fee": {"default": 13000, "type": "int", "category": "Finance",
        "label": "Transportation fee", "unit": "EGP",
        "description": "Flat per-term transportation charge."},
    "finance.scholarship_cgpa": {"default": 3.9, "type": "float", "category": "Finance",
        "label": "Merit scholarship CGPA", "unit": "CGPA",
        "description": "Minimum CGPA for the 100% tuition Academic Excellence award."},
    # ---- Capstone eligibility (% of program credits completed) ----
    "capstone.field_training_a_pct": {"default": 60, "type": "int", "category": "Capstone",
        "label": "Field Training A — required completion", "unit": "%",
        "description": "Completed-credit % needed to register Field Training A."},
    "capstone.field_training_b_pct": {"default": 75, "type": "int", "category": "Capstone",
        "label": "Field Training B — required completion", "unit": "%",
        "description": "Completed-credit % needed to register Field Training B."},
    "capstone.grad_project_i_pct": {"default": 80, "type": "int", "category": "Capstone",
        "label": "Graduation Project I — required completion", "unit": "%",
        "description": "Completed-credit % needed to register Graduation Project I."},
    "capstone.grad_project_ii_pct": {"default": 90, "type": "int", "category": "Capstone",
        "label": "Graduation Project II — required completion", "unit": "%",
        "description": "Completed-credit % needed to register Graduation Project II."},
    # ---- Enrollment (registration validation) ----
    "enrollment.credit_limit_high": {"default": 22, "type": "int", "category": "Enrollment",
        "label": "Overload credit limit — CGPA > 3.0", "unit": "CH",
        "description": "Overload allowed from semester 4 on for students with CGPA above 3.0 (Dr. Ashraf §1.4)."},
    "enrollment.credit_limit_standard": {"default": 20, "type": "int", "category": "Enrollment",
        "label": "Normal load credit limit", "unit": "CH",
        "description": "Normal-load max credit hours per regular term (CGPA at/above the applicable bar)."},
    "enrollment.credit_limit_low": {"default": 12, "type": "int", "category": "Enrollment",
        "label": "Half load credit limit", "unit": "CH",
        "description": "Reduced (half) load when CGPA is below the applicable bar — <1.667 after semester 2, <2.0 from semester 4 (Dr. Ashraf §1.3–1.4)."},
    "enrollment.sem2_credits": {"default": 16, "type": "int", "category": "Enrollment",
        "label": "Semester-2 credit limit", "unit": "CH",
        "description": "Fixed registration load in semester 2 — every student moves on from semester 1 regardless of CGPA (Dr. Ashraf §1.2)."},
    "enrollment.sem1_credits_math0_pass": {"default": 16, "type": "int", "category": "Enrollment",
        "label": "Semester-1 credit limit — Math 0 passed", "unit": "CH",
        "description": "First-semester load for students who passed the Math 0 placement exam (Dr. Ashraf §1.1)."},
    "enrollment.sem1_credits_math0_fail": {"default": 12, "type": "int", "category": "Enrollment",
        "label": "Semester-1 credit limit — Math 0 failed", "unit": "CH",
        "description": "Reduced first-semester load for students who did not pass the Math 0 placement exam (Dr. Ashraf §1.1)."},
    "enrollment.overload_min_cgpa": {"default": 3.0, "type": "float", "category": "Enrollment",
        "label": "Overload minimum CGPA", "unit": "CGPA",
        "description": "CGPA above which overload registration is allowed, from semester 4 on (Dr. Ashraf §1.4)."},
    "enrollment.credit_limit_summer": {"default": 9, "type": "int", "category": "Enrollment",
        "label": "Credit limit — summer term", "unit": "CH",
        "description": "Max credit hours in a summer term (all students)."},
    "enrollment.prereq_min_points": {"default": 1.0, "type": "float", "category": "Enrollment",
        "label": "Prerequisite passing grade", "unit": "points",
        "description": "Minimum grade points (D = 1.0) for a course to satisfy a prerequisite."},
    # ---- Petitions ----
    "petition.freeze_max_total": {"default": 4, "type": "int", "category": "Petitions",
        "label": "Max frozen semesters — total", "unit": "semesters",
        "description": "Total cap on approved semester freezes across the entire program (§15.3)."},
    "petition.freeze_max_consecutive": {"default": 2, "type": "int", "category": "Petitions",
        "label": "Max frozen semesters — consecutive", "unit": "semesters",
        "description": "Maximum consecutive main semesters that may be frozen (§15.3)."},
    "petition.transfer_min_cgpa": {"default": 2.0, "type": "float", "category": "Petitions",
        "label": "Transfer minimum CGPA", "unit": "CGPA",
        "description": "Minimum CGPA to request a program transfer."},
    "petition.final_chance_min_completion_pct": {"default": 80, "type": "int", "category": "Petitions",
        "label": "Final-chance minimum completion", "unit": "%",
        "description": "Minimum % of required credit hours completed to petition final chance (§14.1)."},
    # ---- Retake / attendance ----
    "retake.cap_after_fail": {"default": 3.3, "type": "float", "category": "Retake & Attendance",
        "label": "Grade cap after failing retake", "unit": "points",
        "description": "Max grade points awarded on a retake of a failed course (B+ = 3.3)."},
    "retake.improvement_cap_4yr": {"default": 9, "type": "int", "category": "Retake & Attendance",
        "label": "Improvement-retake CH cap — 4-year programs", "unit": "CH",
        "description": "Lifetime credit-hour cap on passed-course improvement retakes in 4-year programs (§10.2). Beyond it, attempts are averaged."},
    "retake.improvement_cap_5yr": {"default": 12, "type": "int", "category": "Retake & Attendance",
        "label": "Improvement-retake CH cap — 5-year programs", "unit": "CH",
        "description": "Lifetime credit-hour cap on passed-course improvement retakes in 5-year programs (§10.2). Beyond it, attempts are averaged."},
    "attendance.fw_threshold_pct": {"default": 25, "type": "int", "category": "Retake & Attendance",
        "label": "Force-withdrawal absence threshold", "unit": "%",
        "description": "Absence % that triggers an automatic Force Withdrawal.",
        "enforced": False},  # no attendance data in this dataset yet
}

_cache: Dict[str, Any] = {}
_loaded = False


def _coerce(raw: Any, typ: str) -> Any:
    if typ == "int":
        return int(float(raw))
    if typ == "float":
        return float(raw)
    if typ == "bool":
        return str(raw).lower() in ("1", "true", "yes")
    return raw


async def _ensure_loaded(db: AsyncSession) -> None:
    global _loaded
    if _loaded:
        return
    overrides = {
        row.key: row.value
        for row in (await db.execute(select(PolicyConfig))).scalars().all()
    }
    for key, meta in DEFAULTS.items():
        raw = overrides.get(key, meta["default"])
        _cache[key] = _coerce(raw, meta["type"])
    _loaded = True


async def get_policy(key: str, db: AsyncSession) -> Any:
    """Live value for a rule (override or code default), correctly typed."""
    await _ensure_loaded(db)
    if key in _cache:
        return _cache[key]
    meta = DEFAULTS.get(key)
    return _coerce(meta["default"], meta["type"]) if meta else None


async def all_policies(db: AsyncSession) -> list:
    await _ensure_loaded(db)
    overridden = {
        row.key: row
        for row in (await db.execute(select(PolicyConfig))).scalars().all()
    }
    out = []
    for key, meta in DEFAULTS.items():
        row = overridden.get(key)
        default_val = _coerce(meta["default"], meta["type"])
        value = _cache.get(key, default_val)
        out.append({
            "key": key,
            "value": value,
            "default": default_val,
            "is_overridden": value != default_val,
            "type": meta["type"],
            "category": meta["category"],
            "label": meta["label"],
            "unit": meta["unit"],
            "description": meta["description"],
            "enforced": meta.get("enforced", True),
            "updated_at": row.updated_at.isoformat() if row and row.updated_at else None,
            "updated_by": row.updated_by if row else None,
        })
    return out


async def set_policy(key: str, value: Any, db: AsyncSession, updated_by: str) -> dict:
    meta = DEFAULTS.get(key)
    if not meta:
        raise KeyError(key)
    typed = _coerce(value, meta["type"])
    old = await get_policy(key, db)
    row = await db.get(PolicyConfig, key)
    if row:
        row.value = str(typed)
        row.updated_at = datetime.utcnow()
        row.updated_by = updated_by
    else:
        db.add(PolicyConfig(key=key, value=str(typed), updated_by=updated_by))
    _cache[key] = typed  # refresh cache immediately
    return {"key": key, "old": old, "new": typed}


async def seed_policies(db: AsyncSession) -> int:
    """Insert any missing rule with its default (idempotent)."""
    existing = {
        row.key for row in (await db.execute(select(PolicyConfig))).scalars().all()
    }
    created = 0
    for key, meta in DEFAULTS.items():
        if key not in existing:
            db.add(PolicyConfig(key=key, value=str(meta["default"]), updated_by="system"))
            created += 1
    if created:
        await db.commit()
    global _loaded
    _loaded = False  # force reload on next read
    return created
