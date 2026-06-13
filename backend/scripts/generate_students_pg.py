"""Generate ~400 rule-clean AIS/AIE students on PostgreSQL.

Cohorts follow the student-code convention (Dr. Ashraf): the code prefix is
the entry year — 25xxxxxx = 1st year, 24 = 2nd, 23 = 3rd, 22 = 4th,
21 = graduated (AIS, 4-year) or 5th year (AIE, 5-year).

Every transcript is SIMULATED through the actual business rules:
  * semester-indexed credit-limit ladder (Math 0 / 16CH / 1.667 / 2.0 / overload)
  * prerequisites must be passed (>= D) in an EARLIER semester
  * courses only taken when a section is offered that semester
  * failed-course retakes capped at B+ (old F stops counting)
  * improvement retakes within the 9/12-CH cap (latest counts)
  * warning/dismissal ladder + summer recovery (replayed at the end through
    services.standing — the PRODUCTION engine writes academic_standing)

Timeline (today = June 2026): grades posted through Spring 2026 (sem 17);
Summer 2026 (18) has in-progress enrollments; Fall 2026 (19) is the empty
planning target for the AI schedule generator.

Run AFTER scripts.migrate_to_pg:  python -m scripts.generate_students_pg
"""
import asyncio
import os
import random
import sqlite3
from datetime import date, datetime, timedelta
from uuid import uuid4

PG_URL = os.environ.get("PG_URL", "postgresql+asyncpg://aiu:aiu_dev@localhost:5433/aiu")
os.environ["DATABASE_URL"] = PG_URL

from sqlalchemy import select, text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from models.advisor import AdvisorAssignment  # noqa: E402
from models.ai_models import Notification  # noqa: E402
from models.enrollment import Enrollment, Grade, Waitlist  # noqa: E402
from models.financial import FinancialAccount, FinancialTransaction, Scholarship  # noqa: E402
from models.petitions import Petition  # noqa: E402
from models.student import Student  # noqa: E402

SQLITE_DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "aiu.db")
rng = random.Random(2026)

# ---------------- calendar (PG semester ids are chronological) ----------------
MAINS = [1, 2, 4, 5, 7, 8, 10, 11, 13, 14, 16, 17]          # Fall/Spring 2020-2026
SUMMERS = {2: 3, 5: 6, 8: 9, 11: 12, 14: 15, 17: 18}         # follows that Spring
GRADED_THROUGH = 17                                          # Summer 2026 = in progress
ENTRY_SEMESTER = {21: 4, 22: 7, 23: 10, 24: 13, 25: 16}      # Fall of entry year
SEM_DATES = {}                                               # filled from DB

COHORTS = {  # (major_code, entry_yy) -> count   (total = 400)
    ("AIS", 25): 55, ("AIS", 24): 50, ("AIS", 23): 45, ("AIS", 22): 40, ("AIS", 21): 30,
    ("AIE", 25): 40, ("AIE", 24): 38, ("AIE", 23): 36, ("AIE", 22): 34, ("AIE", 21): 32,
}
MAJOR_ID = {"AIS": 1, "AIE": 3}
PROGRAM_ID = {"AIS": 1, "AIE": 2}
DURATION = {"AIS": 4, "AIE": 5}
IMPROVE_CAP = {"AIS": 9, "AIE": 12}
DEMO_HASH = "$2b$12$Q1/N2pwzP3PtmkXts6vdU.XDBQJyP1eOzfjJKbPsLLuHlBHwTqFo6"  # same demo pwd as before

# grade ladder: (letter, points, typical %)
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


def sample_grade(mu, course_level):
    sigma = 0.55 + max(0.0, (3.2 - mu)) * 0.28
    s = rng.gauss(mu - (0.15 if course_level >= 3 else 0.0) - (0.10 if course_level >= 4 else 0.0), sigma)
    if s < 0.8:
        return ("F", 0.0, rng.randint(25, 49))
    best = min(LETTERS[1:], key=lambda L: abs(L[1] - s))  # A+ reserved
    if best[0] == "A" and s > 4.05 and rng.random() < 0.5:
        best = LETTERS[0]
    return (best[0], best[1], min(99, best[2] + rng.randint(-2, 2)))


def cap_letter(letter, points, cap_points=3.3):
    if points <= cap_points:
        return letter, points
    return "B+", cap_points  # §10.1 — retake of a failed course caps at B+


class Sim:
    """One student's life through the rules."""

    def __init__(self, sid, code, major, entry_yy, archetype, mu, flags):
        self.sid, self.code, self.major, self.yy = sid, code, major, entry_yy
        self.archetype, self.mu, self.flags = archetype, mu, flags
        self.math0 = flags.get("math0", rng.random() < 0.88)
        self.cum_pts = 0.0
        self.cum_cr = 0
        self.passed = {}            # course -> best effective points
        self.failed_open = []       # failed courses awaiting retake
        self.improve_credits = 0
        self.warn = 0
        self.severe = 0
        self.dismissed_at = None
        self.graduated_at = None
        self.frozen = set(flags.get("freeze_sems", ()))
        self.enrollments = []       # dicts
        self.grades = []
        self.mains_done = 0
        self.queue = []             # plan items: ("C", code) or ("E", group)
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
        """Mirror of services.standing.evaluate_semester (kept in lockstep)."""
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


async def main():
    engine = create_async_engine(PG_URL, echo=False)

    # ---------------- load catalog from PG ----------------
    async with engine.connect() as conn:
        sem_rows = (await conn.execute(text(
            "SELECT semester_id, code, type, start_date, end_date FROM semesters"))).all()
        for sid_, code_, type_, sd, ed in sem_rows:
            SEM_DATES[sid_] = {"code": code_, "type": type_, "start": sd, "end": ed}
        course_rows = (await conn.execute(text(
            "SELECT code, credits, name FROM courses"))).all()
        credits = {c: cr for c, cr, _ in course_rows}
        sec_rows = (await conn.execute(text(
            "SELECT section_id, course_code, semester_id, capacity FROM sections"))).all()
        prereq_rows = (await conn.execute(text(
            "SELECT course_code, prerequisite_course_code FROM prerequisites"))).all()
        rgc = (await conn.execute(text(
            "SELECT major_code, group_name, course_code, required_year, required_semester "
            "FROM requirement_group_courses WHERE major_code IN ('AIS','AIE')"))).all()

    offered = {}
    for sec_id, ccode, sem_id, capn in sec_rows:
        offered.setdefault((ccode, sem_id), []).append({"id": sec_id, "cap": capn, "n": 0})
    prereqs = {}
    for c, p in prereq_rows:
        prereqs.setdefault(c, []).append(p)

    plans = {}   # major -> ordered [("C", code) | ("E", group)] by (year, sem)
    baskets = {}  # (major, group) -> [codes]
    for major in ("AIS", "AIE"):
        items = []
        seen_groups = set()
        rows = sorted([r for r in rgc if r[0] == major], key=lambda r: (r[3] or 9, r[4] or 9, r[2]))
        for _, group, code_, _, _ in rows:
            if group.endswith("Required"):
                items.append(("C", code_))
            else:
                baskets.setdefault((major, group), []).append(code_)
                if group not in seen_groups:
                    seen_groups.add(group)
                    items.append(("E", group))
        plans[major] = items

    # demographic bundles from the old DB (real, reused — nothing invented)
    src = sqlite3.connect(SQLITE_DB)
    bundles = src.execute(
        "SELECT full_name, gender, nationality, city, home_address, postal_code, "
        "emergency_contact_name, emergency_relationship, emergency_phone, emergency_email, "
        "phone, school_id FROM students WHERE full_name IS NOT NULL").fetchall()
    src.close()
    rng.shuffle(bundles)

    # ---------------- simulate every student ----------------
    sims, students_rows = [], []
    eid = gid = 0
    sid = 0
    used_names = set()

    for (major, yy), count in COHORTS.items():
        serial_base = 1 if major == "AIS" else 5001
        for i in range(count):
            sid += 1
            serial = serial_base + i
            # keep the two muscle-memory demo codes alive in the AIS freshman cohort
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
                arch, mu = "summer_recovery", 2.15
                flags["takes_summer"] = True
            elif i == 3 and yy <= 23:
                arch, mu = "freeze", 2.7
                entry = ENTRY_SEMESTER[yy]
                third_main = MAINS[MAINS.index(entry) + 2]
                flags["freeze_sems"] = {third_main}
            elif i in (4, 5):
                arch, mu = "fast_track", 3.35
                flags["takes_summer"] = True
            elif i == 6:
                arch, mu = "scholar", 3.95
            elif i == 7 and yy <= 23:
                arch, mu = "improver", 2.85
                flags["improver"] = True
            if rng.random() < 0.12:
                flags["takes_summer"] = True
            if major == "AIS" and yy == 25 and serial in (45, 103):
                flags["takes_summer"] = True  # demo students have current courses

            s = Sim(sid, code, major, yy, arch, mu, flags)
            s.queue = list(plans[major])
            sims.append(s)

    sem_order = sorted(SEM_DATES)
    for s in sims:
        entry = ENTRY_SEMESTER[s.yy]
        elect_taken = set()
        for sem_id in [x for x in sem_order if x >= entry and x <= 18]:
            info = SEM_DATES[sem_id]
            is_summer = (info["type"] or "").lower() == "summer"
            if s.dismissed_at or s.graduated_at:
                break
            if sem_id in s.frozen:
                continue
            if is_summer and not (
                s.flags.get("takes_summer") or s.warn > 0 or
                (len([q for q in s.queue if q[0] == "C"]) <= 2 and s.mains_done >= 6)
            ):
                continue

            slot = s.mains_done + 1
            limit = s.limit_for(slot, is_summer)
            target = limit if s.archetype == "fast_track" else min(limit, 17)
            if is_summer:
                target = min(limit, rng.choice((3, 6, 6, 9)))

            chosen = []  # (course, is_retake, is_improvement, prev_idx)
            load = 0

            def can_take(c):
                if (c, sem_id) not in offered:
                    return False
                return all(s.passed.get(p, 0) >= 1.0 for p in prereqs.get(c, ()))

            for c in list(s.failed_open):  # retakes first
                if load >= target:
                    break
                if can_take(c) and credits.get(c, 3) + load <= limit:
                    chosen.append((c, True, False))
                    load += credits.get(c, 3)
                    s.failed_open.remove(c)
            for item in list(s.queue):
                if load >= target:
                    break
                if item[0] == "C":
                    c = item[1]
                    if c in s.taken_ever or not can_take(c) or credits.get(c, 3) + load > limit:
                        continue
                    chosen.append((c, False, False))
                    load += credits.get(c, 3)
                    s.queue.remove(item)
                else:
                    opts = [c for c in baskets.get((s.major, item[1]), ())
                            if c not in s.taken_ever and can_take(c) and credits.get(c, 3) + load <= limit]
                    if not opts:
                        continue
                    c = rng.choice(opts)
                    chosen.append((c, False, False))
                    load += credits.get(c, 3)
                    s.queue.remove(item)
                    elect_taken.add(item[1])
            # improvement retakes (within the 9/12-CH cap) when room remains
            if s.flags.get("improver") and not is_summer and slot >= 5:
                for c, pts in sorted(s.passed.items(), key=lambda kv: kv[1]):
                    cr = credits.get(c, 3)
                    if pts > 2.3 or load + cr > min(limit, target + 3):
                        continue
                    if s.improve_credits + cr > IMPROVE_CAP[s.major]:
                        break
                    if (c, sem_id) in offered and not any(x[0] == c for x in chosen):
                        chosen.append((c, False, True))
                        load += cr
                        s.improve_credits += cr

            if not chosen:
                if not is_summer:
                    s.mains_done += 1  # an empty (all-deferred) term still passes
                continue

            for c, is_retake, is_improve in chosen:
                eid += 1
                sec = min(offered[(c, sem_id)], key=lambda x: x["n"])
                sec["n"] += 1
                attempt = 2 if (is_retake or is_improve) else 1
                graded = sem_id <= GRADED_THROUGH
                enr = {
                    "enrollment_id": eid, "student_id": s.sid, "section_id": sec["id"],
                    "status": "Enrolled", "attempt_number": attempt,
                    "is_retake": is_retake or is_improve,
                    "enrollment_date": datetime.combine(info["start"], datetime.min.time()) - timedelta(days=rng.randint(5, 20)),
                    "drop_date": None, "withdrawal_date": None,
                }
                s.taken_ever.add(c)
                if not graded:
                    s.enrollments.append(enr)
                    continue

                if rng.random() < 0.015 and not is_retake:  # rare withdrawal
                    enr["status"] = "Withdrawn"
                    enr["withdrawal_date"] = datetime.combine(info["start"], datetime.min.time()) + timedelta(days=30)
                    s.enrollments.append(enr)
                    gid += 1
                    s.grades.append({"grade_id": gid, "enrollment_id": eid, "grade_letter": "W",
                                     "grade_points": None, "percentage": None,
                                     "counts_in_gpa": False, "is_improvement": False,
                                     "grade_date": datetime.combine(info["end"], datetime.min.time())})
                    if ("C", c) in plans[s.major]:
                        if c not in s.passed and ("C", c) not in s.queue:
                            s.queue.insert(0, ("C", c))
                    else:  # withdrawn elective — put its basket back in the plan
                        for (mj, group), codes_ in baskets.items():
                            if mj == s.major and c in codes_:
                                s.queue.insert(0, ("E", group))
                                break
                    s.taken_ever.discard(c)
                    continue

                boost = 0.35 if is_retake else (0.5 if is_improve else 0.0)
                if is_summer and s.archetype == "summer_recovery":
                    boost += 1.0
                level = int(c[3]) if len(c) > 3 and c[3].isdigit() else 1
                letter, pts, pct = sample_grade(s.mu + boost, level)
                if is_retake:
                    letter, pts = cap_letter(letter, pts)
                if is_improve and pts <= s.passed.get(c, 0):
                    letter, pts = "B+", max(3.3, s.passed.get(c, 0))  # improvements improve
                    pct = 85

                enr["status"] = "Failed" if letter == "F" else "Satisfied"
                s.enrollments.append(enr)
                gid += 1
                s.grades.append({"grade_id": gid, "enrollment_id": eid, "grade_letter": letter,
                                 "grade_points": pts, "percentage": float(pct),
                                 "counts_in_gpa": True, "is_improvement": is_improve,
                                 "grade_date": datetime.combine(info["end"], datetime.min.time())})

                cr = credits.get(c, 3)
                if (is_retake or is_improve) and c in [g for g in s.passed] or is_retake:
                    # supersede the previous counted attempt (latest counts)
                    for g_old in s.grades[:-1]:
                        enr_old = next(e for e in s.enrollments if e["enrollment_id"] == g_old["enrollment_id"])
                        if enr_old["student_id"] != s.sid or not g_old["counts_in_gpa"]:
                            continue
                        old_sec = g_old.get("_course")
                        if old_sec == c:
                            g_old["counts_in_gpa"] = False
                            if g_old["grade_points"] is not None:
                                s.cum_pts -= g_old["grade_points"] * cr
                                s.cum_cr -= cr
                s.grades[-1]["_course"] = c
                if letter == "F":
                    s.failed_open.append(c)
                else:
                    s.passed[c] = max(s.passed.get(c, 0), pts)
                s.cum_pts += pts * cr
                s.cum_cr += cr

            if sem_id <= GRADED_THROUGH:
                if not is_summer:
                    s.mains_done += 1
                s.standing_step(s.mains_done, is_summer)
                if not s.queue and not s.failed_open and sem_id <= GRADED_THROUGH:
                    s.graduated_at = sem_id

        # ----- student master row -----
        b = bundles[(s.sid - 1) % len(bundles)]
        name = b[0]
        if name in used_names:
            name = f"{name.split()[0]} {rng.choice(bundles)[0].split()[-1]}"
        used_names.add(name)
        first = "".join(ch for ch in name.split()[0].lower() if ch.isalpha())
        last = "".join(ch for ch in name.split()[-1].lower() if ch.isalpha())
        email = f"{first}.{last}.{s.code}@aiu.edu.eg"
        entry_date = SEM_DATES[ENTRY_SEMESTER[s.yy]]["start"]
        if s.dismissed_at:
            status = "Dismissed"
        elif s.graduated_at:
            status = "Graduated"
        elif s.warn > 0:
            status = "Probation"
        else:
            status = "Active"
        duration = DURATION[s.major]
        level = duration if s.graduated_at else max(1, min(duration, (s.mains_done + 1) // 2))
        grad = (SEM_DATES[s.graduated_at]["end"] if s.graduated_at
                else date(2000 + s.yy + duration, 6, 30))
        students_rows.append({
            "student_id": s.sid, "student_code": s.code, "full_name": name, "email": email,
            "phone": b[10], "hashed_password": DEMO_HASH, "program_id": PROGRAM_ID[s.major],
            "major_id": MAJOR_ID[s.major], "level": level, "status": status,
            "enrollment_date": entry_date, "expected_graduation": grad,
            "cgpa": s.cgpa, "math0_passed": s.math0,
            "created_at": datetime.combine(entry_date, datetime.min.time()),
            "date_of_birth": f"{2000 + s.yy - 18 - rng.randint(0, 1)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
            "gender": b[1], "nationality": b[2], "school_id": b[11],
            "home_address": b[4], "city": b[3], "postal_code": b[5],
            "emergency_contact_name": b[6], "emergency_relationship": b[7],
            "emergency_phone": b[8], "emergency_email": b[9],
        })

    for g in (g for s in sims for g in s.grades):
        g.pop("_course", None)

    # ---------------- bulk insert ----------------
    all_enr = [e for s in sims for e in s.enrollments]
    all_grades = [g for s in sims for g in s.grades]
    async with engine.begin() as conn:
        for tbl in ("waitlist", "notifications", "advisor_assignments", "petitions",
                    "financial_transactions", "scholarships", "financial_accounts",
                    "academic_standing", "grades", "enrollments", "students"):
            await conn.execute(text(f"DELETE FROM {tbl}"))
        await conn.execute(Student.__table__.insert(), students_rows)
        for i in range(0, len(all_enr), 5000):
            await conn.execute(Enrollment.__table__.insert(), all_enr[i:i + 5000])
        for i in range(0, len(all_grades), 5000):
            await conn.execute(Grade.__table__.insert(), all_grades[i:i + 5000])
        # capacity never below what history shows
        await conn.execute(text(
            "UPDATE sections SET capacity = sub.n + 3 FROM ("
            " SELECT section_id, COUNT(*) AS n FROM enrollments GROUP BY section_id"
            ") sub WHERE sections.section_id = sub.section_id AND sections.capacity < sub.n"))
    print(f"students={len(students_rows)} enrollments={len(all_enr)} grades={len(all_grades)}")

    # ---------------- authoritative standing via the PRODUCTION engine ----------------
    from core.database import AsyncSessionLocal
    from services.standing import replay_student_standing
    async with AsyncSessionLocal() as db:
        for n, s in enumerate(sims, 1):
            await replay_student_standing(s.sid, db)
            if n % 50 == 0:
                await db.commit()
                print(f"  standing replayed {n}/{len(sims)}")
        await db.commit()

    # ---------------- satellites ----------------
    today = datetime(2026, 6, 11, 9, 0)
    assigns, notifs, accounts, txns, schols, petitions, waitl = [], [], [], [], [], [], []
    async with engine.connect() as conn:
        st_rows = (await conn.execute(text(
            "SELECT student_id, student_code, full_name, cgpa, status FROM students"))).all()
        cur_enr = (await conn.execute(text(
            "SELECT e.student_id, SUM(c.credits) FROM enrollments e "
            "JOIN sections sec ON sec.section_id=e.section_id "
            "JOIN courses c ON c.code=sec.course_code "
            "WHERE e.status='Enrolled' AND sec.semester_id=18 GROUP BY e.student_id"))).all()
    summer_credits = {a: int(b) for a, b in cur_enr}

    aid = 0
    for sid_, code_, name_, cgpa_, status_ in st_rows:
        aid += 1
        advisor_id = (sid_ % 40) + 1
        assigns.append({"advisor_assignment_id": aid, "advisor_id": advisor_id,
                        "advisor_name": None, "student_code": code_, "student_name": name_,
                        "assigned_date": date(2000 + int(code_[:2]), 9, 15),
                        "end_date": None, "is_active": True})
        notifs.append({"student_id": sid_, "type": "academic", "subject": "Spring 2026 grades posted",
                       "message": "Your Spring 2026 grades are now available in Academic Records.",
                       "status": "Unread", "created_at": datetime(2026, 6, 5, 10, 0),
                       "sent_at": datetime(2026, 6, 5, 10, 0)})
        if status_ in ("Active", "Probation"):
            notifs.append({"student_id": sid_, "type": "registration",
                           "subject": "Fall 2026 registration is open",
                           "message": "Plan your Fall 2026 schedule — registration closes September 19.",
                           "status": "Unread", "created_at": datetime(2026, 6, 1, 9, 0),
                           "sent_at": datetime(2026, 6, 1, 9, 0)})

        cr = summer_credits.get(sid_, 0)
        tuition = cr * 2750
        transport = 13000 if cr else 0
        eligible = (cgpa_ or 0) >= 3.9 and tuition > 0
        schol = tuition if eligible else 0
        if cr:
            bal = tuition + transport - schol
            accounts.append({"id": str(uuid4()), "student_id": sid_, "semester_code": "Summer 2026",
                             "term_credits": cr, "tuition_fee": tuition, "transportation_fee": transport,
                             "fines": 0, "total_charges": tuition + transport,
                             "scholarship_credit": schol, "payments_made": 0,
                             "current_balance": bal, "payment_due_date": "2026-07-10",
                             "payment_status": "Paid" if bal <= 0 else "Due",
                             "currency": "EGP", "last_updated": today})
            txns.append({"id": str(uuid4()), "student_id": sid_, "transaction_ref": f"CHG-{sid_}-SU26",
                         "semester_code": "Summer 2026", "date": "2026-06-05", "type": "charge",
                         "category": "Tuition", "description": f"Summer charge ({cr} credits)",
                         "amount": tuition, "currency": "EGP", "status": "Posted", "reference": ""})
            if eligible:
                ref = f"SCH-{sid_}-01"
                schols.append({"id": str(uuid4()), "student_id": sid_, "scholarship_ref": ref,
                               "semester_code": "Summer 2026", "scholarship_type": "Academic Excellence Scholarship",
                               "percentage": 100, "amount": schol, "status": "Active",
                               "criteria_basis": "CGPA", "cgpa_at_award": cgpa_,
                               "notes": "Rule: CGPA >= 3.9 -> 100% tuition"})
        elif status_ in ("Active", "Probation", "Graduated"):
            # last billed term settled (real history, zero balance)
            accounts.append({"id": str(uuid4()), "student_id": sid_, "semester_code": "Spring 2026",
                             "term_credits": 0, "tuition_fee": 0, "transportation_fee": 0,
                             "fines": 0, "total_charges": 0, "scholarship_credit": 0,
                             "payments_made": 0, "current_balance": 0,
                             "payment_due_date": None, "payment_status": "Paid",
                             "currency": "EGP", "last_updated": today})

    # petitions that match the generated histories
    freeze_sims = [s for s in sims if s.frozen][:3]
    for s in freeze_sims:
        sem = SEM_DATES[next(iter(s.frozen))]["code"]
        petitions.append({"id": str(uuid4()), "student_id": s.sid, "type": "freeze",
                          "status": "approved", "subject": f"Semester freeze — {sem}",
                          "body": "Medical circumstances required a freeze.",
                          "freeze_semester_code": sem, "effect_applied": True,
                          "submitted_at": datetime(2000 + s.yy + 1, 8, 20, 10, 0),
                          "decided_at": datetime(2000 + s.yy + 1, 8, 25, 10, 0),
                          "reviewer_id": "registrar", "reviewer_role": "registrar",
                          "decision_comment": "Approved per §15 — within freeze caps."})
    dism = [s for s in sims if s.dismissed_at][:1]
    for s in dism:
        petitions.append({"id": str(uuid4()), "student_id": s.sid, "type": "final_chance",
                          "status": "submitted", "subject": "Final chance request",
                          "body": "Requesting a final-chance semester to complete my degree.",
                          "freeze_semester_code": None, "effect_applied": False,
                          "submitted_at": today, "decided_at": None,
                          "reviewer_id": None, "reviewer_role": None, "decision_comment": None})

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
        for tname, pk in (("students", "student_id"), ("enrollments", "enrollment_id"),
                          ("grades", "grade_id"), ("notifications", "notification_id"),
                          ("advisor_assignments", "advisor_assignment_id"),
                          ("academic_standing", "academic_standing_id"),
                          ("waitlist", "waitlist_id")):
            await conn.execute(text(
                f"SELECT setval(pg_get_serial_sequence('{tname}', '{pk}'), "
                f"COALESCE((SELECT MAX({pk}) FROM {tname}), 1))"))

    # ---------------- verification report ----------------
    async with engine.connect() as conn:
        def q(sql):
            return conn.execute(text(sql))
        print("\n--- verification ---")
        for label, sql in [
            ("status mix", "SELECT status, COUNT(*) FROM students GROUP BY status ORDER BY 2 DESC"),
            ("cohort mix", "SELECT LEFT(student_code,2), m.code, COUNT(*) FROM students s JOIN majors m ON m.major_id=s.major_id GROUP BY 1,2 ORDER BY 1 DESC"),
            ("grade letters", "SELECT grade_letter, COUNT(*) FROM grades GROUP BY 1 ORDER BY 2 DESC"),
            ("prereq violations", """SELECT COUNT(*) FROM enrollments e
                JOIN sections sec ON sec.section_id=e.section_id
                JOIN prerequisites p ON p.course_code=sec.course_code
                WHERE NOT EXISTS (
                  SELECT 1 FROM enrollments e2
                  JOIN sections s2 ON s2.section_id=e2.section_id
                  JOIN grades g2 ON g2.enrollment_id=e2.enrollment_id
                  WHERE e2.student_id=e.student_id AND s2.course_code=p.prerequisite_course_code
                    AND s2.semester_id < sec.semester_id AND g2.grade_points >= 1.0)"""),
            ("double-counted attempts", """SELECT COUNT(*) FROM (
                SELECT e.student_id, sec.course_code FROM enrollments e
                JOIN sections sec ON sec.section_id=e.section_id
                JOIN grades g ON g.enrollment_id=e.enrollment_id
                WHERE g.counts_in_gpa AND g.grade_letter NOT IN ('W','I','S','U')
                GROUP BY 1,2 HAVING COUNT(*)>1) x"""),
            ("over-capacity sections", """SELECT COUNT(*) FROM (
                SELECT sec.section_id, sec.capacity, COUNT(*) n FROM enrollments e
                JOIN sections sec ON sec.section_id=e.section_id
                WHERE e.status != 'Dropped' GROUP BY 1,2 HAVING COUNT(*) > sec.capacity) x"""),
            ("cgpa drift vs standing", """SELECT COUNT(*) FROM students s
                JOIN academic_standing a ON a.student_code=s.student_code
                WHERE a.semester_id=(SELECT MAX(a2.semester_id) FROM academic_standing a2
                                     WHERE a2.student_code=s.student_code)
                AND ABS(COALESCE(a.cgpa,0)-COALESCE(s.cgpa,0)) > 0.001"""),
            ("summer 2026 in progress", "SELECT COUNT(DISTINCT e.student_id) FROM enrollments e JOIN sections s ON s.section_id=e.section_id WHERE s.semester_id=18 AND e.status='Enrolled'"),
        ]:
            rows = (await q(sql)).all()
            print(f"{label}: {rows if len(rows) > 1 else rows[0]}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
