"""Seed a few pending petitions + advisor approvals so the admin review
queues are populated for the demo. Insert-only-if-empty (idempotent).

Run: python -m scripts.seed_approvals
"""
import asyncio
from datetime import datetime, timedelta

from sqlalchemy import func, select

from core.database import AsyncSessionLocal
from models.advisor import AdvisorApproval, ApprovalStatus
from models.petitions import Petition, PetitionStatus, PetitionType
from models.student import Student

PETITIONS = [
    (PetitionType.freeze, "Freeze request — Fall 2026", "Family medical circumstances; requesting a one-term freeze.", {"freeze_semester_code": "Fall-2026"}),
    (PetitionType.transfer_between_programs, "Transfer to Data Science track", "Strong interest in ML; requesting transfer between programs.", {"target_program_code": "DS"}),
    (PetitionType.grade_appeal, "Grade appeal — CSE361", "Believe my final exam was miscalculated; requesting review.", {"current_grade": "C", "requested_grade": "B"}),
    (PetitionType.final_chance, "Final chance petition", "Requesting a final chance to recover my standing next term.", {}),
    (PetitionType.freeze, "Freeze request — Spring 2027", "Internship abroad; requesting a semester freeze.", {"freeze_semester_code": "Spring-2027"}),
]

APPROVALS = [
    ("registration", "Fall-2026", "Requesting registration approval for an 18-credit load."),
    ("add", "Fall-2026", "Add CSE471 after the deadline — prerequisite cleared late."),
    ("load_adjustment", "Fall-2026", "Requesting overload to 21 credits to graduate on time."),
    ("withdrawal", "Spring-2026", "Requesting course withdrawal from MAT212."),
]


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        student_ids = [
            r[0] for r in (
                await db.execute(select(Student.student_id).order_by(Student.student_id).limit(12))
            ).all()
        ]
        now = datetime.utcnow()

        n_pet = (await db.execute(select(func.count()).select_from(Petition))).scalar() or 0
        if n_pet == 0:
            for i, (ptype, subject, body, extra) in enumerate(PETITIONS):
                db.add(Petition(
                    student_id=student_ids[i % len(student_ids)],
                    type=ptype,
                    status=PetitionStatus.submitted,
                    subject=subject,
                    body=body,
                    submitted_at=now - timedelta(days=i),
                    **extra,
                ))
            print(f"Inserted {len(PETITIONS)} pending petitions.")
        else:
            print(f"Petitions table not empty ({n_pet}); skipped.")

        n_app = (await db.execute(select(func.count()).select_from(AdvisorApproval))).scalar() or 0
        if n_app == 0:
            for i, (atype, sem, justification) in enumerate(APPROVALS):
                db.add(AdvisorApproval(
                    student_id=student_ids[(i + 5) % len(student_ids)],
                    advisor_id=None,
                    type=atype,
                    status=ApprovalStatus.pending.value,
                    semester_code=sem,
                    justification=justification,
                    created_at=now - timedelta(days=i),
                ))
            print(f"Inserted {len(APPROVALS)} pending advisor approvals.")
        else:
            print(f"Advisor approvals table not empty ({n_app}); skipped.")

        await db.commit()


if __name__ == "__main__":
    asyncio.run(seed())
