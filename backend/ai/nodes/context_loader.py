from datetime import datetime

from sqlalchemy import func, select

from ai.state import ChatState
from core.database import AsyncSessionLocal
from models.academic import AcademicStanding, RegistrationPeriod, Semester
from models.course import Course, Section
from models.enrollment import Enrollment, Grade
from models.student import Program, Student
from services.policy import get_policy


async def load_student_context(state: ChatState) -> ChatState:
    async with AsyncSessionLocal() as db:
        student = await db.get(Student, state["student_id"])
        if not student:
            return {**state, "student_context": {}}

        # Latest standing (for status only; GPA is calculated from actual grades)
        all_standings_res = await db.execute(
            select(AcademicStanding, Semester)
            .join(Semester, Semester.semester_id == AcademicStanding.semester_id)
            .where(AcademicStanding.student_code == student.student_code)
            .order_by(AcademicStanding.semester_id.desc())
        )
        all_standings = all_standings_res.all()
        standing = all_standings[0][0] if all_standings else None

        enrolled_res = await db.execute(
            select(Section.course_code, Semester.code)
            .select_from(Enrollment)
            .join(Section, Section.section_id == Enrollment.section_id)
            .join(Semester, Semester.semester_id == Section.semester_id)
            .where(
                Enrollment.student_id == student.student_id,
                Enrollment.status == "Enrolled",
            )
        )
        enrolled = enrolled_res.all()
        in_progress = [f"{code} ({sem})" for code, sem in enrolled]

        # Registration windows open RIGHT NOW — deadlines the advisor must know
        now = datetime.utcnow()
        win_rows = await db.execute(
            select(Semester.code, func.max(RegistrationPeriod.close_date))
            .select_from(RegistrationPeriod)
            .join(Semester, Semester.semester_id == RegistrationPeriod.semester_id)
            .where(
                RegistrationPeriod.is_active == True,  # noqa: E712
                (RegistrationPeriod.open_date.is_(None)) | (RegistrationPeriod.open_date <= now),
                (RegistrationPeriod.close_date.is_(None)) | (RegistrationPeriod.close_date >= now),
            )
            .group_by(Semester.code)
        )
        open_windows = [
            f"{code} (closes {close.strftime('%B %d, %Y')})" if close else code
            for code, close in win_rows.all()
        ]

        program = await db.get(Program, student.program_id)

        # Hard load caps from the policy table — the LLM must know them so it
        # never invents an over-cap plan when chatting about loads
        limit_summer = int(await get_policy("enrollment.credit_limit_summer", db))
        limit_std = int(await get_policy("enrollment.credit_limit_standard", db))
        limit_high = int(await get_policy("enrollment.credit_limit_high", db))
        overload_bar = float(await get_policy("enrollment.overload_min_cgpa", db))
        load_limits = (
            f"Summer terms max {limit_summer} CH; regular semesters max {limit_std} CH "
            f"(overload to {limit_high} CH only with CGPA > {overload_bar} from semester 4)"
        )

        # Calculate CGPA + latest SGPA from actual graded courses (verifiable from transcript)
        grade_rows = await db.execute(
            select(
                Grade.grade_points,
                Course.credits,
                Grade.counts_in_gpa,
                Grade.grade_letter,
                Section.semester_id,
            )
            .select_from(Grade)
            .join(Enrollment, Enrollment.enrollment_id == Grade.enrollment_id)
            .join(Section, Section.section_id == Enrollment.section_id)
            .join(Course, Course.code == Section.course_code)
            .where(Enrollment.student_id == student.student_id)
        )
        tot_pts = 0.0
        tot_cr = 0
        earned_cr = 0
        by_sem: dict[int, tuple[float, int]] = {}
        for pts, credits, counts, letter, sem_id in grade_rows.all():
            if not counts or pts is None or letter in ("W", "I", "S", "U"):
                continue
            p = float(pts) * int(credits or 0)
            c = int(credits or 0)
            tot_pts += p
            tot_cr += c
            if float(pts) >= 1.0:
                earned_cr += c
            prev = by_sem.get(sem_id, (0.0, 0))
            by_sem[sem_id] = (prev[0] + p, prev[1] + c)

        cgpa = round(tot_pts / tot_cr, 3) if tot_cr else 0.0
        sgpa_current = None
        if by_sem:
            latest_sem_id = max(by_sem.keys())
            sp, sc = by_sem[latest_sem_id]
            sgpa_current = round(sp / sc, 3) if sc else None

        ctx = {
            "student_number": student.student_code,
            "full_name": student.full_name,
            "program_id": student.program_id,
            "academic_level": student.level,
            "cgpa": cgpa,
            "sgpa_current": sgpa_current,
            "standing": (standing.status or "Good Standing") if standing else "Good Standing",
            "consecutive_probation": standing.probation_semesters if standing else 0,
            "current_enrolled_count": len(enrolled),
            "today": now.strftime("%A, %B %d, %Y"),
            "open_registration_windows": "; ".join(open_windows) or "none",
            "in_progress_courses": ", ".join(in_progress) or "none",
            "earned_credits": earned_cr,
            "total_credits": program.total_credits if program else None,
            "load_limits": load_limits,
        }
    return {**state, "student_context": ctx}
