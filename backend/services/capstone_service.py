"""Field Training (§19) + Graduation Project (§20) eligibility + enrollment."""
from datetime import datetime
from typing import Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.capstone import (
    CapstoneEnrollment,
    CapstoneMilestone,
    CapstoneStage,
    CapstoneStatus,
    STAGE_THRESHOLDS,
)
from models.student import Program, Student
from services.gpa_calculator import get_cgpa_components
from services.policy import get_policy

# capstone stage -> its policy key (admin-editable completion threshold)
_STAGE_POLICY = {
    CapstoneStage.field_training_a: "capstone.field_training_a_pct",
    CapstoneStage.field_training_b: "capstone.field_training_b_pct",
    CapstoneStage.graduation_project_i: "capstone.grad_project_i_pct",
    CapstoneStage.graduation_project_ii: "capstone.grad_project_ii_pct",
}


async def _completion_pct(student_id: int, db: AsyncSession) -> Tuple[float, int, int]:
    """Completion % from REAL completed (graded) credits / program requirement."""
    student = await db.get(Student, student_id)
    if not student:
        return 0.0, 0, 0
    program = await db.get(Program, student.program_id) if student.program_id else None
    required = (program.total_credits if program else 140) or 140
    _points, completed = await get_cgpa_components(student_id, db)
    pct = (completed / required * 100.0) if required else 0.0
    return pct, int(completed), int(required)


async def check_eligibility(
    student_id: str, stage: CapstoneStage, db: AsyncSession
) -> Tuple[bool, str, Dict]:
    pct, completed, required = await _completion_pct(student_id, db)
    threshold = float(await get_policy(_STAGE_POLICY[stage], db))
    info = {
        "completion_pct": round(pct, 2),
        "completed_credits": completed,
        "required_credits": required,
        "threshold_pct": threshold,
    }
    if pct < threshold:
        return (
            False,
            f"Need {threshold:.0f}% completion ({int(required * threshold / 100)} CH). "
            f"You have {completed}/{required} ({pct:.1f}%).",
            info,
        )
    return True, "Eligible", info


async def enroll_capstone(
    student_id: str,
    stage: CapstoneStage,
    semester_code: str,
    db: AsyncSession,
    supervisor_name: Optional[str] = None,
    supervisor_email: Optional[str] = None,
    title: Optional[str] = None,
    company_or_lab: Optional[str] = None,
) -> Dict:
    ok, msg, info = await check_eligibility(student_id, stage, db)
    if not ok:
        return {"success": False, "message": msg, **info}

    existing = (
        await db.execute(
            select(CapstoneEnrollment)
            .where(CapstoneEnrollment.student_id == student_id)
            .where(CapstoneEnrollment.stage == stage)
        )
    ).scalar_one_or_none()
    if existing:
        return {"success": False, "message": f"Already registered for {stage.value}"}

    row = CapstoneEnrollment(
        student_id=student_id,
        stage=stage,
        semester_code=semester_code,
        status=CapstoneStatus.in_progress,
        supervisor_name=supervisor_name,
        supervisor_email=supervisor_email,
        title=title,
        company_or_lab=company_or_lab,
    )
    db.add(row)
    await db.flush()

    # Scaffold default milestones
    defaults = (
        ["Proposal", "Mid-Review", "Final Report"]
        if stage in (CapstoneStage.graduation_project_i, CapstoneStage.graduation_project_ii)
        else ["Orientation", "Mid-Review", "Final Report"]
    )
    for name in defaults:
        db.add(CapstoneMilestone(capstone_enrollment_id=row.id, name=name))

    await db.commit()
    await db.refresh(row)
    return {
        "success": True,
        "message": "Capstone enrollment created",
        "capstone_enrollment_id": row.id,
        **info,
    }


async def list_for_student(student_id: str, db: AsyncSession):
    rows = (
        await db.execute(
            select(CapstoneEnrollment)
            .where(CapstoneEnrollment.student_id == student_id)
            .order_by(CapstoneEnrollment.created_at.asc())
        )
    ).scalars().all()
    out = []
    for r in rows:
        milestones = (
            await db.execute(
                select(CapstoneMilestone).where(
                    CapstoneMilestone.capstone_enrollment_id == r.id
                )
            )
        ).scalars().all()
        out.append({
            "id": r.id,
            "stage": r.stage.value,
            "status": r.status.value,
            "semester_code": r.semester_code,
            "title": r.title,
            "supervisor_name": r.supervisor_name,
            "company_or_lab": r.company_or_lab,
            "hours_logged": r.hours_logged,
            "grade_letter": r.grade_letter,
            "milestones": [
                {
                    "id": m.id,
                    "name": m.name,
                    "due_date": m.due_date.isoformat() if m.due_date else None,
                    "completed": m.completed,
                    "score": m.score,
                }
                for m in milestones
            ],
        })
    return out


async def update_milestone(
    milestone_id: str,
    db: AsyncSession,
    completed: Optional[bool] = None,
    score: Optional[float] = None,
    notes: Optional[str] = None,
) -> Optional[CapstoneMilestone]:
    m = await db.get(CapstoneMilestone, milestone_id)
    if not m:
        return None
    if completed is not None:
        m.completed = completed
    if score is not None:
        m.score = score
    if notes is not None:
        m.notes = notes
    await db.commit()
    await db.refresh(m)
    return m


async def submit_final(
    capstone_enrollment_id: str,
    grade_letter: str,
    grade_points: float,
    report_url: Optional[str],
    db: AsyncSession,
) -> Optional[CapstoneEnrollment]:
    row = await db.get(CapstoneEnrollment, capstone_enrollment_id)
    if not row:
        return None
    row.grade_letter = grade_letter
    row.grade_points = grade_points
    row.final_report_url = report_url
    row.status = CapstoneStatus.passed if grade_points and grade_points >= 1.0 else CapstoneStatus.failed
    row.completed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(row)
    return row
