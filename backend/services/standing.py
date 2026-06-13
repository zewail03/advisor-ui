"""Academic-standing state machine (Dr. Ashraf advising notes §1–§3).

The ladder, per MAIN semester completed:
  - Semesters 1–2: CGPA does not affect standing at all (§1.2).
  - End of semester 3: CGPA < 1.667  -> first warning (§1.3, §2.1).
  - Semester 4 onward: the bar becomes 2.0 (§1.4).
  - Consecutive warnings with CGPA in [1.0, 2.0): dismissed at the 4th (§2.2).
  - Consecutive semesters with CGPA < 1.0: dismissed at the 3rd (§2.3).
  - A semester at/above the bar resets the warning count (§2.4).
  - Summer terms never ADD a warning, but a summer that lifts CGPA to/above
    the bar clears the warning streak (§3).

`replay_student_standing` rebuilds the whole academic_standing history from
raw grades, so any grade edit keeps standing provably consistent with the
rules engine. All thresholds come from the policy service (admin-editable).
"""
from typing import Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.academic import AcademicStanding, Semester
from models.course import Course, Section
from models.enrollment import Enrollment, Grade
from models.student import Student
from services.policy import get_policy

GOOD = "Good Standing"
WARNING = "Probation"  # UI vocabulary; warning_count carries the 1..4 ladder
DISMISSED = "Dismissed"


async def evaluate_semester(
    *,
    cgpa: float,
    main_semester_index: int,
    is_summer: bool,
    prev_warning_count: int,
    prev_severe_count: int,
    prev_status: str,
    db: AsyncSession,
) -> Dict:
    """Apply one semester's result to the standing state machine.

    `main_semester_index` is the 1-based count of MAIN (non-summer) semesters
    completed so far, including the one being evaluated when it is a main one.
    """
    if prev_status == DISMISSED:
        return {
            "status": DISMISSED,
            "warning_count": prev_warning_count,
            "severe_count": prev_severe_count,
            "note": "Dismissed — standing frozen",
        }

    warning_start = int(await get_policy("standing.warning_start_semester", db))
    early_bar = float(await get_policy("standing.probation_cgpa_early", db))
    regular_bar = float(await get_policy("standing.probation_cgpa", db))
    severe_bar = float(await get_policy("standing.severe_cgpa", db))
    dismiss_at = int(await get_policy("standing.dismissal_warnings", db))
    dismiss_severe_at = int(await get_policy("standing.dismissal_warnings_severe", db))
    summer_recovery = bool(await get_policy("standing.summer_recovery", db))

    # Semesters 1–2: CGPA is not considered (§1.2)
    if main_semester_index < warning_start:
        return {"status": GOOD, "warning_count": 0, "severe_count": 0,
                "note": "CGPA not evaluated before semester "
                        f"{warning_start} (Dr. Ashraf §1.2)"}

    bar = early_bar if main_semester_index == warning_start else regular_bar

    if is_summer:
        # Summer can only clear a warning, never add one (§3)
        if summer_recovery and prev_warning_count > 0 and cgpa >= bar:
            return {"status": GOOD, "warning_count": 0, "severe_count": 0,
                    "note": f"Summer recovery — CGPA {cgpa:.2f} ≥ {bar} clears warnings (§3)"}
        return {"status": WARNING if prev_warning_count else GOOD,
                "warning_count": prev_warning_count,
                "severe_count": prev_severe_count,
                "note": "Summer term — standing unchanged"}

    if cgpa >= bar:
        return {"status": GOOD, "warning_count": 0, "severe_count": 0,
                "note": f"CGPA {cgpa:.2f} ≥ {bar} — good standing"}

    warning_count = prev_warning_count + 1
    severe_count = prev_severe_count + 1 if cgpa < severe_bar else 0

    if severe_count >= dismiss_severe_at:
        return {"status": DISMISSED, "warning_count": warning_count,
                "severe_count": severe_count,
                "note": f"Dismissed — CGPA < {severe_bar} for "
                        f"{dismiss_severe_at} consecutive semesters (§2.3)"}
    if warning_count >= dismiss_at:
        return {"status": DISMISSED, "warning_count": warning_count,
                "severe_count": severe_count,
                "note": f"Dismissed — {dismiss_at} consecutive warnings (§2.2)"}

    return {"status": WARNING, "warning_count": warning_count,
            "severe_count": severe_count,
            "note": f"Warning {warning_count} of {dismiss_at} — "
                    f"CGPA {cgpa:.2f} < {bar}"}


async def replay_student_standing(student_id: int, db: AsyncSession) -> Optional[Dict]:
    """Rebuild the student's entire academic_standing history from raw grades
    and persist it (rows replaced; student.cgpa/status updated). Does NOT
    commit. Returns the final state, or None if the student has no grades."""
    student = await db.get(Student, student_id)
    if not student:
        return None

    rows = (await db.execute(
        select(
            Semester.semester_id, Semester.code, Semester.type,
            Grade.grade_points, Grade.grade_letter, Grade.counts_in_gpa,
            Course.credits,
        )
        .select_from(Grade)
        .join(Enrollment, Enrollment.enrollment_id == Grade.enrollment_id)
        .join(Section, Section.section_id == Enrollment.section_id)
        .join(Semester, Semester.semester_id == Section.semester_id)
        .join(Course, Course.code == Section.course_code)
        .where(Enrollment.student_id == student_id)
        .order_by(Semester.semester_id)
    )).all()
    if not rows:
        return None

    # bucket grades per semester, in chronological order
    semesters: List[Dict] = []
    by_sem: Dict[int, Dict] = {}
    for sem_id, sem_code, sem_type, pts, letter, counts, credits in rows:
        b = by_sem.get(sem_id)
        if b is None:
            b = {"semester_id": sem_id, "code": sem_code,
                 "is_summer": (sem_type or "").lower() == "summer", "grades": []}
            by_sem[sem_id] = b
            semesters.append(b)
        b["grades"].append((pts, letter, counts, credits))

    await db.execute(
        delete(AcademicStanding).where(AcademicStanding.student_code == student.student_code)
    )

    cum_pts = 0.0
    cum_cr = 0
    main_index = 0
    state = {"status": GOOD, "warning_count": 0, "severe_count": 0, "note": ""}
    final_cgpa = 0.0

    for sem in semesters:
        sem_pts, sem_cr = 0.0, 0
        for pts, letter, counts, credits in sem["grades"]:
            if not counts or pts is None or letter in ("W", "I", "S", "U"):
                continue
            sem_pts += float(pts) * int(credits or 0)
            sem_cr += int(credits or 0)
            cum_pts += float(pts) * int(credits or 0)
            cum_cr += int(credits or 0)
        sem_gpa = round(sem_pts / sem_cr, 3) if sem_cr else None
        cgpa = round(cum_pts / cum_cr, 3) if cum_cr else 0.0
        final_cgpa = cgpa
        if not sem["is_summer"]:
            main_index += 1

        state = await evaluate_semester(
            cgpa=cgpa,
            main_semester_index=main_index,
            is_summer=sem["is_summer"],
            prev_warning_count=state["warning_count"],
            prev_severe_count=state["severe_count"],
            prev_status=state["status"],
            db=db,
        )
        db.add(AcademicStanding(
            semester_id=sem["semester_id"],
            student_code=student.student_code,
            semester_code=sem["code"],
            semester_gpa=sem_gpa,
            cgpa=cgpa,
            status=state["status"],
            warning_count=state["warning_count"],
            probation_semesters=state["severe_count"],
            notes=state["note"],
        ))

    student.cgpa = final_cgpa
    if state["status"] == DISMISSED:
        student.status = "Dismissed"
    elif student.status not in ("Graduated", "Suspended", "Frozen", "Withdrawn"):
        student.status = "Probation" if state["warning_count"] > 0 else "Active"

    return {"cgpa": final_cgpa, **state}
