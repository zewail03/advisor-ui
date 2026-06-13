"""Petition workflow (§14, §15, §16, §27)."""
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from models.academic import Semester
from models.enrollment import Grade
from models.petitions import (
    APPEAL_WINDOW_DAYS,
    Petition,
    PetitionStatus,
    PetitionType,
)
from models.student import Program, Student
from services.audit_service import log_action
from services.gpa_calculator import get_cgpa_components
from services.policy import get_policy


async def _get_student(student_id: int, db: AsyncSession) -> Optional[Student]:
    return await db.get(Student, student_id)


async def _approved_count(
    student_id: int, ptype: PetitionType, db: AsyncSession
) -> int:
    return (
        await db.execute(
            select(func.count())
            .select_from(Petition)
            .where(Petition.student_id == student_id)
            .where(Petition.type == ptype)
            .where(Petition.status == PetitionStatus.approved)
        )
    ).scalar_one()


async def _frozen_semester_codes(student_id: int, db: AsyncSession) -> set:
    rows = (
        await db.execute(
            select(Petition.freeze_semester_code)
            .where(Petition.student_id == student_id)
            .where(Petition.type == PetitionType.freeze)
            .where(Petition.status == PetitionStatus.approved)
        )
    ).all()
    return {r[0] for r in rows if r[0]}


async def _violates_consecutive_freeze(
    student_id: int, requested_code: str, consec_cap: int, db: AsyncSession
) -> bool:
    """§15.3: True if approving this freeze would exceed `consec_cap`
    consecutive frozen MAIN semesters (summers don't count)."""
    rows = (
        await db.execute(
            select(Semester.code)
            .where(~Semester.code.like("Summer%"))
            .order_by(Semester.start_date)
        )
    ).all()
    codes = [r[0] for r in rows if r[0]]
    requested = requested_code.replace("-", " ")
    if requested not in codes:
        return False
    i = codes.index(requested)
    preceding = codes[max(0, i - consec_cap):i]
    if len(preceding) < consec_cap:
        return False
    frozen = await _frozen_semester_codes(student_id, db)
    return all(c in frozen for c in preceding)


async def _completion_pct(student_id: int, db: AsyncSession) -> Tuple[float, int, int]:
    """% of the program's required credit hours completed (real graded credits)."""
    student = await _get_student(student_id, db)
    program = (
        await db.get(Program, student.program_id)
        if student and student.program_id
        else None
    )
    required = (program.total_credits if program else 140) or 140
    _points, completed = await get_cgpa_components(student_id, db)
    pct = (completed / required * 100.0) if required else 0.0
    return pct, int(completed), int(required)


async def validate_eligibility(
    student_id: str,
    ptype: PetitionType,
    db: AsyncSession,
    enrollment_id: Optional[str] = None,
    freeze_semester_code: Optional[str] = None,
) -> Tuple[bool, str]:
    student = await _get_student(student_id, db)
    cgpa = (student.cgpa if student else 0.0) or 0.0
    status = (student.status if student else "") or ""

    if ptype == PetitionType.final_chance:
        # §14.1: dismissed/at-dismissal-risk, >=80% credits completed,
        # and never used a final chance before.
        if status.lower() not in ("dismissed", "final chance", "dismissal risk"):
            return False, "Final chance is only available to dismissed students"
        if await _approved_count(student_id, PetitionType.final_chance, db) > 0:
            return False, "Final chance already used — the policy applies once per student"
        min_pct = int(await get_policy("petition.final_chance_min_completion_pct", db))
        pct, completed, required = await _completion_pct(student_id, db)
        if pct < min_pct:
            return False, (
                f"Final chance requires ≥{min_pct}% of program credits completed — "
                f"you have {completed}/{required} CH ({pct:.1f}%)"
            )
        return True, "Eligible"

    if ptype == PetitionType.freeze:
        # §15.3: total cap across the program + consecutive-semester cap.
        total_cap = int(await get_policy("petition.freeze_max_total", db))
        consec_cap = int(await get_policy("petition.freeze_max_consecutive", db))
        used = await _approved_count(student_id, PetitionType.freeze, db)
        if used >= total_cap:
            return False, f"Freeze limit reached ({used}/{total_cap} total across the program)"
        if freeze_semester_code and await _violates_consecutive_freeze(
            student_id, freeze_semester_code, consec_cap, db
        ):
            return False, (
                f"Cannot freeze more than {consec_cap} consecutive semesters — "
                f"the {consec_cap} semesters before {freeze_semester_code} are already frozen"
            )
        return True, "Eligible"

    if ptype in (PetitionType.transfer_in, PetitionType.transfer_between_programs):
        min_cgpa = float(await get_policy("petition.transfer_min_cgpa", db))
        if cgpa < min_cgpa:
            return False, f"Transfer requires CGPA ≥ {min_cgpa:.2f} (current {cgpa:.2f})"
        return True, "Eligible"

    if ptype == PetitionType.grade_appeal:
        if not enrollment_id:
            return False, "Grade appeal requires an enrollment id"
        grade = (
            await db.execute(select(Grade).where(Grade.enrollment_id == enrollment_id))
        ).scalar_one_or_none()
        if not grade:
            return False, "No grade on record for that enrollment"
        age = datetime.utcnow() - grade.recorded_at
        if age > timedelta(days=APPEAL_WINDOW_DAYS):
            return False, f"Appeal window ({APPEAL_WINDOW_DAYS} days) has expired"
        return True, "Eligible"

    return False, "Unknown petition type"


async def submit_petition(
    student_id: str,
    ptype: PetitionType,
    subject: str,
    db: AsyncSession,
    body: Optional[str] = None,
    payload_json: Optional[str] = None,
    enrollment_id: Optional[str] = None,
    current_grade: Optional[str] = None,
    requested_grade: Optional[str] = None,
    freeze_semester_code: Optional[str] = None,
    source_program_code: Optional[str] = None,
    target_program_code: Optional[str] = None,
) -> Dict:
    ok, msg = await validate_eligibility(
        student_id, ptype, db,
        enrollment_id=enrollment_id,
        freeze_semester_code=freeze_semester_code,
    )
    if not ok:
        return {"success": False, "message": msg}

    student = await _get_student(student_id, db)
    petition = Petition(
        student_id=student_id,
        type=ptype,
        status=PetitionStatus.submitted,
        subject=subject,
        body=body,
        payload_json=payload_json,
        enrollment_id=enrollment_id,
        current_grade=current_grade,
        requested_grade=requested_grade,
        freeze_semester_code=freeze_semester_code,
        source_program_code=source_program_code,
        target_program_code=target_program_code,
        transfer_cgpa_snapshot=student.cgpa if student else None,
    )
    db.add(petition)
    await db.flush()
    await log_action(
        db,
        action="petition.submit",
        entity_type="petition",
        entity_id=petition.id,
        actor_id=str(student_id),
        actor_role="student",
        subject_student_id=str(student_id),
        after={"type": ptype.value, "subject": subject},
    )
    await db.commit()
    await db.refresh(petition)
    return {"success": True, "petition_id": petition.id, "status": petition.status.value}


async def _apply_effect(petition: Petition, db: AsyncSession) -> None:
    """Applies the side-effect of an approved petition where automatic."""
    if petition.effect_applied:
        return

    if petition.type == PetitionType.grade_appeal and petition.requested_grade and petition.enrollment_id:
        from models.enrollment import GRADE_POINTS, GradeEnum
        grade = (
            await db.execute(
                select(Grade).where(Grade.enrollment_id == petition.enrollment_id)
            )
        ).scalar_one_or_none()
        if grade:
            try:
                grade.letter_grade = GradeEnum(petition.requested_grade)
            except ValueError:
                pass
            grade.grade_points = GRADE_POINTS.get(petition.requested_grade, grade.grade_points)

    if petition.type == PetitionType.transfer_between_programs and petition.target_program_code:
        from models.student import Program
        target = (
            await db.execute(
                select(Program).where(Program.code == petition.target_program_code)
            )
        ).scalar_one_or_none()
        student = await db.get(Student, petition.student_id)
        if student and target:
            student.program_id = target.program_id

    if petition.type == PetitionType.final_chance:
        student = await db.get(Student, petition.student_id)
        if student:
            # Registrar will re-evaluate standing next term.
            student.status = "Probation"

    petition.effect_applied = True


async def decide_petition(
    petition_id: str,
    reviewer_id: str,
    reviewer_role: str,
    approve: bool,
    comment: Optional[str],
    db: AsyncSession,
) -> Tuple[bool, str, Optional[Petition]]:
    petition = await db.get(Petition, petition_id)
    if not petition:
        return False, "Petition not found", None
    if petition.status in (PetitionStatus.approved, PetitionStatus.rejected):
        return False, f"Petition already {petition.status.value}", petition

    before = {"status": petition.status.value}
    petition.status = PetitionStatus.approved if approve else PetitionStatus.rejected
    petition.reviewer_id = reviewer_id
    petition.reviewer_role = reviewer_role
    petition.decision_comment = comment
    petition.decided_at = datetime.utcnow()

    if approve:
        await _apply_effect(petition, db)

    await log_action(
        db,
        action=f"petition.{petition.status.value}",
        entity_type="petition",
        entity_id=petition.id,
        actor_id=reviewer_id,
        actor_role=reviewer_role,
        subject_student_id=str(petition.student_id),
        before=before,
        after={
            "status": petition.status.value,
            "type": petition.type.value,
            "effect_applied": petition.effect_applied,
            "comment": comment,
        },
    )
    await db.commit()
    await db.refresh(petition)
    return True, "OK", petition
