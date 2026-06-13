"""Multi-semester degree planner — a roadmap to graduation, computed fresh
from the student's real record every time.

Two modes:
  normal   — main semesters only, plan pace, weak-area courses get light terms
  fastest  — adds summer terms (Dr. Ashraf §4) and overload when the CGPA
             allows, to beat the normal timeline ("racer")

Constraints honored each simulated term:
  * study-plan order (required_year/required_semester) — never ahead unless
    racing, never skipped; failed courses are retaken first
  * prerequisites (a course is schedulable only after its prereqs are planned
    or passed in an EARLIER term)
  * course offering patterns (a Fall-only course is never planned in Spring —
    patterns are learned from the live sections history)
  * the credit-limit ladder (Math 0 / 16 CH / 1.667 / 2.0 / overload >3.0)
  * weak-subject load shaping: at most one personally-hard course per term in
    normal mode (two when racing), with the term kept lighter
"""
from typing import Dict, List, Set, Tuple

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.academic import RequirementGroup, RequirementGroupCourse, Semester
from models.course import Course, Section
from models.enrollment import Enrollment, Grade
from models.student import Major, Student
from services.academic_profile import build_academic_profile, personal_difficulty
from services.policy import get_policy

MAX_TERMS = 16  # safety valve


def _future_terms(include_summers: bool, lead_with_summer_2026: bool = False) -> List[Tuple[str, str]]:
    """(term name, type) starting from Fall 2026 — optionally with the still-
    registrable Summer 2026 term in front (racing students can use it NOW)."""
    out: List[Tuple[str, str]] = []
    if lead_with_summer_2026:
        out.append(("Summer 2026", "Summer"))
    year = 2026
    while len(out) < MAX_TERMS:
        out.append((f"Fall {year}", "Fall"))
        out.append((f"Spring {year + 1}", "Spring"))
        if include_summers:
            out.append((f"Summer {year + 1}", "Summer"))
        year += 1
    return out[:MAX_TERMS]


async def _offering_patterns(db: AsyncSession) -> Dict[str, Set[str]]:
    rows = await db.execute(
        select(Section.course_code, Semester.type)
        .join(Semester, Semester.semester_id == Section.semester_id)
        .distinct()
    )
    out: Dict[str, Set[str]] = {}
    for code, sem_type in rows.all():
        if code and sem_type:
            out.setdefault(code, set()).add(sem_type)
    return out


async def _student_record(student_id: int, db: AsyncSession):
    rows = (await db.execute(
        select(Section.course_code, Grade.grade_points, Grade.grade_letter, Grade.counts_in_gpa)
        .select_from(Grade)
        .join(Enrollment, Enrollment.enrollment_id == Grade.enrollment_id)
        .join(Section, Section.section_id == Enrollment.section_id)
        .where(Enrollment.student_id == student_id)
    )).all()
    passed: Set[str] = set()
    failed_open: Set[str] = set()
    pts_sum, cr_sum = 0.0, 0
    for code, pts, letter, counts in rows:
        if pts is not None and pts >= 1.0:
            passed.add(code)
        if counts and pts is not None and letter not in ("W", "I", "S", "U"):
            pts_sum += float(pts) * 3
            cr_sum += 3
    for code, pts, letter, counts in rows:
        if letter in ("F", "FW") and code not in passed:
            failed_open.add(code)
    # also count in-progress (Enrolled, no grade) as "will be passed" —
    # the roadmap starts AFTER the current term
    in_prog = (await db.execute(
        select(Section.course_code)
        .select_from(Enrollment)
        .join(Section, Section.section_id == Enrollment.section_id)
        .where(Enrollment.student_id == student_id, Enrollment.status == "Enrolled")
    )).all()
    in_progress = {r[0] for r in in_prog}
    cgpa = round(pts_sum / cr_sum, 3) if cr_sum else 0.0
    mains_done = int((await db.execute(
        select(func.count(func.distinct(Semester.semester_id)))
        .select_from(Grade)
        .join(Enrollment, Enrollment.enrollment_id == Grade.enrollment_id)
        .join(Section, Section.section_id == Enrollment.section_id)
        .join(Semester, Semester.semester_id == Section.semester_id)
        .where(Enrollment.student_id == student_id, ~Semester.code.like("Summer%"))
    )).scalar() or 0)
    return passed, failed_open, in_progress, cgpa, mains_done


async def build_degree_plan(
    student: Student, db: AsyncSession, mode: str = "normal",
    term_caps: Dict[str, int] | None = None,
) -> Dict:
    """term_caps: optional per-term credit-hour caps requested by the student
    (e.g. {"Fall 2027": 12}). A requested cap can only LOWER a term below its
    legal limit, never raise it — displaced courses spill into later terms
    under the same prerequisite/offering/cap rules."""
    racing = mode == "fastest"
    term_caps = term_caps or {}

    # ---- inputs, all live ----
    profile = await build_academic_profile(student.student_id, db)
    passed, failed_open, in_progress, cgpa, mains_done = await _student_record(
        student.student_id, db
    )
    effective_done = passed | in_progress
    patterns = await _offering_patterns(db)
    overload_bar = float(await get_policy("enrollment.overload_min_cgpa", db))
    limit_high = int(await get_policy("enrollment.credit_limit_high", db))
    limit_std = int(await get_policy("enrollment.credit_limit_standard", db))
    limit_low = int(await get_policy("enrollment.credit_limit_low", db))
    limit_summer = int(await get_policy("enrollment.credit_limit_summer", db))
    limit_sem2 = int(await get_policy("enrollment.sem2_credits", db))
    regular_bar = float(await get_policy("standing.probation_cgpa", db))
    early_bar = float(await get_policy("standing.probation_cgpa_early", db))

    major = await db.get(Major, student.major_id) if student.major_id else None
    major_code = major.code if major else None

    plan_rows = (await db.execute(
        select(RequirementGroupCourse.course_code, RequirementGroupCourse.group_name,
               RequirementGroupCourse.required_year, RequirementGroupCourse.required_semester)
        .where(RequirementGroupCourse.major_code == major_code)
    )).all()
    groups = {
        g.name: g for g in (await db.execute(
            select(RequirementGroup).where(RequirementGroup.major_id == student.major_id)
        )).scalars().all()
    }
    courses = {
        c.code: c for c in (await db.execute(select(Course))).scalars().all()
    }
    prereqs: Dict[str, List[str]] = {}
    from models.course import Prerequisite
    for c, p in (await db.execute(
        select(Prerequisite.course_code, Prerequisite.prerequisite_course_code)
    )).all():
        prereqs.setdefault(c, []).append(p)

    # ---- remaining work ----
    # required courses still owed (plan order), incl. failed retakes first
    required = sorted(
        [(r[2] or 9, r[3] or 9, r[0]) for r in plan_rows
         if r[1].endswith("Required") and r[0] not in effective_done],
    )
    # elective baskets: how many picks still owed per basket
    basket_members: Dict[str, List[str]] = {}
    basket_slot: Dict[str, Tuple[int, int]] = {}
    for code, gname, ry, rs in plan_rows:
        if gname.endswith("Required"):
            continue
        basket_members.setdefault(gname, []).append(code)
        basket_slot[gname] = (ry or 9, rs or 9)
    baskets_owed: Dict[str, int] = {}
    for gname, members in basket_members.items():
        need = groups[gname].min_courses if gname in groups else 1
        done = len([m for m in members if m in effective_done])
        if need - done > 0:
            baskets_owed[gname] = need - done

    queue: List[Dict] = []
    for code in sorted(failed_open):
        queue.append({"kind": "retake", "code": code, "slot": (0, 0)})
    for ry, rs, code in required:
        queue.append({"kind": "required", "code": code, "slot": (ry, rs)})
    for gname, n in sorted(baskets_owed.items(), key=lambda kv: basket_slot[kv[0]]):
        for _ in range(n):
            queue.append({"kind": "elective", "basket": gname, "slot": basket_slot[gname]})

    # Within the same plan slot, chain-critical courses go first — a course
    # that transitively unlocks many owed courses must never be deferred.
    from services.prereq_graph import chain_unlock_counts
    owed_codes = {it["code"] for it in queue if "code" in it}
    chain = chain_unlock_counts(
        [(c, p) for c, ps in prereqs.items() for p in ps], restrict_to=owed_codes
    )
    queue.sort(key=lambda it: (it["slot"], -chain.get(it.get("code", ""), 0)))

    def _personal(code: str) -> Dict:
        c = courses.get(code)
        return personal_difficulty(profile, code, c.name if c else "", "Unknown")

    def _credits(code: str) -> int:
        c = courses.get(code)
        return c.credits if c else 3

    def _offered(code: str, term_type: str) -> bool:
        return term_type in patterns.get(code, {"Fall", "Spring"})

    # ---- feasibility bound (pure credit-cap arithmetic) ----
    # Sum of legal per-term caps from now: the first term where cumulative
    # capacity covers the remaining credits is the earliest graduation that is
    # even POSSIBLE — anything earlier violates the load rules outright.
    # Summer 2026 counts only if the student isn't already enrolled in it.
    summer26_available = racing and not in_progress
    remaining_credits = sum(
        _credits(it["code"]) if "code" in it else 3 for it in queue
    )

    def _cap_for(slot: int, term_type: str) -> int:
        if term_type == "Summer":
            return limit_summer
        if slot <= 2:
            return limit_sem2
        if slot == 3:
            return limit_std if cgpa >= early_bar else limit_low
        if cgpa > overload_bar:
            return limit_high
        if cgpa >= regular_bar:
            return limit_std
        return limit_low

    earliest_feasible = None
    cap_sum, walk_mains = 0, 0
    feasibility_seq = _future_terms(include_summers=True,
                                    lead_with_summer_2026=not in_progress)
    for tname, ttype in feasibility_seq:
        cap_sum += _cap_for(mains_done + walk_mains + 1, ttype)
        if ttype != "Summer":
            walk_mains += 1
        if cap_sum >= remaining_credits:
            earliest_feasible = tname
            break

    # ---- bottleneck: longest remaining prerequisite chain ----
    # Each link needs its own term (a prereq must be PASSED in an earlier
    # term), so a chain of N owed courses needs >= N terms regardless of
    # credit room. Whichever bound is later is the binding constraint.
    owed_required = {it["code"] for it in queue if "code" in it}
    _depth_memo: Dict[str, int] = {}
    _best_prev: Dict[str, str] = {}

    def _chain_depth(code: str) -> int:
        if code in _depth_memo:
            return _depth_memo[code]
        _depth_memo[code] = 1  # cycle guard
        best = 0
        for p in prereqs.get(code, ()):
            if p in owed_required:
                d = _chain_depth(p)
                if d > best:
                    best = d
                    _best_prev[code] = p
        _depth_memo[code] = best + 1
        return _depth_memo[code]

    chain_terms, chain_tail = 0, None
    for c in owed_required:
        d = _chain_depth(c)
        if d > chain_terms:
            chain_terms, chain_tail = d, c
    chain_path: List[str] = []
    cur = chain_tail
    while cur:
        chain_path.append(cur)
        cur = _best_prev.get(cur)
    chain_path.reverse()

    binding = "credit caps"
    if earliest_feasible and chain_terms:
        names = [n for n, _ in feasibility_seq]
        idx_credit = names.index(earliest_feasible) if earliest_feasible in names else 0
        if chain_terms - 1 > idx_credit:
            binding = "prerequisite chain"

    # ---- simulate term by term ----
    max_hard_per_term = 2 if racing else 1
    terms_out: List[Dict] = []
    planned_passed = set(effective_done)
    stalled = 0
    applied_caps: Dict[str, int] = {}

    mains_planned = 0
    for term_name, term_type in _future_terms(
        include_summers=racing, lead_with_summer_2026=summer26_available
    ):
        if not queue:
            break
        # semester-indexed load ladder (Dr. Ashraf §1.2–1.4): sem 2 fixed,
        # sem 3 uses the 1.667 bar, overload only from sem 4 with CGPA > 3.0
        slot = mains_done + mains_planned + 1
        if term_type == "Summer":
            limit = limit_summer
        elif slot <= 2:
            limit = limit_sem2
        elif slot == 3:
            limit = limit_std if cgpa >= early_bar else limit_low
        elif cgpa > overload_bar and racing:
            limit = limit_high
        elif cgpa >= regular_bar:
            limit = limit_std
        else:
            limit = limit_low
        requested_cap = term_caps.get(term_name)
        if requested_cap is not None:
            # student may lighten a term, never exceed its legal limit
            limit = min(limit, max(int(requested_cap), 3))
            applied_caps[term_name] = limit
        target = limit if racing else min(limit, 17)

        chosen: List[Dict] = []
        load = 0
        hard_count = 0
        for item in list(queue):
            if load >= target:
                break
            if item["kind"] == "elective":
                opts = [m for m in basket_members[item["basket"]]
                        if m not in planned_passed and _offered(m, term_type)
                        and all(p in planned_passed for p in prereqs.get(m, ()))]
                if not opts:
                    continue
                opts.sort(key=lambda m: 0 if _personal(m)["personal"] == "Easier for you" else 1)
                code = opts[0]
            else:
                code = item["code"]
                if not _offered(code, term_type):
                    continue
                if not all(p in planned_passed for p in prereqs.get(code, ())):
                    continue
            cr = _credits(code)
            if load + cr > limit:
                continue
            pers = _personal(code)
            is_hard = pers["personal"] == "Hard for you"
            if is_hard and hard_count >= max_hard_per_term:
                continue
            chosen.append({
                "course_code": code,
                "course_title": courses[code].name if code in courses else "",
                "credits": cr,
                "kind": item["kind"],
                "subject_area": pers["area"],
                "personal_difficulty": pers["personal"],
                "personal_reason": pers["reason"],
            })
            load += cr
            hard_count += 1 if is_hard else 0
            planned_passed.add(code)
            queue.remove(item)
            # a hard course keeps its term light so the student can focus
            if is_hard and not racing:
                target = min(target, load + 6)

        if not chosen:
            stalled += 1
            if stalled >= 3:
                break
            continue
        stalled = 0
        note = ""
        hard_in = [c for c in chosen if c["personal_difficulty"] == "Hard for you"]
        if term_name in applied_caps:
            note = f"capped at {applied_caps[term_name]} CH at your request"
        elif hard_in and not racing:
            note = (f"kept light ({load} CH) to focus on {hard_in[0]['course_code']} "
                    f"({hard_in[0]['subject_area']} — your weaker area)")
        terms_out.append({
            "term": term_name,
            "type": term_type,
            "credits": load,
            "courses": chosen,
            "note": note,
        })
        if term_type != "Summer":
            mains_planned += 1

    # ---- conflict-aware first term: assign REAL sections (Fall 2026 exists
    # in the catalog) and flag any course whose only sections clash ----
    if terms_out and terms_out[0]["term"] == "Fall 2026":
        from sqlalchemy.orm import selectinload
        from services.validation import sections_conflict

        first = terms_out[0]
        codes_first = [c["course_code"] for c in first["courses"]]
        sec_rows = (await db.execute(
            select(Section)
            .options(selectinload(Section.meetings))
            .where(Section.course_code.in_(codes_first), Section.semester_id == 19,
                   Section.status == "Open")
        )).scalars().unique().all()
        by_course: Dict[str, List[Section]] = {}
        for s in sec_rows:
            by_course.setdefault(s.course_code, []).append(s)
        placed: List[Section] = []
        for c in first["courses"]:
            options = by_course.get(c["course_code"], [])
            pick = next(
                (s for s in options if not any(sections_conflict(s, p) for p in placed)),
                None,
            )
            if pick is not None:
                placed.append(pick)
                c["section_number"] = pick.section_number
                c["instructor"] = pick.instructor_name
                c["meetings"] = [
                    {"day": m.day_of_week, "start": m.start_time, "end": m.end_time,
                     "location": m.location}
                    for m in (pick.meetings or [])
                ]
                c["schedule_conflict"] = False
            else:
                c["schedule_conflict"] = bool(options)  # offered but clashes

    # ---- risk-aware projection: optimistic assumes every pass; realistic
    # uses the student's own per-area pass rate blended with each course's
    # cohort pass rate ----
    import math

    planned = [c for t in terms_out for c in t["courses"]]
    planned_codes = [c["course_code"] for c in planned]
    cohort_pass: Dict[str, float] = {}
    if planned_codes:
        rows = (await db.execute(
            select(
                Section.course_code,
                func.avg(case((Grade.grade_points >= 1.0, 1.0), else_=0.0)),
            )
            .select_from(Grade)
            .join(Enrollment, Enrollment.enrollment_id == Grade.enrollment_id)
            .join(Section, Section.section_id == Enrollment.section_id)
            .where(Section.course_code.in_(planned_codes),
                   Grade.counts_in_gpa == True,  # noqa: E712
                   Grade.grade_points.is_not(None))
            .group_by(Section.course_code)
        )).all()
        cohort_pass = {code: float(r) for code, r in rows if r is not None}

    area_rates = {a: v.get("pass_rate") for a, v in (profile.get("areas") or {}).items()}
    overall_rate = (
        sum(r for r in area_rates.values() if r is not None) / max(
            len([r for r in area_rates.values() if r is not None]), 1)
        if any(r is not None for r in area_rates.values()) else 0.9
    )

    expected_failures = 0.0
    expected_failed_credits = 0.0
    at_risk: List[Dict] = []
    for c in planned:
        student_rate = area_rates.get(c["subject_area"]) or overall_rate
        p = 0.35 * student_rate + 0.65 * cohort_pass.get(c["course_code"], 0.9)
        p = min(max(p, 0.05), 0.99)
        c["pass_probability"] = round(p, 2)
        expected_failures += 1 - p
        expected_failed_credits += (1 - p) * c["credits"]
        if p < 0.6:
            at_risk.append({"course_code": c["course_code"], "pass_probability": round(p, 2)})

    avg_term_load = (
        sum(t["credits"] for t in terms_out) / len(terms_out) if terms_out else 15
    )
    extra_terms = math.ceil(expected_failed_credits / max(avg_term_load, 1)) if planned else 0

    grad_term = terms_out[-1]["term"] if terms_out and not queue else None
    realistic_term = grad_term
    if grad_term and extra_terms:
        seq = [name for name, _ in _future_terms(include_summers=racing)]
        try:
            idx = seq.index(grad_term) + extra_terms
            realistic_term = seq[idx] if idx < len(seq) else "beyond horizon"
        except ValueError:
            pass

    return {
        "mode": mode,
        "cgpa": cgpa,
        "weak_areas": profile.get("weak_areas", []),
        "strong_areas": profile.get("strong_areas", []),
        "remaining_courses": len(queue) + sum(len(t["courses"]) for t in terms_out),
        "unplannable": [
            (it.get("code") or f"elective ({it['basket']})") for it in queue
        ],
        "terms": terms_out,
        "graduation_term": grad_term,
        "terms_to_graduation": len(terms_out),
        "remaining_credits": remaining_credits,
        "earliest_feasible_term": earliest_feasible,
        "applied_term_caps": applied_caps,
        "load_rules": {
            "summer_max": limit_summer,
            "standard_max": limit_std,
            "overload_max": limit_high,
            "overload_bar": overload_bar,
        },
        "bottleneck": {
            "binding_constraint": binding,
            "longest_prereq_chain": chain_path,
            "chain_terms_needed": chain_terms,
        },
        "risk": {
            "expected_course_failures": round(expected_failures, 1),
            "courses_at_risk": at_risk,
            "extra_terms_expected": extra_terms,
            "realistic_graduation_term": realistic_term,
        },
    }


async def compare_degree_plans(
    student: Student, db: AsyncSession, term_caps: Dict[str, int] | None = None
) -> Dict:
    """Normal vs fastest, with the savings spelled out."""
    normal = await build_degree_plan(student, db, mode="normal", term_caps=term_caps)
    fastest = await build_degree_plan(student, db, mode="fastest", term_caps=term_caps)
    saved = None
    if normal["graduation_term"] and fastest["graduation_term"]:
        mains_normal = len([t for t in normal["terms"] if t["type"] != "Summer"])
        mains_fast = len([t for t in fastest["terms"] if t["type"] != "Summer"])
        saved = mains_normal - mains_fast
    return {
        "normal": normal,
        "fastest": fastest,
        "main_semesters_saved": saved,
        "summers_used": len([t for t in fastest["terms"] if t["type"] == "Summer"]),
        "remaining_credits": fastest.get("remaining_credits"),
        "earliest_feasible_term": fastest.get("earliest_feasible_term"),
        "bottleneck": fastest.get("bottleneck"),
        "applied_term_caps": fastest.get("applied_term_caps") or normal.get("applied_term_caps") or {},
        "load_rules": fastest.get("load_rules"),
    }


def render_degree_plan_summary(payload: Dict) -> str:
    """Compact text for the chat LLM."""
    lines: List[str] = []
    caps = payload.get("applied_term_caps") or {}
    if caps:
        caps_str = "; ".join(f"{t} capped at {c} CH" for t, c in caps.items())
        lines.append(
            f"REVISION APPLIED by the planning engine at the student's request: "
            f"{caps_str}. Displaced courses were re-planned into later terms with "
            f"all rules re-checked (prerequisites, offering patterns, load caps). "
            f"Present THESE plans — they already include the change."
        )
    for mode in ("normal", "fastest"):
        plan = payload.get(mode)
        if not plan:
            continue
        head = (f"{mode.upper()} plan: graduates {plan['graduation_term'] or 'beyond horizon'}"
                f" in {plan['terms_to_graduation']} terms")
        if plan.get("weak_areas"):
            head += f" | weak areas: {', '.join(plan['weak_areas'])}"
        lines.append(head)
        risk = plan.get("risk") or {}
        if risk.get("extra_terms_expected"):
            at_risk = ", ".join(c["course_code"] for c in risk.get("courses_at_risk", [])) or "none specific"
            lines.append(
                f"  risk: ~{risk['expected_course_failures']} expected course failure(s) "
                f"(at risk: {at_risk}) -> realistic graduation {risk['realistic_graduation_term']} "
                f"(optimistic {plan['graduation_term']})"
            )
        for t in plan["terms"]:
            cs = ", ".join(
                c["course_code"] + ("(retake)" if c["kind"] == "retake" else "")
                for c in t["courses"]
            )
            line = f"  {t['term']}: {cs} = {t['credits']} CH"
            if t.get("note"):
                line += f" [{t['note']}]"
            lines.append(line)
    if payload.get("main_semesters_saved") is not None:
        lines.append(
            f"Fast-track saves {payload['main_semesters_saved']} main semester(s) "
            f"using {payload.get('summers_used', 0)} summer term(s)."
        )
    if payload.get("earliest_feasible_term"):
        lines.append(
            f"FEASIBILITY BOUND (use this to answer 'can I graduate by X?'): "
            f"{payload['remaining_credits']} credit hours remain. Adding up the MAXIMUM "
            f"legal load of every future term (semester-indexed credit caps, overload "
            f"and summers included), the earliest mathematically possible graduation "
            f"is {payload['earliest_feasible_term']}. Any earlier target is impossible "
            f"under the university's credit-limit rules — show the student this "
            f"arithmetic when they ask."
        )
    bn = payload.get("bottleneck") or {}
    if bn.get("longest_prereq_chain"):
        lines.append(
            f"BOTTLENECK: binding constraint is {bn['binding_constraint']}. Longest "
            f"remaining prerequisite chain: {' -> '.join(bn['longest_prereq_chain'])} "
            f"({bn['chain_terms_needed']} sequential terms minimum — each link must be "
            f"passed in an earlier term than the next). Use this to explain WHY the "
            f"timeline can't compress further."
        )
    rules = payload.get("load_rules") or {}
    if rules:
        lines.append(
            f"HARD LOAD LIMITS (university policy — NEVER violate, NEVER move courses "
            f"between terms yourself): Summer terms max {rules['summer_max']} CH; regular "
            f"semesters max {rules['standard_max']} CH (overload to {rules['overload_max']} CH "
            f"only with CGPA > {rules['overload_bar']} from semester 4). If the student asks "
            f"to modify a plan, do NOT rearrange the tables freehand — the planning engine "
            f"must recompute. Ask them to name the term and the load they want."
        )
    lines.append(
        "Guidance for the answer: render each plan as a markdown table "
        "(| Term | Courses | CH | Note |), one row per term — courses comma-separated "
        "in one cell. After the tables, one short paragraph comparing the plans "
        "(semesters saved, summer terms, risk)."
    )
    return "\n".join(lines)
