"""Regenerate the 220 AIS students PLAN-DRIVEN: every student walks the official
AIS study plan term-by-term, so the cohort starts identically (Sem 1 is the same
for everyone). Divergence comes only from grades, failures->retakes (which push
courses to later terms), elective picks, and the edge-case archetypes.

Replaces the old greedy "fill to the credit limit" packing (which leaked Sem-2
courses into Sem 1). Sections are created on demand so every plan course is
offerable in every cohort's semester.

Run AFTER the catalog is the trimmed AIS+gen-ed set (63 courses, 133 CH):
  .\\venv\\Scripts\\python.exe -m scripts.regenerate_ais_plan
Backup first (this rebuilds all transcripts): aiu_pre_replan.dump
"""
import asyncio
import os
import random
import sqlite3
from datetime import date, datetime, timedelta
from uuid import uuid4

PG_URL = os.environ.get("PG_URL", "postgresql+asyncpg://aiu:aiu_dev@localhost:5433/aiu")
os.environ["DATABASE_URL"] = PG_URL

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from models.advisor import AdvisorAssignment  # noqa: E402
from models.ai_models import Notification  # noqa: E402
from models.enrollment import Enrollment, Grade  # noqa: E402
from models.financial import FinancialAccount, FinancialTransaction, Scholarship  # noqa: E402
from models.petitions import Petition  # noqa: E402
from models.student import Student  # noqa: E402

SQLITE_DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "aiu.db")
rng = random.Random(2026)

# ---- calendar (PG semester ids are chronological) ----
MAINS = [1, 2, 4, 5, 7, 8, 10, 11, 13, 14, 16, 17]
SUMMER_AFTER = {2: 3, 5: 6, 8: 9, 11: 12, 14: 15, 17: 18}
GRADED_THROUGH = 17                                   # Summer 2026 (18) = in progress
ENTRY_SEMESTER = {21: 4, 22: 7, 23: 10, 24: 13, 25: 16}
SEM_DATES = {}

COHORTS = {("AIS", 25): 55, ("AIS", 24): 50, ("AIS", 23): 45, ("AIS", 22): 40, ("AIS", 21): 30}
MAJOR_ID = {"AIS": 1}
PROGRAM_ID = {"AIS": 1}
DURATION = {"AIS": 4}
IMPROVE_CAP = {"AIS": 9}
DEMO_HASH = "$2b$12$Q1/N2pwzP3PtmkXts6vdU.XDBQJyP1eOzfjJKbPsLLuHlBHwTqFo6"

# ---- the official AIS study plan, by slot (1..8). "C"=fixed course, "E"=elective basket ----
PLAN = {
    1: [("C", "MAT111"), ("C", "PHY211"), ("C", "CSE014"), ("C", "LAN022"), ("C", "PSC101"), ("C", "CSE013")],
    2: [("C", "MAT112"), ("C", "MAT131"), ("C", "CSE015"), ("C", "CSE315"), ("C", "LAN111"), ("C", "LAN112")],
    3: [("C", "MAT212"), ("C", "MAT231"), ("C", "CSE111"), ("C", "CSE131"), ("C", "AIE111"), ("C", "LAN114")],
    4: [("C", "MAT312"), ("C", "CSE132"), ("C", "CSE221"), ("C", "CSE281"), ("C", "AIE121"), ("C", "AIE191"), ("C", "LIB116")],
    5: [("C", "CSE233"), ("C", "CSE251"), ("C", "CSE261"), ("C", "AIE231"), ("C", "AIE323"), ("C", "GEO217")],
    6: [("C", "CSE112"), ("C", "AIE212"), ("C", "AIE213"), ("C", "AIE241"), ("C", "AIE292"), ("E", "AIS E1"), ("C", "LAN130")],
    7: [("C", "CSE363"), ("C", "AIE322"), ("C", "AIE332"), ("C", "AIE493"), ("E", "AIS E2"), ("C", "MGT222"), ("E", "University Elective")],
    8: [("C", "AIE425"), ("C", "AIE314"), ("C", "AIE494"), ("E", "AIS E3"), ("E", "University Elective")],
}
BASKETS = {
    "AIS E1": ["CSE211", "CSE234", "CSE344", "CSE382", "CSE383"],
    "AIS E2": ["AIE351", "AIE417", "CSE464"],
    "AIS E3": ["AIE418"],
    "University Elective": ["PHS071", "PSC207", "MGT201", "MGT102", "ADL123", "MGT121", "LAN211"],
}

LETTERS = [("A+", 4.0, 96), ("A", 4.0, 93), ("A-", 3.7, 89), ("B+", 3.3, 85),
           ("B", 3.0, 81), ("B-", 2.7, 77), ("C+", 2.3, 74), ("C", 2.0, 70),
           ("C-", 1.7, 66), ("D+", 1.3, 62), ("D", 1.0, 58)]
ARCHETYPES = [("strong", 3.45, 0.22), ("good", 3.00, 0.35), ("average", 2.60, 0.25),
              ("weak", 2.10, 0.12), ("at_risk", 1.55, 0.06)]


def pick_archetype():
    x, acc = rng.random(), 0.0
    for name, mu, w in ARCHETYPES:
        acc += w
        if x <= acc:
            return name, mu
    return "average", 2.6


def sample_grade(mu, level):
    sigma = 0.55 + max(0.0, (3.2 - mu)) * 0.28
    s = rng.gauss(mu - (0.15 if level >= 3 else 0.0) - (0.10 if level >= 4 else 0.0), sigma)
    if s < 0.8:
        return ("F", 0.0, rng.randint(25, 49))
    best = min(LETTERS[1:], key=lambda L: abs(L[1] - s))
    if best[0] == "A" and s > 4.05 and rng.random() < 0.5:
        best = LETTERS[0]
    return (best[0], best[1], min(99, best[2] + rng.randint(-2, 2)))


def cap_letter(letter, points, cap=3.3):
    return (letter, points) if points <= cap else ("B+", cap)


class Sim:
    def __init__(self, sid, code, major, yy, archetype, mu, flags):
        self.sid, self.code, self.major, self.yy = sid, code, major, yy
        self.archetype, self.mu, self.flags = archetype, mu, flags
        self.math0 = flags.get("math0", rng.random() < 0.88)
        self.cum_pts = 0.0
        self.cum_cr = 0
        self.passed = {}
        self.failed_open = []
        self.improve_credits = 0
        self.warn = 0
        self.severe = 0
        self.dismissed_at = None
        self.graduated_at = None
        self.frozen = set(flags.get("freeze_sems", ()))
        self.enrollments = []
        self.grades = []
        self.mains_done = 0
        self.loaded_upto = 0
        self.pending = []           # carry-over plan items not yet taken
        self.taken_ever = set()

    @property
    def cgpa(self):
        return round(self.cum_pts / self.cum_cr, 3) if self.cum_cr else 0.0

    def limit_for(self, slot, is_summer):
        if is_summer:
            return 9
        if slot <= 1:
            return 16 if self.math0 else 12
        if slot == 2:
            return 16
        if slot == 3:
            return 20 if self.cgpa >= 1.667 else 12
        if self.cgpa > 3.0:
            return 22
        return 20 if self.cgpa >= 2.0 else 12

    def standing_step(self, slot, is_summer):
        if self.dismissed_at:
            return
        if slot < 3:
            self.warn = self.severe = 0
            return
        bar = 1.667 if slot == 3 else 2.0
        if is_summer:
            if self.warn and self.cgpa >= bar:
                self.warn = self.severe = 0
            return
        if self.cgpa >= bar:
            self.warn = self.severe = 0
            return
        self.warn += 1
        self.severe = self.severe + 1 if self.cgpa < 1.0 else 0
        if self.severe >= 3 or self.warn >= 4:
            self.dismissed_at = True

    def load_plan(self, upto):
        upto = min(upto, 8)
        while self.loaded_upto < upto:
            self.loaded_upto += 1
            self.pending.extend(PLAN.get(self.loaded_upto, []))


async def main():
    engine = create_async_engine(PG_URL, echo=False)

    async with engine.connect() as conn:
        for sid_, code_, type_, sd, ed in (await conn.execute(text(
                "SELECT semester_id, code, type, start_date, end_date FROM semesters"))).all():
            SEM_DATES[sid_] = {"code": code_, "type": type_, "start": sd, "end": ed}
        credits = {c: cr for c, cr in (await conn.execute(text("SELECT code, credits FROM courses"))).all()}
        offered = {}
        for sec_id, ccode, sem_id in (await conn.execute(text(
                "SELECT section_id, course_code, semester_id FROM sections"))).all():
            offered.setdefault((ccode, sem_id), sec_id)
        prereqs = {}
        for c, p in (await conn.execute(text(
                "SELECT course_code, prerequisite_course_code FROM prerequisites"))).all():
            prereqs.setdefault(c, []).append(p)
        next_sid_seq = (await conn.execute(text("SELECT COALESCE(MAX(section_id),0)+1 FROM sections"))).scalar()

    new_sections = []
    instructors = ["Dr. Mona Adel", "Dr. Karim Fouad", "Dr. Salma Nabil", "Eng. Omar Tarek",
                   "Dr. Hana Mostafa", "University Staff", "Dr. Youssef Aziz"]

    def section_for(course, sem_id):
        nonlocal next_sid_seq
        key = (course, sem_id)
        if key in offered:
            return offered[key]
        sid_ = next_sid_seq
        next_sid_seq += 1
        info = SEM_DATES[sem_id]
        status = "Open" if sem_id >= 18 else "Closed"
        new_sections.append({
            "section_id": sid_, "semester_id": sem_id, "section_number": f"S{(sid_ % 90) + 1}",
            "capacity": 250, "status": status, "course_code": course,
            "instructor_name": rng.choice(instructors),
        })
        offered[key] = sid_
        return sid_

    # demographics from the old DB (real, reused)
    src = sqlite3.connect(SQLITE_DB)
    bundles = src.execute(
        "SELECT full_name, gender, nationality, city, home_address, postal_code, "
        "emergency_contact_name, emergency_relationship, emergency_phone, emergency_email, "
        "phone, school_id FROM students WHERE full_name IS NOT NULL").fetchall()
    src.close()
    rng.shuffle(bundles)

    # ---- build sims (same cohort/archetype scheme as the original generator) ----
    sims, students_rows = [], []
    sid = 0
    used_names = set()
    for (major, yy), count in COHORTS.items():
        for i in range(count):
            sid += 1
            serial = 1 + i
            if major == "AIS" and yy == 25 and i == count - 1:
                serial = 103
            code = f"{yy}10{serial:04d}"

            flags = {}
            arch, mu = pick_archetype()
            if i == 0 and yy <= 23:
                arch, mu = "dismissed_track", 1.75
            elif i == 1 and yy <= 23:
                arch, mu = "dismissed_severe", 0.85
            elif i == 2 and yy <= 23:
                arch, mu, flags["takes_summer"] = "summer_recovery", 2.15, True
            elif i == 3 and yy <= 23:
                arch, mu = "freeze", 2.7
                entry = ENTRY_SEMESTER[yy]
                flags["freeze_sems"] = {MAINS[MAINS.index(entry) + 2]}
            elif i in (4, 5):
                arch, mu, flags["takes_summer"] = "fast_track", 3.35, True
            elif i == 6:
                arch, mu = "scholar", 3.95
            elif i == 7 and yy <= 23:
                arch, mu, flags["improver"] = "improver", 2.85, True
            if rng.random() < 0.12:
                flags["takes_summer"] = True
            if major == "AIS" and yy == 25 and serial in (45, 103, 2):
                flags["takes_summer"] = True  # keep demo students with current courses

            sims.append(Sim(sid, code, major, yy, arch, mu, flags))

    # ---- simulate each student through the plan ----
    eid = gid = 0
    sem_order = sorted(SEM_DATES)
    for s in sims:
        entry = ENTRY_SEMESTER[s.yy]
        for sem_id in [x for x in sem_order if entry <= x <= 18]:
            if s.dismissed_at or s.graduated_at:
                break
            if sem_id in s.frozen:
                continue
            info = SEM_DATES[sem_id]
            is_summer = (info["type"] or "").lower() == "summer"

            high = s.archetype in ("fast_track", "scholar")
            if is_summer and not (s.flags.get("takes_summer") or s.warn > 0 or s.failed_open or
                                  (high and s.pending)):
                continue

            slot = s.mains_done + 1
            limit = s.limit_for(slot, is_summer)
            if not is_summer:
                # Year 1 (slots 1-2) is lockstep for the whole cohort; high achievers
                # only start pulling future terms forward (overload) from slot 3.
                s.load_plan(8 if (high and slot >= 3) else slot)
            target = limit if high else (min(limit, 9) if is_summer else min(limit, 18))

            chosen, load, picked = [], 0, set()

            def can_take(c):
                return all(s.passed.get(p, 0) >= 1.0 for p in prereqs.get(c, ()))

            # retakes of failed required courses first (catch-up)
            for c in list(s.failed_open):
                cr = credits.get(c, 3)
                if c not in picked and load + cr <= limit and can_take(c):
                    chosen.append((c, True, False)); load += cr; picked.add(c); s.failed_open.remove(c)

            if not is_summer:
                still = []
                for item in s.pending:
                    if load >= target:
                        still.append(item); continue
                    if item[0] == "C":
                        c = item[1]
                        if c in s.taken_ever or c in picked:
                            continue
                        cr = credits.get(c, 3)
                        if can_take(c) and load + cr <= limit:
                            chosen.append((c, False, False)); load += cr; picked.add(c)
                        else:
                            still.append(item)
                    else:
                        opts = [c for c in BASKETS.get(item[1], ())
                                if c not in s.taken_ever and c not in picked and can_take(c)
                                and load + credits.get(c, 3) <= limit]
                        if opts:
                            c = rng.choice(opts)
                            chosen.append((c, False, False)); load += credits.get(c, 3); picked.add(c)
                        else:
                            still.append(item)
                s.pending = still

            # improvement retakes (within cap), improver archetype, room remaining
            if s.flags.get("improver") and not is_summer and slot >= 5:
                for c, pts in sorted(s.passed.items(), key=lambda kv: kv[1]):
                    cr = credits.get(c, 3)
                    if pts > 2.3 or c in picked or load + cr > min(limit, target + 3) or s.improve_credits + cr > IMPROVE_CAP[s.major]:
                        continue
                    chosen.append((c, False, True)); load += cr; picked.add(c); s.improve_credits += cr

            if not chosen:
                if not is_summer:
                    s.mains_done += 1
                continue

            for c, is_retake, is_improve in chosen:
                eid += 1
                sec_id = section_for(c, sem_id)
                attempt = 2 if (is_retake or is_improve) else 1
                graded = sem_id <= GRADED_THROUGH
                enr = {"enrollment_id": eid, "student_id": s.sid, "section_id": sec_id,
                       "status": "Enrolled", "attempt_number": attempt,
                       "is_retake": is_retake or is_improve,
                       "enrollment_date": datetime.combine(info["start"], datetime.min.time()) - timedelta(days=rng.randint(5, 20)),
                       "drop_date": None, "withdrawal_date": None}
                s.taken_ever.add(c)
                if not graded:
                    s.enrollments.append(enr)
                    continue

                boost = 0.35 if is_retake else (0.5 if is_improve else 0.0)
                if is_summer and s.archetype == "summer_recovery":
                    boost += 1.0
                level = int(c[3]) if len(c) > 3 and c[3].isdigit() else 1
                if c in ("LAN022", "PSC101"):  # 0-CH pass/fail
                    letter, pts, pct, counts = "P", 4.0, None, False
                else:
                    letter, pts, pct = sample_grade(s.mu + boost, level)
                    counts = True
                    if is_retake:
                        letter, pts = cap_letter(letter, pts)
                    if is_improve and pts <= s.passed.get(c, 0):
                        letter, pts, pct = "B+", max(3.3, s.passed.get(c, 0)), 85

                enr["status"] = "Failed" if letter == "F" else "Satisfied"
                s.enrollments.append(enr)
                gid += 1
                s.grades.append({"grade_id": gid, "enrollment_id": eid, "grade_letter": letter,
                                 "grade_points": pts, "percentage": float(pct) if pct is not None else None,
                                 "counts_in_gpa": counts, "is_improvement": is_improve,
                                 "grade_date": datetime.combine(info["end"], datetime.min.time()),
                                 "_course": c})
                cr = credits.get(c, 3)
                if (is_retake or is_improve):  # supersede the prior counted attempt (latest counts)
                    for g_old in s.grades[:-1]:
                        if g_old.get("_course") == c and g_old["counts_in_gpa"] and g_old["grade_points"] is not None:
                            g_old["counts_in_gpa"] = False
                            s.cum_pts -= g_old["grade_points"] * cr
                            s.cum_cr -= cr
                if letter == "F":
                    s.failed_open.append(c)
                    s.cum_cr += cr   # F counts as 0 points until retaken (matches replay engine)
                elif counts:
                    s.passed[c] = max(s.passed.get(c, 0), pts)
                    s.cum_pts += pts * cr
                    s.cum_cr += cr
                else:
                    s.passed[c] = max(s.passed.get(c, 0), 4.0)  # P -> passed, no GPA

            if sem_id <= GRADED_THROUGH:
                if not is_summer:
                    s.mains_done += 1
                s.standing_step(s.mains_done, is_summer)
                all_required_done = all(
                    (it[1] in s.passed) if it[0] == "C" else True
                    for sl in PLAN.values() for it in sl
                ) and not s.pending and not s.failed_open
                if all_required_done and s.loaded_upto >= 8:
                    s.graduated_at = sem_id

        # ----- student master row -----
        b = bundles[(s.sid - 1) % len(bundles)]
        name = b[0]
        if name in used_names:
            name = f"{name.split()[0]} {rng.choice(bundles)[0].split()[-1]}"
        used_names.add(name)
        first = "".join(ch for ch in name.split()[0].lower() if ch.isalpha())
        last = "".join(ch for ch in name.split()[-1].lower() if ch.isalpha())
        entry_date = SEM_DATES[ENTRY_SEMESTER[s.yy]]["start"]
        status = ("Dismissed" if s.dismissed_at else "Graduated" if s.graduated_at
                  else "Probation" if s.warn > 0 else "Active")
        duration = DURATION[s.major]
        level = duration if s.graduated_at else max(1, min(duration, (s.mains_done + 1) // 2))
        grad = (SEM_DATES[s.graduated_at]["end"] if s.graduated_at else date(2000 + s.yy + duration, 6, 30))
        students_rows.append({
            "student_id": s.sid, "student_code": s.code, "full_name": name,
            "email": f"{first}.{last}.{s.code}@aiu.edu.eg", "phone": b[10], "hashed_password": DEMO_HASH,
            "program_id": PROGRAM_ID[s.major], "major_id": MAJOR_ID[s.major], "level": level, "status": status,
            "enrollment_date": entry_date, "expected_graduation": grad, "cgpa": s.cgpa, "math0_passed": s.math0,
            "created_at": datetime.combine(entry_date, datetime.min.time()),
            "date_of_birth": f"{2000 + s.yy - 18 - rng.randint(0, 1)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
            "gender": b[1], "nationality": b[2], "school_id": b[11], "home_address": b[4], "city": b[3],
            "postal_code": b[5], "emergency_contact_name": b[6], "emergency_relationship": b[7],
            "emergency_phone": b[8], "emergency_email": b[9],
        })

    for g in (g for s in sims for g in s.grades):
        g.pop("_course", None)

    all_enr = [e for s in sims for e in s.enrollments]
    all_grades = [g for s in sims for g in s.grades]

    async with engine.begin() as conn:
        for tbl in ("waitlist", "notifications", "advisor_assignments", "petitions",
                    "financial_transactions", "scholarships", "financial_accounts",
                    "academic_standing", "grades", "enrollments", "students"):
            await conn.execute(text(f"DELETE FROM {tbl}"))
        if new_sections:
            from models.course import Section
            for i in range(0, len(new_sections), 5000):
                await conn.execute(Section.__table__.insert(), new_sections[i:i + 5000])
        await conn.execute(Student.__table__.insert(), students_rows)
        for i in range(0, len(all_enr), 5000):
            await conn.execute(Enrollment.__table__.insert(), all_enr[i:i + 5000])
        for i in range(0, len(all_grades), 5000):
            await conn.execute(Grade.__table__.insert(), all_grades[i:i + 5000])
    print(f"students={len(students_rows)} enrollments={len(all_enr)} grades={len(all_grades)} new_sections={len(new_sections)}")

    from core.database import AsyncSessionLocal
    from services.standing import replay_student_standing
    async with AsyncSessionLocal() as db:
        for n, s in enumerate(sims, 1):
            await replay_student_standing(s.sid, db)
            if n % 50 == 0:
                await db.commit()
        await db.commit()

    # ---- satellites (advisors, notifications, summer-2026 financials, sample petitions) ----
    today = datetime(2026, 6, 13, 9, 0)
    assigns, notifs, accounts, txns, schols, petitions = [], [], [], [], [], []
    async with engine.connect() as conn:
        st_rows = (await conn.execute(text(
            "SELECT student_id, student_code, full_name, cgpa, status FROM students"))).all()
        cur_enr = (await conn.execute(text(
            "SELECT e.student_id, SUM(c.credits) FROM enrollments e JOIN sections sec ON sec.section_id=e.section_id "
            "JOIN courses c ON c.code=sec.course_code WHERE e.status='Enrolled' AND sec.semester_id=18 GROUP BY e.student_id"))).all()
    summer_credits = {a: int(b or 0) for a, b in cur_enr}
    aid = 0
    for sid_, code_, name_, cgpa_, status_ in st_rows:
        aid += 1
        assigns.append({"advisor_assignment_id": aid, "advisor_id": (sid_ % 40) + 1, "advisor_name": None,
                        "student_code": code_, "student_name": name_,
                        "assigned_date": date(2000 + int(code_[:2]), 9, 15), "end_date": None, "is_active": True})
        notifs.append({"student_id": sid_, "type": "academic", "subject": "Spring 2026 grades posted",
                       "message": "Your Spring 2026 grades are now available in Academic Records.",
                       "status": "Unread", "created_at": datetime(2026, 6, 5, 10, 0), "sent_at": datetime(2026, 6, 5, 10, 0)})
        if status_ in ("Active", "Probation"):
            notifs.append({"student_id": sid_, "type": "registration", "subject": "Fall 2026 registration is open",
                           "message": "Plan your Fall 2026 schedule - registration closes September 19.",
                           "status": "Unread", "created_at": datetime(2026, 6, 1, 9, 0), "sent_at": datetime(2026, 6, 1, 9, 0)})
        cr = summer_credits.get(sid_, 0)
        tuition, transport = cr * 2750, (13000 if cr else 0)
        eligible = (cgpa_ or 0) >= 3.9 and tuition > 0
        schol = tuition if eligible else 0
        if cr:
            bal = tuition + transport - schol
            accounts.append({"id": str(uuid4()), "student_id": sid_, "semester_code": "Summer 2026", "term_credits": cr,
                             "tuition_fee": tuition, "transportation_fee": transport, "fines": 0,
                             "total_charges": tuition + transport, "scholarship_credit": schol, "payments_made": 0,
                             "current_balance": bal, "payment_due_date": "2026-07-10",
                             "payment_status": "Paid" if bal <= 0 else "Due", "currency": "EGP", "last_updated": today})
            txns.append({"id": str(uuid4()), "student_id": sid_, "transaction_ref": f"CHG-{sid_}-SU26",
                         "semester_code": "Summer 2026", "date": "2026-06-05", "type": "charge", "category": "Tuition",
                         "description": f"Summer charge ({cr} credits)", "amount": tuition, "currency": "EGP",
                         "status": "Posted", "reference": ""})
            if eligible:
                schols.append({"id": str(uuid4()), "student_id": sid_, "scholarship_ref": f"SCH-{sid_}-01",
                               "semester_code": "Summer 2026", "scholarship_type": "Academic Excellence Scholarship",
                               "percentage": 100, "amount": schol, "status": "Active", "criteria_basis": "CGPA",
                               "cgpa_at_award": cgpa_, "notes": "Rule: CGPA >= 3.9 -> 100% tuition"})
        elif status_ in ("Active", "Probation", "Graduated"):
            accounts.append({"id": str(uuid4()), "student_id": sid_, "semester_code": "Spring 2026", "term_credits": 0,
                             "tuition_fee": 0, "transportation_fee": 0, "fines": 0, "total_charges": 0,
                             "scholarship_credit": 0, "payments_made": 0, "current_balance": 0,
                             "payment_due_date": None, "payment_status": "Paid", "currency": "EGP", "last_updated": today})

    for s in [s for s in sims if s.frozen][:3]:
        sem = SEM_DATES[next(iter(s.frozen))]["code"]
        petitions.append({"id": str(uuid4()), "student_id": s.sid, "type": "freeze", "status": "approved",
                          "subject": f"Semester freeze - {sem}", "body": "Medical circumstances required a freeze.",
                          "freeze_semester_code": sem, "effect_applied": True,
                          "submitted_at": datetime(2000 + s.yy + 1, 8, 20, 10, 0),
                          "decided_at": datetime(2000 + s.yy + 1, 8, 25, 10, 0),
                          "reviewer_id": "registrar", "reviewer_role": "registrar",
                          "decision_comment": "Approved per section 15 - within freeze caps."})
    for s in [s for s in sims if s.dismissed_at][:1]:
        petitions.append({"id": str(uuid4()), "student_id": s.sid, "type": "final_chance", "status": "submitted",
                          "subject": "Final chance request", "body": "Requesting a final-chance semester to complete my degree.",
                          "freeze_semester_code": None, "effect_applied": False, "submitted_at": today,
                          "decided_at": None, "reviewer_id": None, "reviewer_role": None, "decision_comment": None})

    async with engine.begin() as conn:
        await conn.execute(AdvisorAssignment.__table__.insert(), assigns)
        await conn.execute(Notification.__table__.insert(), notifs)
        if accounts:
            await conn.execute(FinancialAccount.__table__.insert(), accounts)
        if txns:
            await conn.execute(FinancialTransaction.__table__.insert(), txns)
        if schols:
            await conn.execute(Scholarship.__table__.insert(), schols)
        if petitions:
            await conn.execute(Petition.__table__.insert(), petitions)
        for tname, pk in (("students", "student_id"), ("enrollments", "enrollment_id"), ("grades", "grade_id"),
                          ("sections", "section_id"), ("notifications", "notification_id"),
                          ("advisor_assignments", "advisor_assignment_id"),
                          ("academic_standing", "academic_standing_id"), ("waitlist", "waitlist_id")):
            await conn.execute(text(f"SELECT setval(pg_get_serial_sequence('{tname}','{pk}'), "
                                    f"COALESCE((SELECT MAX({pk}) FROM {tname}),1))"))

    async with engine.connect() as conn:
        print("\n--- verification ---")
        for label, sql in [
            ("status mix", "SELECT status, COUNT(*) FROM students GROUP BY status ORDER BY 2 DESC"),
            ("prereq violations", """SELECT COUNT(*) FROM enrollments e JOIN sections sec ON sec.section_id=e.section_id
                JOIN prerequisites p ON p.course_code=sec.course_code WHERE NOT EXISTS (
                  SELECT 1 FROM enrollments e2 JOIN sections s2 ON s2.section_id=e2.section_id
                  JOIN grades g2 ON g2.enrollment_id=e2.enrollment_id WHERE e2.student_id=e.student_id
                  AND s2.course_code=p.prerequisite_course_code AND s2.semester_id<sec.semester_id AND g2.grade_points>=1.0)"""),
            ("cgpa drift vs standing", """SELECT COUNT(*) FROM students s JOIN academic_standing a ON a.student_code=s.student_code
                WHERE a.semester_id=(SELECT MAX(a2.semester_id) FROM academic_standing a2 WHERE a2.student_code=s.student_code)
                AND ABS(COALESCE(a.cgpa,0)-COALESCE(s.cgpa,0))>0.001"""),
        ]:
            rows = (await conn.execute(text(sql))).all()
            print(f"{label}: {rows if len(rows) > 1 else rows[0]}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
