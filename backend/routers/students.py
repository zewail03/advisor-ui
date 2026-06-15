"""Student-facing endpoints.

Rewritten for the real AIU schema:
  * Student PK is integer `student_id`, natural key is `student_code`.
  * AcademicStanding is one row per (student_code, semester) — always take latest.
  * "Transcript" is Enrollment JOIN Grade JOIN Section JOIN Course JOIN Semester.
  * Degree requirements live in RequirementGroupCourse (course_code + program_id/major_id).
  * StudentProfile/TranscriptRecord models no longer exist; we derive everything from
    the above tables and fall back to safe empty strings for legacy profile fields
    the frontend still renders.
"""
from collections import defaultdict
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_student
from models.academic import (
    AcademicStanding,
    RequirementGroupCourse,
    Semester,
)
from models.advisor import Advisor, AdvisorAssignment
from models.course import Course, Section
from models.enrollment import Enrollment, Grade
from models.student import Major, Program, Student
from schemas.student import ProfileUpdate
from services.course_recommender import recommend_courses
from services.recovery_service import build_recovery_plan
from services.requirement_tree import all_plan_codes, build_requirement_tree

router = APIRouter()


_STANDING_RISK = {
    "Probation": "You're on academic probation. Raise your CGPA above 2.0 to return to good standing.",
    "Final Chance": "Final chance — one more sub-2.0 semester and you may be dismissed. See your advisor immediately.",
    "Dismissed": "You have been dismissed from your program. Contact the registrar's office.",
    "Warning": "Academic warning — your CGPA is below the safe threshold. Consider a lighter load or retakes.",
}


async def _latest_standing(
    student_code: str, db: AsyncSession
) -> Optional[AcademicStanding]:
    row = await db.execute(
        select(AcademicStanding)
        .where(AcademicStanding.student_code == student_code)
        .order_by(AcademicStanding.semester_id.desc())
        .limit(1)
    )
    return row.scalar_one_or_none()


async def _transcript_rows(student_id: int, db: AsyncSession) -> List[Dict]:
    rows = await db.execute(
        select(Enrollment, Grade, Section, Course, Semester)
        .join(Grade, Grade.enrollment_id == Enrollment.enrollment_id, isouter=True)
        .join(Section, Section.section_id == Enrollment.section_id)
        .join(Course, Course.code == Section.course_code)
        .join(Semester, Semester.semester_id == Section.semester_id)
        .where(Enrollment.student_id == student_id)
    )
    out: List[Dict] = []
    for enrollment, grade, section, course, semester in rows.all():
        out.append(
            {
                "enrollment_id": enrollment.enrollment_id,
                "semester_code": semester.code,
                "semester_id": semester.semester_id,
                "course_code": course.code,
                "course_name": course.name,
                "credits": course.credits,
                "grade_letter": grade.grade_letter if grade else None,
                "grade_points": float(grade.grade_points) if grade and grade.grade_points is not None else None,
                "percentage": float(grade.percentage) if grade and grade.percentage is not None else None,
                "counts_in_gpa": bool(grade.counts_in_gpa) if grade else True,
                "status": enrollment.status,
            }
        )
    return out


async def _me_payload(student: Student, db: AsyncSession) -> Dict:
    """Full profile payload — shared by GET /me and PATCH /me so the
    frontend always gets the same shape back after a save."""
    program = await db.get(Program, student.program_id) if student.program_id else None
    standing = await _latest_standing(student.student_code, db)

    # Calculate CGPA from actual course grades so math is verifiable
    transcript = await _transcript_rows(student.student_id, db)
    tot_pts = 0.0
    tot_cr = 0
    for r in transcript:
        if r["grade_points"] is not None and r["counts_in_gpa"]:
            tot_pts += r["grade_points"] * r["credits"]
            tot_cr += r["credits"]
    calculated_cgpa = round(tot_pts / tot_cr, 3) if tot_cr else 0.0

    parts = (student.full_name or "").split(" ", 1)
    first_name = parts[0] if parts else ""
    last_name = parts[1] if len(parts) > 1 else ""

    major = await db.get(Major, student.major_id) if student.major_id else None
    advisor_name = (
        await db.execute(
            select(Advisor.full_name)
            .join(AdvisorAssignment, AdvisorAssignment.advisor_id == Advisor.advisor_id)
            .where(AdvisorAssignment.student_code == student.student_code)
            .limit(1)
        )
    ).scalar_one_or_none()

    profile_fields = {
        # The profile page reads `student_id` as the human-visible ID.
        "student_id": student.student_code,
        "username": student.student_code,
        "phone": student.phone or "",
        "home_address": student.home_address or "",
        "city": student.city or "",
        "postal_code": student.postal_code or "",
        "emergency_contact_name": student.emergency_contact_name or "",
        "emergency_relationship": student.emergency_relationship or "",
        "emergency_phone": student.emergency_phone or "",
        "emergency_email": student.emergency_email or "",
        "major": major.name if major else "",
        "academic_year": f"Year {student.level}" if student.level else "",
        "expected_graduation": student.expected_graduation.isoformat() if student.expected_graduation else "",
        "academic_advisor": advisor_name or "",
        # Student-entered personal fields (not in the registrar dataset):
        "date_of_birth": student.date_of_birth or "",
        "gender": student.gender or "",
        "nationality": student.nationality or "",
        "school_id": student.school_id or "",
        "notif_email": 1,
        "notif_sms": 1,
        "notif_advisor": 1,
        "public_profile": 0,
    }

    return {
        "id": student.student_id,
        "student_number": student.student_code,
        "student_code": student.student_code,
        "full_name": student.full_name,
        "first_name": first_name,
        "last_name": last_name,
        "email": student.email,
        "academic_level": student.level,
        "program": {"code": program.code, "name": program.name} if program else None,
        "standing": standing.status if standing else "Good Standing",
        "cgpa": calculated_cgpa,
        # Flattened: the profile page reads these from the top level.
        **profile_fields,
        # Kept nested for any older callers.
        "profile": profile_fields,
    }


@router.get("/me")
async def get_me(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    return await _me_payload(student, db)


@router.patch("/me")
async def update_me(
    patch: ProfileUpdate,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    data = patch.model_dump(exclude_none=True)
    editable = (
        "phone", "date_of_birth", "gender", "nationality", "school_id",
        "home_address", "city", "postal_code",
        "emergency_contact_name", "emergency_relationship",
        "emergency_phone", "emergency_email",
    )
    changed = False
    for field in editable:
        if field in data:
            setattr(student, field, data[field])
            changed = True
    if changed:
        await db.commit()
    # Return the same shape as GET /me — the page replaces its state with this.
    return await _me_payload(student, db)


@router.get("/me/gpa")
async def get_gpa(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    transcript = await _transcript_rows(student.student_id, db)

    # Two views per semester, ordered by semester_id:
    #  * by_sem_all  -> the HISTORICAL term GPA from every graded course that term
    #    (matches the Semester-by-Semester list and a real transcript — a later
    #    retake never rewrites a past term's GPA).
    #  * by_sem_counted -> only grades that still count (latest-counts policy:
    #    superseded retakes have counts_in_gpa=False) -> the authoritative CGPA.
    by_sem_all: Dict[str, List] = defaultdict(list)
    by_sem_counted: Dict[str, List] = defaultdict(list)
    sem_ids: Dict[str, int] = {}
    for r in transcript:
        if r["grade_points"] is not None:
            by_sem_all[r["semester_code"]].append((r["grade_points"], r["credits"]))
            if r["counts_in_gpa"]:
                by_sem_counted[r["semester_code"]].append((r["grade_points"], r["credits"]))
        if r["semester_code"] not in sem_ids:
            sem_ids[r["semester_code"]] = r["semester_id"]

    history = []
    running_pts = 0.0
    running_cr = 0
    for sem_code in sorted(by_sem_all.keys(), key=lambda s: sem_ids.get(s, 0)):
        all_rows = by_sem_all[sem_code]
        tot_pts = sum(pts * cr for pts, cr in all_rows)
        tot_cr = sum(cr for _, cr in all_rows)
        counted = by_sem_counted.get(sem_code, [])
        running_pts += sum(pts * cr for pts, cr in counted)
        running_cr += sum(cr for _, cr in counted)
        history.append({
            "semester": sem_code,
            "sgpa": round(tot_pts / tot_cr, 3) if tot_cr else 0.0,
            "cgpa": round(running_pts / running_cr, 3) if running_cr else 0.0,
        })

    cgpa = round(running_pts / running_cr, 3) if running_cr else 0.0
    sgpa_current = history[-1]["sgpa"] if history else 0.0

    # Completed credits: courses with a passing grade
    completed = sum(
        r["credits"] for r in transcript
        if r["grade_letter"] and r["grade_letter"] not in ("F", "W", "WP", "WF", "I")
    )
    total_program_credits = 144

    return {
        "cgpa": cgpa,
        "sgpa_current": sgpa_current,
        "semester_history": history,
        "completed_credits": completed,
        "total_credits": total_program_credits,
    }


@router.get("/me/standing")
async def get_standing(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    s = await _latest_standing(student.student_code, db)
    if not s:
        return {
            "standing": "Good Standing",
            "cgpa": float(student.cgpa or 0.0),
            "consecutive_probation_semesters": 0,
            "risk_message": None,
        }
    status = (s.status or "Good Standing").strip()
    return {
        "standing": status,
        "cgpa": float(s.cgpa) if s.cgpa is not None else 0.0,
        "consecutive_probation_semesters": int(s.probation_semesters or 0),
        "risk_message": _STANDING_RISK.get(status),
    }


@router.get("/me/grades")
async def get_grades(
    semester: Optional[str] = Query(None),
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    rows = await _transcript_rows(student.student_id, db)
    if semester:
        rows = [r for r in rows if r["semester_code"] == semester]
    return [
        {
            "semester": r["semester_code"],
            "course_code": r["course_code"],
            "course_name": r["course_name"],
            "credits": r["credits"],
            "grade": r["grade_letter"],
            "grade_points": r["grade_points"],
            "status": r["status"],
        }
        for r in rows
    ]


@router.get("/me/transcript")
async def get_transcript(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    rows = await _transcript_rows(student.student_id, db)

    by_sem: Dict[str, List[Dict]] = defaultdict(list)
    for r in rows:
        by_sem[r["semester_code"]].append(
            {
                "course_code": r["course_code"],
                "course_name": r["course_name"],
                "credits": r["credits"],
                "grade": r["grade_letter"],
                "grade_points": r["grade_points"],
                "status": r["status"],
                # False when a later retake superseded this attempt — counts toward
                # the historical term GPA but NOT the cumulative (latest-counts).
                "counts_in_gpa": r["counts_in_gpa"],
            }
        )
    out: Dict[str, Dict] = {}
    for sem, courses in sorted(by_sem.items()):
        # Calculate from actual course grades so the math is always verifiable
        graded = [c for c in courses if c["grade_points"] is not None]
        if graded:
            tp = sum(c["grade_points"] * c["credits"] for c in graded)
            tc = sum(c["credits"] for c in graded)
            term_gpa = round(tp / tc, 3) if tc else 0.0
        else:
            term_gpa = None
        out[sem] = {"term_gpa": term_gpa, "courses": courses}
    return out


async def _requirement_rows(
    program_id: int, major_id: Optional[int], db: AsyncSession
) -> List[RequirementGroupCourse]:
    q = select(RequirementGroupCourse).where(RequirementGroupCourse.program_id == program_id)
    if major_id is not None:
        q = q.where(
            (RequirementGroupCourse.major_id == major_id)
            | (RequirementGroupCourse.major_id.is_(None))
        )
    else:
        q = q.where(RequirementGroupCourse.major_id.is_(None))
    return list((await db.execute(q)).scalars().all())


async def _passed_map(student_id: int, db: AsyncSession) -> Dict[str, Dict]:
    """course_code -> best passed transcript row (grade_points >= 1.0)."""
    rows = await _transcript_rows(student_id, db)
    best: Dict[str, Dict] = {}
    for r in rows:
        if r["grade_points"] is None or r["grade_points"] < 1.0:
            continue
        existing = best.get(r["course_code"])
        if existing is None or r["grade_points"] > existing["grade_points"]:
            best[r["course_code"]] = r
    return best


@router.get("/me/requirements")
async def get_requirements(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    if not student.program_id:
        return {"requirements": [], "program": None}

    program = await db.get(Program, student.program_id)
    req_rows = await _requirement_rows(student.program_id, student.major_id, db)
    passed = await _passed_map(student.student_id, db)

    # Collect credits for requirement courses in one query
    codes = list({r.course_code for r in req_rows})
    credits_map: Dict[str, int] = {}
    titles_map: Dict[str, str] = {}
    if codes:
        course_rows = await db.execute(
            select(Course.code, Course.name, Course.credits).where(Course.code.in_(codes))
        )
        for code, name, credits in course_rows.all():
            credits_map[code] = int(credits or 0)
            titles_map[code] = name

    # Group by group_name
    grouped: Dict[str, List[RequirementGroupCourse]] = defaultdict(list)
    for rc in req_rows:
        grouped[rc.group_name or "Core"].append(rc)

    result = []
    for idx, (group_name, rcs) in enumerate(sorted(grouped.items())):
        courses_list = []
        units_required = 0.0
        units_completed = 0.0
        for rc in rcs:
            cr = credits_map.get(rc.course_code, 0)
            units_required += cr
            taken = passed.get(rc.course_code)
            if taken:
                units_completed += cr
            courses_list.append(
                {
                    "code": rc.course_code,
                    "title": titles_map.get(rc.course_code, rc.course_name or rc.course_code),
                    "units": cr,
                    "is_required": bool(rc.is_required),
                    "taken": bool(taken),
                    "grade": taken["grade_letter"] if taken else None,
                    "semester": taken["semester_code"] if taken else None,
                }
            )
        pct = round((units_completed / units_required) * 100, 1) if units_required else 0.0
        result.append(
            {
                "requirement_id": str(idx),
                "category": group_name,
                "total_units_required": units_required,
                "units_completed": units_completed,
                "units_in_progress": 0.0,
                "completion_percentage": pct,
                "satisfied": units_completed >= units_required and units_required > 0,
                "is_core": True,
                "courses": courses_list,
            }
        )
    return {
        "requirements": result,
        "program": {"code": program.code, "name": program.name} if program else None,
    }


@router.get("/me/requirements-tree")
async def get_requirements_tree(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Nested degree-audit hierarchy (Program -> semester blocks -> category
    sub-requirements -> courses), styled after the AIU portal. Satisfied/% roll
    up from the student's actual passed courses; anchored on the canonical plan."""
    if not student.program_id:
        return {"program": None, "overall": None, "semesters": []}

    program = await db.get(Program, student.program_id)
    major = await db.get(Major, student.major_id) if student.major_id else None
    passed = await _passed_map(student.student_id, db)

    # courses the student is currently sitting (enrolled, not yet passed)
    inprog_rows = await db.execute(
        select(Section.course_code)
        .join(Enrollment, Enrollment.section_id == Section.section_id)
        .where(Enrollment.student_id == student.student_id, Enrollment.status == "Enrolled")
    )
    in_progress = {code for (code,) in inprog_rows.all()} - set(passed.keys())

    codes = list(all_plan_codes())
    meta_rows = await db.execute(
        select(Course.code, Course.name, Course.credits, Course.description).where(Course.code.in_(codes))
    )
    course_meta = {
        code: {"title": name, "credits": int(cr or 0), "description": desc}
        for code, name, cr, desc in meta_rows.all()
    }

    total_credits = float(getattr(program, "total_credits", 0) or 133)
    # the portal's top node is the MAJOR ("Artificial Intelligence Science"),
    # not the parent program ("Computer Science")
    title = (major.name if major else None) or (program.name if program else "Program")
    return build_requirement_tree(
        title,
        program.code if program else None,
        total_credits,
        course_meta,
        passed,
        in_progress,
    )


@router.get("/me/study-plan")
async def get_study_plan(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Remaining courses to graduation, ordered by code."""
    if not student.program_id:
        return {"remaining": []}

    req_rows = await _requirement_rows(student.program_id, student.major_id, db)
    required_codes = {r.course_code for r in req_rows}
    passed = await _passed_map(student.student_id, db)
    remaining_codes = sorted(required_codes - set(passed.keys()))

    if not remaining_codes:
        return {"remaining": []}

    course_rows = await db.execute(
        select(Course).where(Course.code.in_(remaining_codes))
    )
    remaining = [
        {
            "course_id": c.course_id,
            "code": c.code,
            "title": c.name,
            "credits": c.credits,
        }
        for c in course_rows.scalars().all()
    ]
    remaining.sort(key=lambda x: x["code"])
    return {"remaining": remaining}


@router.get("/me/graduation-check")
async def graduation_check(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    reqs_data = await get_requirements(student, db)
    missing = [r for r in reqs_data["requirements"] if not r["satisfied"]]
    eligible = len(missing) == 0
    return {
        "eligible": eligible,
        "missing": [
            {
                "category": m["category"],
                "units_remaining": m["total_units_required"] - m["units_completed"],
            }
            for m in missing
        ],
        "blocking_reasons": [] if eligible else [f"Outstanding: {m['category']}" for m in missing],
    }


@router.get("/me/graduation-countdown")
async def graduation_countdown(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    # Use transcript-based completed credits for consistency with /me/gpa
    transcript = await _transcript_rows(student.student_id, db)
    completed = sum(
        r["credits"] for r in transcript
        if r["grade_letter"] and r["grade_letter"] not in ("F", "W", "WP", "WF", "I")
    )
    total_program = 144
    remaining_credits = max(0, total_program - completed)
    best = max(1, -(-remaining_credits // 18)) if remaining_credits else 0
    worst = max(1, -(-remaining_credits // 12)) if remaining_credits else 0
    return {
        "remaining_credits": remaining_credits,
        "completed_credits": completed,
        "total_credits": total_program,
        "semesters_remaining": best,
        "best_case": best,
        "worst_case": worst,
    }


@router.get("/me/recovery-plan")
async def recovery_plan(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    return await build_recovery_plan(student.student_id, db)


@router.get("/me/course-recommendations")
async def course_recommendations(
    semester: str = Query("Fall 2026"),
    top_n: int = Query(5, ge=1, le=20),
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    return await recommend_courses(student, semester, db, top_n=top_n)


@router.get("/me/academic-profile")
async def academic_profile(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Subject-area strengths/weaknesses derived live from the transcript."""
    from services.academic_profile import build_academic_profile

    return await build_academic_profile(student.student_id, db)


@router.get("/me/degree-plan")
async def degree_plan(
    mode: str = Query("both", pattern="^(normal|fastest|both)$"),
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Term-by-term roadmap to graduation. mode=fastest adds summers/overload."""
    from services.degree_planner import build_degree_plan, compare_degree_plans

    if mode == "both":
        return await compare_degree_plans(student, db)
    return await build_degree_plan(student, db, mode=mode)


async def _narrate_risk(name: str, r: Dict) -> Optional[str]:
    """Let the LLM narrate the model's output (model computes, LLM narrates).
    Graceful: returns None if Groq is unavailable."""
    from ai.groq_client import FAST_MODEL, complete

    factors = "; ".join(f"{f['label']} — {f['detail']}" for f in r["factors"]) or "no specific risk factors"
    protective = ", ".join(p["label"] for p in r["protective"]) or "none noted"
    actions = "; ".join(r["recommended_actions"]) or "maintain current study habits"
    system = (
        "You are a warm, supportive AIU academic advisor. In 2-3 short sentences, speak directly to the "
        "student ('you') about an early-warning model's reading of their first-year record. Never be alarmist. "
        "If risk is low, reassure and add one light tip. If moderate or high, be honest and give concrete, "
        "doable next steps. Use ONLY the facts provided — do not invent grades or numbers."
    )
    user = (
        f"Student: {name}\n"
        f"Predicted risk band: {r['risk_band']} (score {r['risk_score']:.0%}); this is a {r['horizon']}.\n"
        f"Risk factors: {factors}\n"
        f"Protective factors: {protective}\n"
        f"Suggested actions: {actions}"
    )
    msg = await complete(
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        model=FAST_MODEL, temperature=0.4, max_tokens=220,
    )
    return msg.strip() or None


@router.get("/me/risk")
async def academic_risk(
    narrate: bool = Query(True),
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """Academic early-warning forecast from the trained ML model, with the
    explainable factors behind the score and an LLM-narrated message."""
    from services.risk_model import predict_risk

    result = await predict_risk(student.student_id, db)
    if result is None:
        return {"available": False}
    result["available"] = True
    result["student_name"] = student.full_name
    if narrate:
        try:
            result["narrative"] = await _narrate_risk(student.full_name, result)
        except Exception:
            result["narrative"] = None
    return result
