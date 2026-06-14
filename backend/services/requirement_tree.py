"""Nested degree-audit hierarchy, styled after the AIU PeopleSoft "Enroll by My
Requirements" view.

The structure is anchored on the SAME canonical 8-semester AIS study plan that
drives every student's transcript (scripts/regenerate_ais_plan.py), so the audit
is always internally consistent with the data. Shape:

    Program (Artificial Intelligence Science, 133 cr)
      └ UAIS- 1st .. 8th SEM           (semester blocks)
          └ category sub-requirements  (Math & Basic Sciences, Basic Computing,
            UAIS Specialization, Training, Projects, Electives, University …)
              └ courses                (taken / in-progress / not-started)

Satisfied + "% completed" roll up bottom-up from the student's ACTUAL passed
courses. Only catalog courses are referenced (no invented data).
"""
from typing import Dict, List, Optional, Set

# ---- canonical AIS plan, by slot (1..8): "C"=fixed course, "E"=elective basket
# (kept in lock-step with scripts/regenerate_ais_plan.py) ----
PLAN: Dict[int, list] = {
    1: [("C", "MAT111"), ("C", "PHY211"), ("C", "CSE014"), ("C", "LAN022"), ("C", "PSC101"), ("C", "CSE013")],
    2: [("C", "MAT112"), ("C", "MAT131"), ("C", "CSE015"), ("C", "CSE315"), ("C", "LAN111"), ("C", "LAN112")],
    3: [("C", "MAT212"), ("C", "MAT231"), ("C", "CSE111"), ("C", "CSE131"), ("C", "AIE111"), ("C", "LAN114")],
    4: [("C", "MAT312"), ("C", "CSE132"), ("C", "CSE221"), ("C", "CSE281"), ("C", "AIE121"), ("C", "AIE191"), ("C", "LIB116")],
    5: [("C", "CSE233"), ("C", "CSE251"), ("C", "CSE261"), ("C", "AIE231"), ("C", "AIE323"), ("C", "GEO217")],
    6: [("C", "CSE112"), ("C", "AIE212"), ("C", "AIE213"), ("C", "AIE241"), ("C", "AIE292"), ("E", "AIS E1"), ("C", "LAN130")],
    7: [("C", "CSE363"), ("C", "AIE322"), ("C", "AIE332"), ("C", "AIE493"), ("E", "AIS E2"), ("C", "MGT222"), ("E", "University Elective")],
    8: [("C", "AIE425"), ("C", "AIE314"), ("C", "AIE494"), ("E", "AIS E3"), ("E", "University Elective")],
}

BASKETS: Dict[str, List[str]] = {
    "AIS E1": ["CSE211", "CSE234", "CSE344", "CSE382", "CSE383"],
    "AIS E2": ["AIE351", "AIE417", "CSE464"],
    "AIS E3": ["AIE418"],
    "University Elective": ["PHS071", "PSC207", "MGT201", "MGT102", "ADL123", "MGT121", "LAN211"],
}

# elective baskets: display category + how many credits the basket requires
BASKET_CATEGORY = {
    "AIS E1": "UAIS - Electives - E1",
    "AIS E2": "UAIS - Electives - E2",
    "AIS E3": "UAIS - Electives - E3",
    "University Elective": "Elective University",
}
BASKET_MIN_CREDITS = {"AIS E1": 3, "AIS E2": 3, "AIS E3": 3, "University Elective": 2}

# fixed course -> sub-requirement category (matches the portal's category names)
CATEGORY_OF: Dict[str, str] = {
    # Mathematics and Basic Sciences
    "MAT111": "Mathematics and Basic Sciences", "MAT112": "Mathematics and Basic Sciences",
    "MAT131": "Mathematics and Basic Sciences", "MAT212": "Mathematics and Basic Sciences",
    "MAT231": "Mathematics and Basic Sciences", "MAT312": "Mathematics and Basic Sciences",
    "PHY211": "Mathematics and Basic Sciences", "CSE315": "Mathematics and Basic Sciences",
    # Basic Computing Sciences
    "CSE014": "Basic Computing Sciences", "CSE015": "Basic Computing Sciences",
    "CSE111": "Basic Computing Sciences", "CSE131": "Basic Computing Sciences",
    "CSE132": "Basic Computing Sciences", "CSE221": "Basic Computing Sciences",
    "CSE233": "Basic Computing Sciences", "CSE251": "Basic Computing Sciences",
    "CSE261": "Basic Computing Sciences", "AIE111": "Basic Computing Sciences",
    "AIE121": "Basic Computing Sciences",
    # UAIS Specialization
    "CSE281": "UAIS Specialization", "CSE112": "UAIS Specialization", "CSE363": "UAIS Specialization",
    "AIE231": "UAIS Specialization", "AIE323": "UAIS Specialization", "AIE212": "UAIS Specialization",
    "AIE213": "UAIS Specialization", "AIE241": "UAIS Specialization", "AIE322": "UAIS Specialization",
    "AIE332": "UAIS Specialization", "AIE425": "UAIS Specialization", "AIE314": "UAIS Specialization",
    # UAIS - Training
    "AIE191": "UAIS - Training", "AIE292": "UAIS - Training",
    # UAIS - Projects
    "AIE493": "UAIS - Projects", "AIE494": "UAIS - Projects",
    # University Requirement (1)
    "CSE013": "University Requirement (1)", "LAN112": "University Requirement (1)",
    "LAN114": "University Requirement (1)", "LIB116": "University Requirement (1)",
    "GEO217": "University Requirement (1)", "MGT222": "University Requirement (1)",
    # UC2 - Languages
    "LAN111": "UC2 - Languages", "LAN130": "UC2 - Languages",
    # zero-credit
    "PSC101": "UC - PSC - 0 Credits", "LAN022": "UC - LAN - 0 Credits",
}

# order sub-requirements are displayed within a semester block
CATEGORY_ORDER = [
    "Mathematics and Basic Sciences",
    "Basic Computing Sciences",
    "UAIS Specialization",
    "UAIS - Training",
    "UAIS - Projects",
    "UAIS - Electives - E1",
    "UAIS - Electives - E2",
    "UAIS - Electives - E3",
    "Elective University",
    "University Requirement (1)",
    "UC2 - Languages",
    "UC - PSC - 0 Credits",
    "UC - LAN - 0 Credits",
]

_ORDINAL = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th", 6: "6th", 7: "7th", 8: "8th"}
SEMESTER_LABEL = {n: f"UAIS- {_ORDINAL[n]} SEM" for n in range(1, 9)}


def all_plan_codes() -> Set[str]:
    """Every course code referenced by the plan (fixed + every basket pool)."""
    codes: Set[str] = set()
    for items in PLAN.values():
        for kind, val in items:
            if kind == "C":
                codes.add(val)
    for pool in BASKETS.values():
        codes.update(pool)
    return codes


def _course_obj(code: str, course_meta: Dict[str, dict], passed: Dict[str, dict], in_progress: Set[str]) -> dict:
    meta = course_meta.get(code, {})
    p = passed.get(code)
    taken = p is not None
    inprog = (not taken) and (code in in_progress)
    return {
        "code": code,
        "title": meta.get("title", code),
        "description": meta.get("description"),
        "units": float(meta.get("credits", 0)),
        "taken": taken,
        "in_progress": inprog,
        "grade": p["grade_letter"] if p else None,
        "term": p["semester_code"] if p else None,
        "status": "Taken" if taken else ("In Progress" if inprog else "Not Started"),
    }


def _finalize_subreq(cat: dict) -> dict:
    """Compute satisfied/% — by credit units, or by course count for 0-credit blocks."""
    courses = cat["courses"]
    req_units = cat["required_units"]
    if req_units > 0:
        completed = min(cat["completed_units"], req_units)
        pct = round(completed / req_units * 100, 1)
        satisfied = completed >= req_units
        basis = "units"
        req_display, done_display = req_units, completed
    else:
        total_c = len(courses)
        done_c = sum(1 for c in courses if c["taken"])
        pct = round(done_c / total_c * 100, 1) if total_c else 100.0
        satisfied = total_c > 0 and done_c >= total_c
        basis = "courses"
        req_display, done_display = float(total_c), float(done_c)
    return {
        "category": cat["category"],
        "is_basket": cat["is_basket"],
        "basis": basis,
        "required": req_display,
        "completed": done_display,
        "in_progress": cat["in_progress_units"],
        "completion_percentage": pct,
        "satisfied": satisfied,
        "courses": courses,
    }


def build_requirement_tree(
    program_name: str,
    program_code: Optional[str],
    total_credits: float,
    course_meta: Dict[str, dict],
    passed: Dict[str, dict],
    in_progress: Set[str],
) -> dict:
    semesters = []
    prog_completed = 0.0
    prog_inprog = 0.0

    for slot in range(1, 9):
        cats: Dict[str, dict] = {}

        def _cat(name: str, is_basket: bool) -> dict:
            return cats.setdefault(name, {
                "category": name, "is_basket": is_basket, "courses": [],
                "required_units": 0.0, "completed_units": 0.0, "in_progress_units": 0.0,
            })

        for kind, val in PLAN[slot]:
            if kind == "C":
                code = val
                cat = _cat(CATEGORY_OF.get(code, "Other"), False)
                obj = _course_obj(code, course_meta, passed, in_progress)
                cat["courses"].append(obj)
                cat["required_units"] += obj["units"]
                if obj["taken"]:
                    cat["completed_units"] += obj["units"]
                elif obj["in_progress"]:
                    cat["in_progress_units"] += obj["units"]
            else:
                bname = val
                cat = _cat(BASKET_CATEGORY[bname], True)
                req = BASKET_MIN_CREDITS[bname]
                cat["required_units"] += req
                got = 0.0
                inprog_cr = 0.0
                for code in BASKETS[bname]:
                    obj = _course_obj(code, course_meta, passed, in_progress)
                    cat["courses"].append(obj)
                    if obj["taken"]:
                        got += obj["units"]
                    elif obj["in_progress"]:
                        inprog_cr += obj["units"]
                cat["completed_units"] += min(got, req)
                cat["in_progress_units"] += min(inprog_cr, max(0.0, req - got))

        subreqs = []
        sem_req = sem_done = sem_inp = 0.0
        for name in CATEGORY_ORDER:
            if name not in cats:
                continue
            sr = _finalize_subreq(cats[name])
            subreqs.append(sr)
            if sr["basis"] == "units":
                sem_req += sr["required"]
                sem_done += sr["completed"]
            sem_inp += sr["in_progress"]

        sem_pct = round(sem_done / sem_req * 100, 1) if sem_req else 0.0
        semesters.append({
            "name": SEMESTER_LABEL[slot], "slot": slot,
            "required": sem_req, "completed": sem_done, "in_progress": sem_inp,
            "completion_percentage": sem_pct,
            "satisfied": bool(subreqs) and all(s["satisfied"] for s in subreqs),
            "subrequirements": subreqs,
        })
        prog_completed += sem_done
        prog_inprog += sem_inp

    total_required = float(total_credits) if total_credits else sum(s["required"] for s in semesters)
    prog_completed = min(prog_completed, total_required)
    prog_pct = round(prog_completed / total_required * 100, 1) if total_required else 0.0

    return {
        "program": {"name": program_name, "code": program_code, "total_credits": total_required},
        "overall": {
            "required": total_required,
            "completed": prog_completed,
            "in_progress": prog_inprog,
            "completion_percentage": prog_pct,
            "satisfied": all(s["satisfied"] for s in semesters),
        },
        "semesters": semesters,
    }
