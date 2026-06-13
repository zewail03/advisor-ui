"""SQLite -> PostgreSQL(+pgvector) catalog migration, trimmed to AIS + AIE.

What it does (idempotent — drops and recreates the PG schema):
  1. Creates the vector extension + all tables on Postgres.
  2. Copies the REAL catalog: programs, majors (AIS/AIE), semesters,
     registration periods, requirement categories, courses (closure of the two
     study plans + prerequisites), prerequisites, requirement groups (REBUILT:
     one group per elective basket instead of one fake group per course),
     requirement-group courses, sections + meetings, staff, advisors,
     policy_config.
  3. Fixes the planning horizon: Summer 2026 (id 18, NEW) and Fall 2026
     (id 19, remapped from 18) get real dates, cloned section offerings and
     open registration windows so the AI has real terms to plan into.
  4. programs.total_credits is recomputed as the SUM OF THE STUDY PLAN
     (required credits + one 3-credit pick per elective basket), because the
     imported catalog never contained the ~20 credits of general-education
     courses — completion-% rules must use an honest denominator.
  5. Resets every PG identity sequence.

Students/enrollments/grades are NOT copied — scripts/generate_students_pg.py
creates rule-clean cohorts instead.

Run:  python -m scripts.migrate_to_pg
"""
import asyncio
import os
import sqlite3
from datetime import date, datetime

PG_URL = os.environ.get(
    "PG_URL", "postgresql+asyncpg://aiu:aiu_dev@localhost:5433/aiu"
)
os.environ["DATABASE_URL"] = PG_URL  # before core.config import

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from core.database import Base  # noqa: E402
import models  # noqa: F401,E402  (register all tables)
from models.academic import (  # noqa: E402
    RegistrationPeriod, RequirementCategory, RequirementGroup, RequirementGroupCourse, Semester,
)
from models.advisor import Advisor  # noqa: E402
from models.course import Course, Prerequisite, Section, SectionMeeting  # noqa: E402
from models.policy import PolicyConfig  # noqa: E402
from models.staff import Staff  # noqa: E402
from models.student import Major, Program  # noqa: E402

SQLITE_DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "aiu.db")
KEPT_MAJORS = {"AIS": 1, "AIE": 3}        # major_code -> original major_id
ELECTIVE_PICKS_PER_GROUP = 1               # one 3-credit pick per basket
SEM_REMAP = {18: 19}                       # Fall 2026 moves to 19
SUMMER_2026_ID = 18                        # new term, keeps id order chronological
FALL_2026_ID = 19
CLONE_OFFSET = 100_000                     # new ids for cloned sections/meetings


def _d(v):
    return date.fromisoformat(v[:10]) if isinstance(v, str) and v else v


def _dt(v):
    if isinstance(v, str) and v:
        return datetime.fromisoformat(v.replace(" ", "T")[:26])
    return v


def fetch(cur, sql, args=()):
    cur.execute(sql, args)
    cols = [c[0] for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


async def main():
    src = sqlite3.connect(SQLITE_DB)
    cur = src.cursor()

    # ---------- figure out what to keep ----------
    rgc_rows = fetch(cur, "SELECT * FROM requirement_group_courses WHERE major_code IN ('AIS','AIE')")
    plan_codes = {r["course_code"] for r in rgc_rows}

    prereq_all = fetch(cur, "SELECT * FROM prerequisites")
    prereq_map = {}
    for p in prereq_all:
        prereq_map.setdefault(p["course_code"], set()).add(p["prerequisite_course_code"])
    kept_codes = set(plan_codes)
    frontier = set(plan_codes)
    while frontier:  # transitive prerequisite closure
        nxt = set()
        for c in frontier:
            for pre in prereq_map.get(c, ()):
                if pre not in kept_codes:
                    nxt.add(pre)
        kept_codes |= nxt
        frontier = nxt

    courses = [r for r in fetch(cur, "SELECT * FROM courses") if r["code"] in kept_codes]
    credits_by_code = {r["code"]: r["credits"] for r in courses}
    print(f"kept courses: {len(courses)} of 139 (plan {len(plan_codes)} + prereq closure)")

    # plan-sum credit totals per major (honest graduation denominator)
    totals = {}
    for mc in ("AIS", "AIE"):
        req = sum(credits_by_code.get(r["course_code"], 0)
                  for r in rgc_rows
                  if r["major_code"] == mc and r["group_name"].endswith("Required"))
        baskets = {r["group_name"] for r in rgc_rows
                   if r["major_code"] == mc and not r["group_name"].endswith("Required")}
        totals[mc] = req + 3 * ELECTIVE_PICKS_PER_GROUP * len(baskets)
    print(f"program totals from plan: {totals}")

    # ---------- create the PG schema ----------
    engine = create_async_engine(PG_URL, echo=False)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    ins = []  # (table, rows) in FK-safe order

    programs = fetch(cur, "SELECT * FROM programs")
    for p in programs:
        mc = "AIS" if p["program_id"] == 1 else "AIE"
        p["total_credits"] = totals[mc]
    ins.append((Program.__table__, programs))

    majors = [m for m in fetch(cur, "SELECT * FROM majors") if m["code"] in KEPT_MAJORS]
    ins.append((Major.__table__, majors))

    semesters = fetch(cur, "SELECT * FROM semesters")
    for s in semesters:
        s["semester_id"] = SEM_REMAP.get(s["semester_id"], s["semester_id"])
        s["start_date"], s["end_date"] = _d(s["start_date"]), _d(s["end_date"])
        if s["semester_id"] == FALL_2026_ID:  # was dateless
            s.update(start_date=date(2026, 9, 20), end_date=date(2027, 1, 8),
                     weeks=16, type="Fall", year_start=2026, year_end=2027)
    semesters.append({
        "semester_id": SUMMER_2026_ID, "code": "Summer 2026", "type": "Summer",
        "year_start": 2026, "year_end": 2026, "start_date": date(2026, 6, 15),
        "end_date": date(2026, 8, 8), "weeks": 8, "is_optional": 1,
    })
    ins.append((Semester.__table__, semesters))

    periods = fetch(cur, "SELECT * FROM registration_periods")
    for p in periods:
        p["semester_id"] = SEM_REMAP.get(p["semester_id"], p["semester_id"])
        p["open_date"], p["close_date"] = _dt(p["open_date"]), _dt(p["close_date"])
    next_id = max(p["registration_period_id"] for p in periods) + 1
    # open windows for the two plannable terms (today is mid-June 2026)
    for sem_id, close in ((SUMMER_2026_ID, datetime(2026, 6, 14, 23, 59)),
                          (FALL_2026_ID, datetime(2026, 9, 19, 23, 59))):
        periods.append({"registration_period_id": next_id, "semester_id": sem_id,
                        "priority_group": "Normal", "open_date": datetime(2026, 6, 1, 9, 0),
                        "close_date": close, "is_active": 1})
        next_id += 1
    ins.append((RegistrationPeriod.__table__, periods))

    ins.append((RequirementCategory.__table__, fetch(cur, "SELECT * FROM requirement_categories")))
    ins.append((Course.__table__, courses))

    seen, prereqs = set(), []
    for p in prereq_all:
        pair = (p["course_code"], p["prerequisite_course_code"])
        if pair in seen or p["course_code"] not in kept_codes or p["prerequisite_course_code"] not in kept_codes:
            continue
        seen.add(pair)
        prereqs.append(p)
    ins.append((Prerequisite.__table__, prereqs))

    # rebuilt requirement groups: ONE row per (major, basket)
    groups, gid = [], 1
    for mc, mid in KEPT_MAJORS.items():
        names = sorted({r["group_name"] for r in rgc_rows if r["major_code"] == mc})
        for name in names:
            members = [r for r in rgc_rows if r["major_code"] == mc and r["group_name"] == name]
            required = name.endswith("Required")
            groups.append({
                "group_id": gid,
                "program_id": members[0]["program_id"],
                "name": name,
                "course_code": None, "course_name": None,
                "description": ("All required courses" if required
                                else f"Elective basket — pick {ELECTIVE_PICKS_PER_GROUP} of {len(members)}"),
                "min_courses": len(members) if required else ELECTIVE_PICKS_PER_GROUP,
                "min_credits": (sum(credits_by_code.get(m["course_code"], 0) for m in members)
                                if required else 3 * ELECTIVE_PICKS_PER_GROUP),
                "major_id": mid,
            })
            gid += 1
    ins.append((RequirementGroup.__table__, groups))
    ins.append((RequirementGroupCourse.__table__, rgc_rows))

    sections = [s for s in fetch(cur, "SELECT * FROM sections WHERE semester_id <= 17")
                if s["course_code"] in kept_codes]
    meetings = fetch(
        cur,
        f"SELECT m.* FROM section_meetings m JOIN sections s ON s.section_id=m.section_id "
        f"WHERE s.semester_id <= 17 AND s.course_code IN ({','.join('?' * len(kept_codes))})",
        tuple(kept_codes),
    )
    # clone Fall 2025 (16) -> Fall 2026 (19) and Summer 2025 (15) -> Summer 2026 (18)
    # (future offerings always open as Open — source rows may be Closed)
    for src_sem, dst_sem in ((16, FALL_2026_ID), (15, SUMMER_2026_ID)):
        offset = CLONE_OFFSET * (1 if dst_sem == FALL_2026_ID else 2)
        for s in [x for x in sections if x["semester_id"] == src_sem]:
            sections.append({**s, "section_id": s["section_id"] + offset,
                             "semester_id": dst_sem, "status": "Open"})
        src_ids = {x["section_id"] for x in sections
                   if x["semester_id"] == src_sem}
        for m in [x for x in meetings if x["section_id"] in src_ids]:
            meetings.append({**m, "meeting_id": m["meeting_id"] + offset,
                             "section_id": m["section_id"] + offset})
    # Plan courses the old dataset NEVER offered (e.g. PHY211 — required in
    # AIS year 1): without sections no study plan is completable. Synthesize a
    # recurring offering (2 sections, every term) with real instructors.
    offered_codes = {s["course_code"] for s in sections}
    missing = sorted(plan_codes - offered_codes)
    if missing:
        print(f"synthesizing offerings for never-offered plan courses: {missing}")
        instructors = [a["full_name"] for a in fetch(cur, "SELECT full_name FROM advisors")]
        days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"]
        slots = [("09:00", "10:30"), ("11:00", "12:30"), ("13:00", "14:30"), ("15:00", "16:30")]
        next_id = 300_000
        for i, code in enumerate(missing):
            for sem in [s["semester_id"] for s in semesters]:
                for sec_no in (1, 2):
                    next_id += 1
                    sections.append({
                        "section_id": next_id, "semester_id": sem, "section_number": str(sec_no),
                        "capacity": 35, "status": "Open", "course_code": code,
                        "instructor_name": instructors[(i * 2 + sec_no) % len(instructors)],
                    })
                    meetings.append({
                        "meeting_id": next_id, "section_id": next_id, "meeting_type": "Lecture",
                        "day_of_week": days[(i + sec_no) % 5],
                        "start_time": slots[(i + sem + sec_no) % 4][0],
                        "end_time": slots[(i + sem + sec_no) % 4][1],
                        "location": f"B{(i % 4) + 1}-{110 + i}",
                    })
    ins.append((Section.__table__, sections))
    ins.append((SectionMeeting.__table__, meetings))

    ins.append((Staff.__table__, [
        {**r, "created_at": _dt(r["created_at"]), "last_login_at": _dt(r["last_login_at"])}
        for r in fetch(cur, "SELECT * FROM staff")
    ]))
    ins.append((Advisor.__table__, fetch(cur, "SELECT * FROM advisors")))
    ins.append((PolicyConfig.__table__, [
        {**r, "updated_at": _dt(r.get("updated_at"))}
        for r in fetch(cur, "SELECT * FROM policy_config")
    ]))

    # ---------- coerce + bulk insert ----------
    from sqlalchemy import Boolean, Date, DateTime

    def coerce(table, row):
        out = {}
        for col in table.columns:
            if col.name not in row:
                continue
            v = row[col.name]
            if v is not None:
                if isinstance(col.type, Boolean):
                    v = bool(v)
                elif isinstance(col.type, DateTime):
                    v = _dt(v)
                elif isinstance(col.type, Date):
                    v = _d(v)
            out[col.name] = v
        return out

    async with engine.begin() as conn:
        for table, rows in ins:
            if not rows:
                continue
            await conn.execute(table.insert(), [coerce(table, r) for r in rows])
            print(f"  {table.name}: {len(rows)}")
        # reset identity sequences for explicit-PK inserts
        for table, _ in ins:
            pk = list(table.primary_key.columns)[0]
            if pk.type.python_type is int:
                await conn.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{table.name}', '{pk.name}'), "
                    f"COALESCE((SELECT MAX({pk.name}) FROM {table.name}), 1))"
                ))
    await engine.dispose()
    src.close()
    print("catalog migration complete.")


if __name__ == "__main__":
    asyncio.run(main())
