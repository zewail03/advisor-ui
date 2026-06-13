"""Seed financial accounts from REAL student data (fast bulk version).

Every value is derived, not invented:
  * term_credits   = sum of credits of the student's in-progress (Enrolled) courses
  * tuition_fee    = term_credits x policy(finance.tuition_per_credit)
  * transport_fee  = flat policy(finance.transport_fee) (only if registered this term)
  * scholarship    = 100% tuition merit award when CGPA >= policy(finance.scholarship_cgpa)
  * balance        = charges - scholarship  (no payment records exist -> unpaid)

Fee values come from the policy engine (`finance.*` keys in policy_config,
falling back to the code defaults in services.policy.DEFAULTS). Run:
    python -m scripts.seed_financial
"""
import os
import sqlite3
from datetime import datetime, timedelta
from uuid import uuid4

from services.policy import DEFAULTS

CURRENT_TERM = "Spring 2026"
CURRENCY = "EGP"
# ~1 month out from when the seed runs, so the bill reads "Due" (not overdue)
DUE_DATE = (datetime.utcnow().date() + timedelta(days=30)).isoformat()
CHARGE_DATE = "2025-12-26"
SCHOLARSHIP_DATE = "2026-01-05"

DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), "aiu.db")


def _policy(cur: sqlite3.Cursor, key: str) -> float:
    """Live rule value: policy_config override if present, else code default."""
    raw = DEFAULTS[key]["default"]
    try:
        row = cur.execute(
            "SELECT value FROM policy_config WHERE key = ?", (key,)
        ).fetchone()
        if row is not None:
            raw = row[0]
    except sqlite3.OperationalError:
        pass  # table not created yet (first boot) -> use default
    return int(float(raw)) if DEFAULTS[key]["type"] == "int" else float(raw)


def seed() -> None:
    con = sqlite3.connect(DB, timeout=30)
    con.execute("PRAGMA busy_timeout=30000")
    cur = con.cursor()

    tuition_per_credit = _policy(cur, "finance.tuition_per_credit")
    transport_fee = _policy(cur, "finance.transport_fee")
    scholarship_cgpa = _policy(cur, "finance.scholarship_cgpa")

    # idempotent
    cur.execute("DELETE FROM financial_transactions")
    cur.execute("DELETE FROM scholarships")
    cur.execute("DELETE FROM financial_accounts")

    # real in-progress credits per student, in one pass
    credits_by_student = dict(cur.execute("""
        SELECT e.student_id, COALESCE(SUM(c.credits), 0)
        FROM enrollments e
        JOIN sections s ON e.section_id = s.section_id
        JOIN courses c ON s.course_code = c.code
        WHERE e.status = 'Enrolled'
        GROUP BY e.student_id
    """).fetchall())

    students = cur.execute("SELECT student_id, cgpa FROM students").fetchall()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")  # SQLAlchemy DateTime format

    accounts, txns, schols = [], [], []
    for sid, cgpa in students:
        cgpa = cgpa or 0.0
        credits = int(credits_by_student.get(sid, 0))
        tuition = credits * int(tuition_per_credit)
        transport = int(transport_fee) if credits > 0 else 0
        fines = 0
        total = tuition + transport + fines

        eligible = cgpa >= scholarship_cgpa and tuition > 0
        scholarship = tuition if eligible else 0
        payments = 0
        balance = total - scholarship - payments
        status = "Paid" if balance <= 0 else "Due"

        accounts.append((str(uuid4()), sid, CURRENT_TERM, credits, tuition, transport,
                         fines, total, scholarship, payments, balance, DUE_DATE,
                         status, CURRENCY, now))

        if credits > 0:
            txns.append((str(uuid4()), sid, f"CHG-{sid}-TUI", CURRENT_TERM, CHARGE_DATE,
                         "charge", "Tuition", f"Semester Charge ({credits} credits)",
                         tuition, CURRENCY, "Posted", ""))
            txns.append((str(uuid4()), sid, f"CHG-{sid}-TRA", CURRENT_TERM, CHARGE_DATE,
                         "charge", "Transportation", "Transportation Fee",
                         transport, CURRENCY, "Posted", ""))

        if eligible:
            ref = f"SCH-{sid}-01"
            schols.append((str(uuid4()), sid, ref, CURRENT_TERM,
                           "Academic Excellence Scholarship", 100, scholarship,
                           "Active", "CGPA", cgpa,
                           f"Rule: CGPA >= {scholarship_cgpa} -> 100% tuition"))
            txns.append((str(uuid4()), sid, ref + "-TXN", CURRENT_TERM, SCHOLARSHIP_DATE,
                         "scholarship", "Scholarship", "Scholarship Applied",
                         scholarship, CURRENCY, "Posted", ref))

    cur.executemany(
        "INSERT INTO financial_accounts (id, student_id, semester_code, term_credits, "
        "tuition_fee, transportation_fee, fines, total_charges, scholarship_credit, "
        "payments_made, current_balance, payment_due_date, payment_status, currency, "
        "last_updated) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", accounts)
    cur.executemany(
        "INSERT INTO financial_transactions (id, student_id, transaction_ref, "
        "semester_code, date, type, category, description, amount, currency, status, "
        "reference) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", txns)
    cur.executemany(
        "INSERT INTO scholarships (id, student_id, scholarship_ref, semester_code, "
        "scholarship_type, percentage, amount, status, criteria_basis, cgpa_at_award, "
        "notes) VALUES (?,?,?,?,?,?,?,?,?,?,?)", schols)

    con.commit()
    con.close()
    print(f"Seeded {len(accounts)} accounts, {len(txns)} transactions, "
          f"{len(schols)} scholarships across {len(students)} students.")


if __name__ == "__main__":
    seed()
