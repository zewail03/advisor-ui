"""Enrollment service: single + bulk enroll, drop, waitlist.

Rewritten for the real AIU schema:
  * Integer PKs for student_id / section_id / enrollment_id.
  * Section has `course_code` (string FK to Course.code), no course_id.
  * Semester is looked up via Section.semester_id -> Semester.code.
  * Enrollment has no `semester_code` / `advisor_approved` / `enrolled_at` columns.
    Use `enrollment_date` and Section.semester_id for the semester context.
  * Waitlist count comes from live row counts, not Section.waitlist_count.
"""
from datetime import datetime
from typing import Dict

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.academic import Semester
from models.course import Course, Section
from models.enrollment import Enrollment, Waitlist
from services.validation import (
    check_corequisites,
    check_credit_limit,
    check_prerequisites,
    check_seat_availability,
    check_time_conflict,
    is_registration_window_open,
)


async def _advisor_gate(
    student_id: int,
    section: Section,
    new_credits: int,
    semester_code: str,
    db: AsyncSession,
    commit: bool,
) -> Dict | None:
    """Overload and ahead-of-plan ("racer") registrations need advisor
    sign-off. If an approved AdvisorApproval exists the gate opens; otherwise
    a pending request is filed with the student's advisor and enrollment is
    held. Returns a result dict when held, None when clear."""
    from sqlalchemy import func as _func

    from models.advisor import AdvisorApproval, AdvisorAssignment
    from models.course import Course as _Course
    from models.student import Student
    from services.policy import get_policy
    from services.registration_priority import registration_tier

    student = await db.get(Student, student_id)
    if student is None:
        return None

    needed: list = []  # (approval_type, related_id, reason)

    is_summer = "Summer" in (semester_code or "")
    if not is_summer:
        standard = int(await get_policy("enrollment.credit_limit_standard", db))
        current = int((await db.execute(
            select(_func.coalesce(_func.sum(_Course.credits), 0))
            .select_from(Enrollment)
            .join(Section, Section.section_id == Enrollment.section_id)
            .join(_Course, _Course.code == Section.course_code)
            .where(
                Enrollment.student_id == student_id,
                Enrollment.status.in_(("Enrolled", "Satisfied")),
                Section.semester_id == section.semester_id,
            )
        )).scalar() or 0)
        if current + new_credits > standard:
            needed.append((
                "load_adjustment", semester_code,
                f"overload request: {current + new_credits} CH exceeds the "
                f"normal {standard} CH load",
            ))

    tier, tier_reason = await registration_tier(student, section.course_code, db)
    if tier == 4:
        needed.append(("add", section.course_code,
                       f"ahead-of-plan registration: {tier_reason}"))

    if not needed:
        return None

    for approval_type, related_id, reason in needed:
        approved = (await db.execute(
            select(AdvisorApproval).where(
                AdvisorApproval.student_id == student_id,
                AdvisorApproval.type == approval_type,
                AdvisorApproval.related_id == related_id,
                AdvisorApproval.status == "approved",
            )
        )).scalars().first()
        if approved:
            continue

        pending = (await db.execute(
            select(AdvisorApproval).where(
                AdvisorApproval.student_id == student_id,
                AdvisorApproval.type == approval_type,
                AdvisorApproval.related_id == related_id,
                AdvisorApproval.status == "pending",
            )
        )).scalars().first()
        if not pending:
            advisor_id = (await db.execute(
                select(AdvisorAssignment.advisor_id).where(
                    AdvisorAssignment.student_code == student.student_code,
                    AdvisorAssignment.is_active == True,  # noqa: E712
                ).limit(1)
            )).scalar_one_or_none()
            db.add(AdvisorApproval(
                student_id=student_id,
                advisor_id=advisor_id,
                type=approval_type,
                status="pending",
                related_id=related_id,
                semester_code=semester_code,
                justification=reason,
            ))
            if commit:
                await db.commit()
        return {
            "success": False,
            "waitlisted": False,
            "requires_approval": True,
            "approval_type": approval_type,
            "message": (f"Advisor approval required — {reason}. "
                        f"{'Request already pending with your advisor.' if pending else 'Request sent to your advisor.'}"),
            "section_id": section.section_id,
            "course_code": section.course_code,
        }
    return None


async def _section_context(section_id: int, db: AsyncSession):
    section = await db.get(Section, section_id)
    if not section:
        return None, None, None
    course = await db.execute(select(Course).where(Course.code == section.course_code))
    course = course.scalar_one_or_none()
    sem = await db.get(Semester, section.semester_id)
    semester_code = sem.code if sem else None
    return section, course, semester_code


async def enroll_single(
    student_id: int,
    section_id: int,
    db: AsyncSession,
    commit: bool = True,
) -> Dict:
    """Run all 5 checks and enroll, or waitlist on seat shortage.

    Returns: {success, message, waitlisted, section_id, course_code}
    """
    section, course, semester_code = await _section_context(section_id, db)
    if not section:
        return {
            "success": False,
            "waitlisted": False,
            "message": "Section not found",
            "section_id": section_id,
        }
    course_code = course.code if course else section.course_code

    # 1. Registration window
    if semester_code:
        ok, msg = await is_registration_window_open(semester_code, db)
        if not ok:
            return {
                "success": False,
                "waitlisted": False,
                "message": msg,
                "section_id": section_id,
                "course_code": course_code,
            }

    # Duplicate: already enrolled in this course (any section) for this semester.
    dup_for_course = await db.execute(
        select(Enrollment)
        .join(Section, Section.section_id == Enrollment.section_id)
        .where(
            and_(
                Enrollment.student_id == student_id,
                Enrollment.status.in_(("Enrolled", "Satisfied")),
                Section.semester_id == section.semester_id,
                Section.course_code == section.course_code,
            )
        )
    )
    if dup_for_course.scalar_one_or_none():
        return {
            "success": False,
            "waitlisted": False,
            "message": "Already enrolled in this course",
            "section_id": section_id,
            "course_code": course_code,
        }

    # 2. Prerequisites (keyed by course_code now).
    ok, msg = await check_prerequisites(student_id, section.course_code, db)
    if not ok:
        return {
            "success": False,
            "waitlisted": False,
            "message": msg,
            "section_id": section_id,
            "course_code": course_code,
        }

    # 2b. Co-requisites (§25) — no-op shim; AIU schema has no corequisite table.
    ok, msg = await check_corequisites(student_id, section.course_code, semester_code or "", db)
    if not ok:
        return {
            "success": False,
            "waitlisted": False,
            "message": msg,
            "section_id": section_id,
            "course_code": course_code,
        }

    # 3. Credit limit
    credits = course.credits if course else 3
    if semester_code:
        ok, msg = await check_credit_limit(student_id, credits, semester_code, db)
        if not ok:
            return {
                "success": False,
                "waitlisted": False,
                "message": msg,
                "section_id": section_id,
                "course_code": course_code,
            }

    # 3b. Advisor sign-off gate — overload and ahead-of-plan ("racer")
    # registrations are held until the advisor approves.
    gate = await _advisor_gate(
        student_id, section, credits, semester_code or "", db, commit
    )
    if gate is not None:
        return gate

    # 4. Time conflict
    ok, msg = await check_time_conflict(student_id, section_id, semester_code or "", db)
    if not ok:
        return {
            "success": False,
            "waitlisted": False,
            "message": msg,
            "section_id": section_id,
            "course_code": course_code,
        }

    # 5. Seat availability
    ok, msg = await check_seat_availability(section_id, db)
    if not ok:
        # Full -> add to waitlist
        already = await db.execute(
            select(Waitlist).where(
                and_(Waitlist.student_id == student_id, Waitlist.section_id == section_id)
            )
        )
        if already.scalar_one_or_none():
            return {
                "success": False,
                "waitlisted": True,
                "message": "Already on waitlist",
                "section_id": section_id,
                "course_code": course_code,
            }

        from models.student import Student
        from services.waitlist_service import add_to_waitlist

        student = await db.get(Student, student_id)
        info = await add_to_waitlist(student, section, db)
        if commit:
            await db.commit()
        return {
            "success": False,
            "waitlisted": True,
            "message": (f"Section full — added to waitlist at position "
                        f"{info['position']} (priority tier {info['priority_tier']}: "
                        f"{info['priority_reason']})"),
            "section_id": section_id,
            "course_code": course_code,
            "waitlist_position": info["position"],
        }

    # All checks passed -> enroll
    enrollment = Enrollment(
        student_id=student_id,
        section_id=section_id,
        status="Enrolled",
        enrollment_date=datetime.utcnow(),
    )
    db.add(enrollment)
    if commit:
        await db.commit()
        await db.refresh(enrollment)
    return {
        "success": True,
        "waitlisted": False,
        "message": "Enrolled successfully",
        "section_id": section_id,
        "course_code": course_code,
        "enrollment_id": enrollment.enrollment_id,
    }


async def drop_enrollment(
    student_id: int, enrollment_id: int, db: AsyncSession
) -> Dict:
    enrollment = await db.get(Enrollment, int(enrollment_id))
    if not enrollment or enrollment.student_id != student_id:
        return {"success": False, "message": "Enrollment not found"}
    if enrollment.status not in ("Enrolled", "Satisfied"):
        return {"success": False, "message": "Enrollment already dropped"}
    enrollment.status = "Dropped"
    enrollment.drop_date = datetime.utcnow()

    # the freed seat goes to the head of the waitlist automatically
    from services.waitlist_service import promote_for_section

    promoted = await promote_for_section(enrollment.section_id, db)
    await db.commit()
    return {
        "success": True,
        "message": "Class dropped successfully",
        "enrollment_id": enrollment_id,
        "waitlist_promotions": promoted,
    }
