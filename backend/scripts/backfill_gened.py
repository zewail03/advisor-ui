"""Backfill 20 CH of University Requirements (gen-ed) into existing AIS transcripts,
proportional to each student's progress, and create Fall 2026 offerings so the
planner can schedule the remaining ones. 2026-06-13. Backup: aiu_pre_gened.dump.

Rules:
- Gen-ed is laid down over the first ~6 MAIN semesters a student has completed.
- A student who finished K main semesters has done the gen-ed for index 1..min(K,6).
- Two 0-credit pass/fail courses (LAN022, PSC101): grade 'P', points 4.0, counts_in_gpa=False
  (counts as PASSED via grade_points>=1.0, but excluded from CGPA).
- 2-CH gen-ed grades are centered near the student's own CGPA (gen-ed slightly easier),
  so adding them keeps CGPA stable and realistic.
- Each (course, semester) shares one section; students enroll into it (status 'Satisfied').
Run from backend/:  .\\venv\\Scripts\\python.exe -m scripts.backfill_gened
"""
import asyncio
import random
from collections import defaultdict

from sqlalchemy import text

from core.database import AsyncSessionLocal

ZERO_CH = {"LAN022", "PSC101"}
ELECTIVES = ["PHS071", "PSC207", "MGT201", "MGT102", "ADL123", "MGT121", "LAN211"]
GENED_ALL = [
    "PSC101", "LAN022", "GEO217", "LAN111", "LAN130", "CSE013", "MGT222", "LAN114",
    "LIB116", "LAN112", "PHS071", "PSC207", "MGT201", "MGT102", "ADL123", "MGT121", "LAN211",
]
# letter -> (points, percentage), ordered by points desc
SCALE = [
    ("A", 4.0, 92), ("A-", 3.7, 89), ("B+", 3.3, 86), ("B", 3.0, 82), ("B-", 2.7, 79),
    ("C+", 2.3, 76), ("C", 2.0, 72), ("C-", 1.7, 68), ("D+", 1.3, 64), ("D", 1.0, 60),
]
GENED_BASE = {
    1: ["LAN022", "PSC101", "CSE013"],
    2: ["LAN111", "LAN112"],
    3: ["LAN114", "LIB116"],
    4: ["GEO217", "LAN130"],
    5: ["MGT222"],   # + elective 1
    6: [],           # elective 2
}
FALL_2026 = 19


def pick_letter(rng, center):
    target = max(1.0, min(4.0, rng.gauss(center + 0.2, 0.45)))
    return min(SCALE, key=lambda s: abs(s[1] - target))


async def main() -> None:
    async with AsyncSessionLocal() as db:
        guard = (await db.execute(text(
            "select count(*) from enrollments e join sections s on s.section_id=e.section_id "
            "join courses c on c.code=s.course_code where c.category_id=4"
        ))).scalar()
        if guard:
            print(f"ABORT: {guard} gen-ed enrollments already exist (already ran?)")
            return

        cgpa_by = {sid: (c if c is not None else 2.5)
                   for sid, c in (await db.execute(text("select student_id, cgpa from students"))).all()}

        rows = (await db.execute(text(
            "select e.student_id, s.semester_id from grades g "
            "join enrollments e on e.enrollment_id=g.enrollment_id "
            "join sections s on s.section_id=e.section_id "
            "join semesters sem on sem.semester_id=s.semester_id "
            "where lower(coalesce(sem.type,'')) <> 'summer' "
            "group by e.student_id, s.semester_id"
        ))).all()
        main_sems = defaultdict(set)
        for sid, semid in rows:
            main_sems[sid].add(semid)
        main_sems = {sid: sorted(v) for sid, v in main_sems.items()}

        sec_cache = {}

        async def get_section(course, sem_id, status="Closed", cap=250):
            key = (course, sem_id)
            if key in sec_cache:
                return sec_cache[key]
            sid = (await db.execute(text(
                "select section_id from sections where course_code=:c and semester_id=:s order by section_id limit 1"
            ), {"c": course, "s": sem_id})).scalar()
            if sid is None:
                sid = (await db.execute(text(
                    "insert into sections (semester_id, section_number, capacity, status, course_code, instructor_name) "
                    "values (:s,'GEN-1',:cap,:st,:c,'University Staff') returning section_id"
                ), {"s": sem_id, "cap": cap, "st": status, "c": course})).scalar()
            sec_cache[key] = sid
            return sid

        n_enr = 0
        for sid, sems in main_sems.items():
            if not sems:
                continue
            rng = random.Random(2026 + sid)
            e1, e2 = rng.sample(ELECTIVES, 2)
            sched = {1: GENED_BASE[1], 2: GENED_BASE[2], 3: GENED_BASE[3],
                     4: GENED_BASE[4], 5: GENED_BASE[5] + [e1], 6: [e2]}
            center = cgpa_by.get(sid, 2.5)
            for idx in range(1, min(len(sems), 6) + 1):
                sem_id = sems[idx - 1]
                for course in sched[idx]:
                    sec_id = await get_section(course, sem_id)
                    enr_id = (await db.execute(text(
                        "insert into enrollments (student_id, section_id, status, attempt_number, is_retake, enrollment_date) "
                        "values (:st,:sec,'Satisfied',1,false,(select start_date from semesters where semester_id=:sm)) "
                        "returning enrollment_id"
                    ), {"st": sid, "sec": sec_id, "sm": sem_id})).scalar()
                    if course in ZERO_CH:
                        letter, pts, pct, counts = "P", 4.0, None, False
                    else:
                        letter, pts, pct = pick_letter(rng, center)
                        counts = True
                    await db.execute(text(
                        "insert into grades (enrollment_id, grade_letter, grade_points, percentage, counts_in_gpa, is_improvement, grade_date) "
                        "values (:e,:l,:p,:pct,:c,false,(select end_date from semesters where semester_id=:sm))"
                    ), {"e": enr_id, "l": letter, "p": pts, "pct": pct, "c": counts, "sm": sem_id})
                    n_enr += 1

        # Fall 2026 offerings (Open) so the planner can schedule remaining gen-ed.
        new_offerings = 0
        for course in GENED_ALL:
            exists = (await db.execute(text(
                "select 1 from sections where course_code=:c and semester_id=:s limit 1"
            ), {"c": course, "s": FALL_2026})).scalar()
            if not exists:
                await db.execute(text(
                    "insert into sections (semester_id, section_number, capacity, status, course_code, instructor_name) "
                    "values (:s,'GEN-1',250,'Open',:c,'University Staff')"
                ), {"s": FALL_2026, "c": course})
                new_offerings += 1

        await db.commit()
        print(f"backfill: {n_enr} gen-ed enrollments+grades across {len(main_sems)} students; "
              f"sections touched={len(sec_cache)}; Fall2026 offerings added={new_offerings}")


if __name__ == "__main__":
    asyncio.run(main())
