"""Full data-integrity audit of the AIU dataset.

Read-only. Runs a battery of checks and prints a report grouped by area, with a
[FAIL]/[WARN]/[INFO]/[OK] tag, a count, and up to a few sample offenders. The
checks most relevant to the ML early-warning model (grade<->points coherence,
counts_in_gpa correctness, the retake 'latest-counts' invariant, CGPA drift,
standing consistency, prerequisite ordering) are called out as model-critical.

  .\\venv\\Scripts\\python.exe -m scripts.audit_dataset
"""
import asyncio
import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://aiu:aiu_dev@localhost:5433/aiu")

from sqlalchemy import text  # noqa: E402

from core.database import engine  # noqa: E402
from models.enrollment import GRADE_POINTS  # noqa: E402

FAILS = WARNS = 0


def tag(sev: str, label: str, count: int, samples=None, note: str = ""):
    global FAILS, WARNS
    if sev == "FAIL" and count:
        FAILS += 1
        mark = "[FAIL]"
    elif sev == "WARN" and count:
        WARNS += 1
        mark = "[WARN]"
    elif count:
        mark = "[INFO]"
    else:
        mark = "[ OK ]"
    line = f"  {mark} {label}: {count}"
    if note:
        line += f"  — {note}"
    print(line)
    if count and samples:
        for s in samples[:6]:
            print(f"          · {s}")


async def scalar(c, sql, **p):
    return (await c.execute(text(sql), p)).scalar()


async def rows(c, sql, **p):
    return (await c.execute(text(sql), p)).all()


async def main():
    async with engine.connect() as c:
        # ---------------------------------------------------------------- #
        print("\n========== STUDENTS ==========")
        r = await rows(c, "SELECT student_code, COUNT(*) FROM students GROUP BY 1 HAVING COUNT(*)>1")
        tag("FAIL", "duplicate student_code", len(r), [f"{a} x{b}" for a, b in r])

        r = await rows(c, "SELECT LOWER(email), COUNT(*) FROM students GROUP BY 1 HAVING COUNT(*)>1")
        tag("FAIL", "duplicate email", len(r), [f"{a} x{b}" for a, b in r])

        r = await rows(c, "SELECT full_name, COUNT(*) FROM students GROUP BY 1 HAVING COUNT(*)>1")
        tag("WARN", "duplicate full_name (may be acceptable)", len(r), [f"{a} x{b}" for a, b in r])

        r = await rows(c, "SELECT phone, COUNT(*) FROM students WHERE phone IS NOT NULL GROUP BY 1 HAVING COUNT(*)>1")
        tag("WARN", "duplicate phone", len(r), [f"{a} x{b}" for a, b in r])

        n = await scalar(c, "SELECT COUNT(*) FROM students WHERE cgpa < 0 OR cgpa > 4")
        tag("FAIL", "cgpa out of [0,4]", n)

        n = await scalar(c, "SELECT COUNT(*) FROM students WHERE program_id IS NULL OR major_id IS NULL")
        tag("FAIL", "null program/major", n)

        n = await scalar(c, "SELECT COUNT(*) FROM students WHERE level < 1 OR level > 4")
        tag("WARN", "level out of [1,4]", n)

        r = await rows(c, "SELECT DISTINCT status FROM students ORDER BY 1")
        allowed = {"Active", "Probation", "Dismissed", "Graduated", "Suspended", "Frozen", "Withdrawn"}
        bad = [s[0] for s in r if s[0] not in allowed]
        tag("FAIL", "unexpected student.status value", len(bad), bad,
            note=f"present: {sorted(s[0] for s in r)}")

        n = await scalar(c, "SELECT COUNT(*) FROM students WHERE email NOT LIKE '%' || student_code || '%'")
        tag("WARN", "email does not embed student_code", n)

        n = await scalar(c, "SELECT COUNT(*) FROM students WHERE math0_passed IS NULL")
        tag("INFO", "math0_passed is NULL", n, note="treated as passed by the rules engine")

        # ---------------- model-critical: CGPA drift -------------------- #
        print("\n========== GPA / GRADE COHERENCE (model-critical) ==========")
        r = await rows(c, """
            WITH recomputed AS (
              SELECT e.student_id,
                     ROUND((SUM(g.grade_points*co.credits)/NULLIF(SUM(co.credits),0))::numeric, 3) AS cgpa
              FROM grades g
              JOIN enrollments e ON e.enrollment_id=g.enrollment_id
              JOIN sections se ON se.section_id=e.section_id
              JOIN courses co ON co.code=se.course_code
              WHERE g.counts_in_gpa=true AND g.grade_points IS NOT NULL
              GROUP BY e.student_id)
            SELECT s.student_code, s.cgpa, r.cgpa
            FROM students s JOIN recomputed r ON r.student_id=s.student_id
            WHERE ABS(COALESCE(s.cgpa,0)-COALESCE(r.cgpa,0)) > 0.01
        """)
        tag("FAIL", "student.cgpa != recomputed-from-grades", len(r),
            [f"{a}: stored {b} vs computed {d}" for a, b, d in r])

        # latest standing CGPA vs student CGPA
        r = await rows(c, """
            SELECT s.student_code, s.cgpa, a.cgpa
            FROM students s JOIN academic_standing a ON a.student_code=s.student_code
            WHERE a.semester_id=(SELECT MAX(a2.semester_id) FROM academic_standing a2
                                 WHERE a2.student_code=s.student_code)
              AND ABS(COALESCE(a.cgpa,0)-COALESCE(s.cgpa,0)) > 0.01
        """)
        tag("FAIL", "student.cgpa != latest academic_standing.cgpa", len(r),
            [f"{a}: student {b} vs standing {d}" for a, b, d in r])

        # grade_letter <-> grade_points coherence
        combos = await rows(c, "SELECT grade_letter, grade_points, counts_in_gpa, COUNT(*) FROM grades GROUP BY 1,2,3 ORDER BY 1,2,3")
        mism, present = [], []
        for letter, pts, counts, cnt in combos:
            present.append(f"{letter}/{pts}/{counts}:{cnt}")
            if letter in GRADE_POINTS:
                exp = GRADE_POINTS[letter]
                if exp is None:
                    if pts is not None:
                        mism.append(f"{letter} should have NULL points, has {pts} (x{cnt})")
                else:
                    if pts != exp:
                        mism.append(f"{letter} should be {exp} points, has {pts} (x{cnt})")
            elif letter == "P":
                pass  # pass/fail marker, points intentionally unused (counts_in_gpa=False)
            else:
                mism.append(f"unknown grade_letter {letter} (x{cnt})")
        tag("FAIL", "grade_letter <-> grade_points mismatch", len(mism), mism)
        print(f"          (letter/points/counts present: {', '.join(present)})")

        # counts_in_gpa coherence
        n = await scalar(c, "SELECT COUNT(*) FROM grades WHERE grade_letter IN ('W','I','S','U','P') AND counts_in_gpa=true")
        tag("FAIL", "non-graded letter (W/I/S/U/P) marked counts_in_gpa=true", n)

        n = await scalar(c, "SELECT COUNT(*) FROM grades WHERE counts_in_gpa=true AND grade_points IS NULL")
        tag("FAIL", "counts_in_gpa=true but grade_points is NULL", n)

        n = await scalar(c, "SELECT COUNT(*) FROM grades WHERE grade_points IS NOT NULL AND (grade_points<0 OR grade_points>4)")
        tag("FAIL", "grade_points out of [0,4]", n)

        n = await scalar(c, "SELECT COUNT(*) FROM grades WHERE percentage IS NOT NULL AND (percentage<0 OR percentage>100)")
        tag("FAIL", "percentage out of [0,100]", n)

        # THE retake invariant: at most one counted grade per (student, course)
        r = await rows(c, """
            SELECT s.student_code, se.course_code, COUNT(*) n
            FROM grades g
            JOIN enrollments e ON e.enrollment_id=g.enrollment_id
            JOIN students s ON s.student_id=e.student_id
            JOIN sections se ON se.section_id=e.section_id
            WHERE g.counts_in_gpa=true AND g.grade_points IS NOT NULL
            GROUP BY 1,2 HAVING COUNT(*)>1 ORDER BY n DESC
        """)
        tag("FAIL", "double-counted course (>1 counted grade per student+course)", len(r),
            [f"{a} {b} x{n}" for a, b, n in r],
            note="violates latest-counts; corrupts CGPA & the model")

        # ---------------------------------------------------------------- #
        print("\n========== ENROLLMENTS / GRADES LINKAGE ==========")
        n = await scalar(c, """SELECT COUNT(*) FROM enrollments e
                               LEFT JOIN sections se ON se.section_id=e.section_id WHERE se.section_id IS NULL""")
        tag("FAIL", "enrollment -> missing section", n)
        n = await scalar(c, """SELECT COUNT(*) FROM enrollments e
                               LEFT JOIN students s ON s.student_id=e.student_id WHERE s.student_id IS NULL""")
        tag("FAIL", "enrollment -> missing student", n)
        n = await scalar(c, """SELECT COUNT(*) FROM grades g
                               LEFT JOIN enrollments e ON e.enrollment_id=g.enrollment_id WHERE e.enrollment_id IS NULL""")
        tag("FAIL", "grade -> missing enrollment", n)
        r = await rows(c, "SELECT enrollment_id, COUNT(*) FROM grades GROUP BY 1 HAVING COUNT(*)>1")
        tag("FAIL", "multiple grades for one enrollment", len(r), [f"enr {a} x{b}" for a, b in r])

        r = await rows(c, """
            SELECT se.semester_id, sm.code, COUNT(*)
            FROM enrollments e
            JOIN sections se ON se.section_id=e.section_id
            JOIN semesters sm ON sm.semester_id=se.semester_id
            LEFT JOIN grades g ON g.enrollment_id=e.enrollment_id
            WHERE g.grade_id IS NULL
            GROUP BY 1,2 ORDER BY 1
        """)
        tag("INFO", "ungraded enrollments (expected: current in-progress term only)",
            sum(x[2] for x in r), [f"{b} (sem {a}): {n}" for a, b, n in r])

        r = await rows(c, "SELECT DISTINCT status FROM enrollments ORDER BY 1")
        allowed_e = {"Enrolled", "Dropped", "Withdrawn", "Satisfied", "Failed", "Completed"}
        bad = [s[0] for s in r if s[0] not in allowed_e]
        tag("WARN", "unexpected enrollment.status", len(bad), bad, note=f"present: {[s[0] for s in r]}")

        # enrollment.status vs the grade it carries
        n = await scalar(c, """
            SELECT COUNT(*) FROM enrollments e JOIN grades g ON g.enrollment_id=e.enrollment_id
            WHERE e.status='Failed' AND (g.grade_letter NOT IN ('F','FW'))
        """)
        tag("WARN", "status=Failed but grade is not F/FW", n)
        n = await scalar(c, """
            SELECT COUNT(*) FROM enrollments e JOIN grades g ON g.enrollment_id=e.enrollment_id
            WHERE e.status='Satisfied' AND g.grade_letter IN ('F','FW')
        """)
        tag("WARN", "status=Satisfied but grade is F/FW", n)

        # is_retake coherence: flagged retake should have an earlier attempt of same course
        r = await rows(c, """
            SELECT s.student_code, se.course_code
            FROM enrollments e
            JOIN students s ON s.student_id=e.student_id
            JOIN sections se ON se.section_id=e.section_id
            WHERE e.is_retake=true AND NOT EXISTS (
              SELECT 1 FROM enrollments e2 JOIN sections se2 ON se2.section_id=e2.section_id
              WHERE e2.student_id=e.student_id AND se2.course_code=se.course_code
                AND se2.semester_id < se.semester_id)
        """)
        tag("WARN", "is_retake=true with no earlier attempt of the course", len(r),
            [f"{a} {b}" for a, b in r])

        # ---------------------------------------------------------------- #
        print("\n========== ACADEMIC STANDING ==========")
        r = await rows(c, "SELECT student_code, semester_id, COUNT(*) FROM academic_standing GROUP BY 1,2 HAVING COUNT(*)>1")
        tag("FAIL", "duplicate standing row (student, semester)", len(r), [f"{a}/{b} x{n}" for a, b, n in r])
        n = await scalar(c, """SELECT COUNT(*) FROM academic_standing a
                               LEFT JOIN students s ON s.student_code=a.student_code WHERE s.student_code IS NULL""")
        tag("FAIL", "standing -> missing student", n)
        r = await rows(c, "SELECT DISTINCT status FROM academic_standing ORDER BY 1")
        allowed_s = {"Good Standing", "Probation", "Dismissed", "Warning", "Final Chance"}
        bad = [s[0] for s in r if s[0] not in allowed_s]
        tag("WARN", "unexpected standing.status", len(bad), bad, note=f"present: {[s[0] for s in r]}")
        n = await scalar(c, "SELECT COUNT(*) FROM academic_standing WHERE warning_count<0 OR warning_count>4")
        tag("WARN", "warning_count out of [0,4]", n)
        # a dismissed student should not have a later good-standing main row
        r = await rows(c, """
            SELECT a.student_code FROM academic_standing a
            WHERE a.status='Dismissed' AND EXISTS (
              SELECT 1 FROM academic_standing a2 WHERE a2.student_code=a.student_code
                AND a2.semester_id>a.semester_id AND a2.status<>'Dismissed')
            GROUP BY 1
        """)
        tag("WARN", "standing recovers after a Dismissed row", len(r), [x[0] for x in r])

        # ---------------------------------------------------------------- #
        print("\n========== COURSES / SECTIONS / PREREQS ==========")
        r = await rows(c, "SELECT code, COUNT(*) FROM courses GROUP BY 1 HAVING COUNT(*)>1")
        tag("FAIL", "duplicate course code", len(r), [f"{a} x{b}" for a, b in r])
        r = await rows(c, "SELECT code, credits FROM courses WHERE credits<=0 ORDER BY 1")
        tag("INFO", "courses with 0 credits", len(r), [f"{a} ({b}cr)" for a, b in r],
            note="intentional for 0-CH pass/fail (e.g. LAN022, PSC101)")
        n = await scalar(c, """SELECT COUNT(*) FROM sections se
                               LEFT JOIN courses co ON co.code=se.course_code WHERE co.code IS NULL""")
        tag("FAIL", "section -> missing course", n)
        n = await scalar(c, """SELECT COUNT(*) FROM sections se
                               LEFT JOIN semesters sm ON sm.semester_id=se.semester_id WHERE sm.semester_id IS NULL""")
        tag("FAIL", "section -> missing semester", n)
        n = await scalar(c, """SELECT COUNT(*) FROM prerequisites p
                               LEFT JOIN courses c1 ON c1.code=p.course_code WHERE c1.code IS NULL""")
        tag("FAIL", "prerequisite.course_code missing from courses", n)
        n = await scalar(c, """SELECT COUNT(*) FROM prerequisites p
                               LEFT JOIN courses c2 ON c2.code=p.prerequisite_course_code WHERE c2.code IS NULL""")
        tag("FAIL", "prerequisite_course_code missing from courses", n)
        n = await scalar(c, "SELECT COUNT(*) FROM prerequisites WHERE course_code=prerequisite_course_code")
        tag("FAIL", "self-referential prerequisite", n)
        r = await rows(c, "SELECT course_code, prerequisite_course_code, COUNT(*) FROM prerequisites GROUP BY 1,2 HAVING COUNT(*)>1")
        tag("FAIL", "duplicate prerequisite pair", len(r), [f"{a}<-{b} x{n}" for a, b, n in r])

        # prerequisite ORDERING violations: took a course before passing its prereq
        r = await rows(c, """
            SELECT s.student_code, se.course_code, p.prerequisite_course_code
            FROM enrollments e
            JOIN students s ON s.student_id=e.student_id
            JOIN sections se ON se.section_id=e.section_id
            JOIN prerequisites p ON p.course_code=se.course_code
            WHERE NOT EXISTS (
              SELECT 1 FROM enrollments e2
              JOIN sections se2 ON se2.section_id=e2.section_id
              JOIN grades g2 ON g2.enrollment_id=e2.enrollment_id
              WHERE e2.student_id=e.student_id
                AND se2.course_code=p.prerequisite_course_code
                AND se2.semester_id < se.semester_id
                AND g2.grade_points >= 1.0)
        """)
        tag("FAIL", "prerequisite taken-before-passed violation", len(r),
            [f"{a}: {b} before passing {p}" for a, b, p in r])

        # ---------------------------------------------------------------- #
        print("\n========== SATELLITES ==========")
        r = await rows(c, """SELECT student_id, semester_code, COUNT(*) FROM financial_accounts
                             GROUP BY 1,2 HAVING COUNT(*)>1""")
        tag("WARN", "duplicate financial account (student, semester)", len(r), [f"{a}/{b} x{n}" for a, b, n in r])
        n = await scalar(c, """SELECT COUNT(*) FROM financial_accounts f
                               LEFT JOIN students s ON s.student_id=f.student_id WHERE s.student_id IS NULL""")
        tag("FAIL", "financial account -> missing student", n)
        n = await scalar(c, """SELECT COUNT(*) FROM advisor_assignments a
                               LEFT JOIN students s ON s.student_code=a.student_code WHERE s.student_code IS NULL""")
        tag("FAIL", "advisor assignment -> missing student", n)
        n = await scalar(c, """SELECT COUNT(*) FROM notifications no
                               LEFT JOIN students s ON s.student_id=no.student_id WHERE s.student_id IS NULL""")
        tag("FAIL", "notification -> missing student", n)

    print(f"\n========== SUMMARY ==========\n  FAIL checks: {FAILS}   WARN checks: {WARNS}")
    print("  (FAIL = breaks integrity/model coherence; WARN = review; INFO = expected by design)")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
