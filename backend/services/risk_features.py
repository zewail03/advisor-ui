"""First-year leading indicators for the academic early-warning model.

Everything the model sees is derived LIVE from raw grades — nothing is
hand-labelled or remembered. The feature window is intentionally limited to a
student's **first two main (non-summer) semesters** so the model only ever
looks at what is knowable early, then predicts a *later* outcome (a warning /
probation / dismissal, which can only occur from the 3rd main semester on).
Features and the label therefore never overlap in time — the model is genuinely
predictive, not a restatement of the current CGPA.

The same extractor runs at training time (over senior cohorts whose outcome is
already known) and at inference time (over current students), which guarantees
the feature vector is computed identically in both places.
"""
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.course import Course, Section
from models.enrollment import Enrollment, Grade
from models.academic import Semester

# Stable feature order — the training script and the saved model rely on it.
# The set is deliberately curated to leading indicators with stable, sensible
# signs (a weaker first year always raises predicted risk). Candidate features
# that the data made unreliable were dropped on purpose: course withdrawals
# (none occur in the first year), the Math-0 flag (near-constant here), raw
# first-year credit load (the registration cap makes a light load a *proxy* for
# an already-low CGPA, not an independent early signal) and a math-deficit term
# (too collinear with overall performance to carry an independent, stable sign).
FEATURE_NAMES: List[str] = [
    "first_year_gpa",
    "gpa_trend",
    "failed_courses",
    "low_grade_rate",
]

# Human-readable copy for each feature. `label`/`detail` describe the feature
# when it is *raising* predicted risk; `protective` is the label to show when
# the same feature is instead *lowering* risk.
FEATURE_COPY: Dict[str, Dict[str, str]] = {
    "first_year_gpa": {
        "label": "Low first-year GPA",
        "detail": "A first-year GPA of {value:.2f} sits below where peers who stayed in good standing landed.",
        "protective": "Strong first-year GPA",
    },
    "gpa_trend": {
        "label": "Declining GPA",
        "detail": "GPA fell by {magnitude:.2f} between the first two semesters — a downward trend.",
        "protective": "Improving GPA trend",
    },
    "failed_courses": {
        "label": "Failed courses early",
        "detail": "{value:.0f} failed course(s) in the first year add retake load and drag the CGPA down.",
        "protective": "No early course failures",
    },
    "low_grade_rate": {
        "label": "High share of low grades",
        "detail": "{pct:.0f}% of first-year grades fell in the D/F range.",
        "protective": "Few low grades",
    },
}

# letters that carry no grade points
_NON_GRADED = {"W", "I", "S", "U", "P"}
_FAIL = {"F", "FW"}


async def _student_window_rows(student_id: int, db: AsyncSession) -> List[Dict]:
    """All graded/attempted enrollments for the student, chronological, with the
    semester type and course credits attached."""
    rows = (await db.execute(
        select(
            Section.semester_id,
            Semester.type,
            Section.course_code,
            Course.credits,
            Grade.grade_letter,
            Grade.grade_points,
            Grade.counts_in_gpa,
        )
        .select_from(Enrollment)
        .join(Section, Section.section_id == Enrollment.section_id)
        .join(Semester, Semester.semester_id == Section.semester_id)
        .join(Course, Course.code == Section.course_code)
        .join(Grade, Grade.enrollment_id == Enrollment.enrollment_id, isouter=True)
        .where(Enrollment.student_id == student_id)
        .order_by(Section.semester_id)
    )).all()
    return [
        {
            "semester_id": sid,
            "is_summer": (stype or "").lower() == "summer",
            "code": code,
            "credits": int(cr or 0),
            "letter": (letter or "").upper() if letter else None,
            "points": float(pts) if pts is not None else None,
            "counts": bool(counts),
        }
        for sid, stype, code, cr, letter, pts, counts in rows
    ]


def main_semesters_completed(rows: List[Dict]) -> int:
    """Number of distinct GRADED main (non-summer) semesters — the student's
    'maturity'. Used to decide who is a training example vs a prediction target."""
    mains = set()
    for r in rows:
        if r["is_summer"]:
            continue
        if r["letter"] is not None:  # the semester has posted grades
            mains.add(r["semester_id"])
    return len(mains)


def _gpa(grades: List[Dict]) -> Optional[float]:
    """GPA over a set of grade rows, POINT-IN-TIME: a course counts by its actual
    letter grade (F counts as 0), independent of `counts_in_gpa`. We must NOT use
    `counts_in_gpa` here — a later retake flips it to False, which would leak that
    future recovery back into a first-year feature."""
    pts, cr = 0.0, 0
    for g in grades:
        if g["points"] is None or g["letter"] in _NON_GRADED:
            continue
        pts += g["points"] * g["credits"]
        cr += g["credits"]
    return round(pts / cr, 3) if cr else None


def features_from_rows(rows: List[Dict]) -> Optional[Dict[str, float]]:
    """Compute the first-year feature vector from pre-fetched rows. Returns None
    if the student has no graded main-semester record yet.

    All features are computed as the first-year record *stood at first-year end*
    — never using the current `counts_in_gpa` flag, which a year-2+ retake would
    flip and so leak the future into the model (verified: this would inflate
    first-year GPA for ~18 senior students by up to 1.26 points)."""
    # the first two MAIN semesters define the window; pull summers that fall
    # within (before the 2nd main completes) along for the ride.
    main_ids: List[int] = []
    for r in rows:
        if not r["is_summer"] and r["letter"] is not None and r["semester_id"] not in main_ids:
            main_ids.append(r["semester_id"])
    if not main_ids:
        return None
    window_mains = main_ids[:2]
    cutoff = window_mains[-1]
    window = [r for r in rows if r["semester_id"] <= cutoff and r["letter"] is not None]
    if not window:
        return None

    # keep only the latest attempt WITHIN the window per course, so a same-window
    # retake isn't double-counted; everything is then judged by its letter grade.
    latest: Dict[str, Dict] = {}
    for g in sorted(window, key=lambda g: g["semester_id"]):
        latest[g["code"]] = g
    deduped = list(latest.values())
    graded = [g for g in deduped if g["points"] is not None and g["letter"] not in _NON_GRADED]

    first_year_gpa = _gpa(deduped) or 0.0

    sem1_gpa = _gpa([g for g in deduped if g["semester_id"] == window_mains[0]])
    sem2_gpa = _gpa([g for g in deduped if g["semester_id"] == window_mains[1]]) if len(window_mains) > 1 else None
    gpa_trend = round((sem2_gpa - sem1_gpa), 3) if (sem1_gpa is not None and sem2_gpa is not None) else 0.0

    # any course FAILED during the first year (by letter), whether or not it was
    # later retaken — a year-1 failure is a real early-warning signal.
    failed = sum(1 for g in window if g["letter"] in _FAIL)

    low = sum(1 for g in graded if g["points"] < 2.0)
    low_grade_rate = round(low / len(graded), 3) if graded else 0.0

    return {
        "first_year_gpa": first_year_gpa,
        "gpa_trend": gpa_trend,
        "failed_courses": float(failed),
        "low_grade_rate": low_grade_rate,
    }


async def extract_features(
    student_id: int, db: AsyncSession, math0_passed: Optional[bool] = None
) -> Optional[Dict]:
    """Live feature vector for one student. Returns a dict with `features`
    (name->value), `maturity` (main semesters completed) and `vector`
    (values in FEATURE_NAMES order), or None if there is no graded record.

    `math0_passed` is accepted for call-site compatibility but the current
    feature set does not use it (see FEATURE_NAMES)."""
    rows = await _student_window_rows(student_id, db)
    feats = features_from_rows(rows)
    if feats is None:
        return None
    return {
        "features": feats,
        "vector": [feats[name] for name in FEATURE_NAMES],
        "maturity": main_semesters_completed(rows),
    }
