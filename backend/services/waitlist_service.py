"""Waitlist mechanics: tier-ranked joining and automatic seat promotion.

Joining: the queue is ordered by (registration tier, time joined) — a tier-1
on-plan student entered today outranks a tier-4 racer who joined last week
(services.registration_priority).

Promotion: whenever a seat frees up (drop/withdraw), the head of the queue is
automatically enrolled, notified, and the queue renumbered. Promotion re-checks
the essentials (not already enrolled in the course, seat still free); a stale
entry that fails is marked Expired and the next student is tried.
"""
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.ai_models import Notification
from models.course import Section
from models.enrollment import Enrollment, Waitlist
from models.student import Student

_ACTIVE = ("Enrolled", "Satisfied")


async def _active_count(section_id: int, db: AsyncSession) -> int:
    row = await db.execute(
        select(func.count(Enrollment.enrollment_id)).where(
            Enrollment.section_id == section_id,
            Enrollment.status.in_(_ACTIVE),
        )
    )
    return int(row.scalar() or 0)


async def _renumber(section_id: int, db: AsyncSession) -> None:
    rows = (await db.execute(
        select(Waitlist)
        .where(Waitlist.section_id == section_id, Waitlist.status == "Waiting")
        .order_by(Waitlist.priority, Waitlist.joined_at)
    )).scalars().all()
    for i, w in enumerate(rows, start=1):
        w.position = i


async def add_to_waitlist(
    student: Student, section: Section, db: AsyncSession
) -> Dict:
    """Tier-ranked join. Caller commits. Returns position + tier info."""
    from services.registration_priority import registration_tier

    tier, tier_reason = await registration_tier(student, section.course_code, db)
    db.add(Waitlist(
        student_id=student.student_id,
        section_id=section.section_id,
        position=0,
        priority=tier,
        status="Waiting",
        joined_at=datetime.utcnow(),
    ))
    await db.flush()
    await _renumber(section.section_id, db)
    pos_row = await db.execute(
        select(Waitlist.position).where(
            Waitlist.student_id == student.student_id,
            Waitlist.section_id == section.section_id,
        )
    )
    return {
        "position": int(pos_row.scalar() or 1),
        "priority_tier": tier,
        "priority_reason": tier_reason,
    }


async def promote_for_section(section_id: int, db: AsyncSession) -> List[Dict]:
    """Fill every free seat from the head of the queue. Caller commits.
    Returns the promotions performed (student_id, course, position held)."""
    section = await db.get(Section, section_id)
    if not section:
        return []

    promoted: List[Dict] = []
    while True:
        free = section.capacity - await _active_count(section_id, db)
        if free <= 0:
            break
        head: Optional[Waitlist] = (await db.execute(
            select(Waitlist)
            .where(Waitlist.section_id == section_id, Waitlist.status == "Waiting")
            .order_by(Waitlist.priority, Waitlist.joined_at)
            .limit(1)
        )).scalar_one_or_none()
        if head is None:
            break

        # stale-entry guard: already in this course this semester?
        dup = (await db.execute(
            select(Enrollment.enrollment_id)
            .join(Section, Section.section_id == Enrollment.section_id)
            .where(
                and_(
                    Enrollment.student_id == head.student_id,
                    Enrollment.status.in_(_ACTIVE),
                    Section.semester_id == section.semester_id,
                    Section.course_code == section.course_code,
                )
            )
        )).scalar_one_or_none()
        if dup is not None:
            head.status = "Expired"
            continue

        db.add(Enrollment(
            student_id=head.student_id,
            section_id=section_id,
            status="Enrolled",
            enrollment_date=datetime.utcnow(),
        ))
        head.status = "Registered"
        head.registered_at = datetime.utcnow()
        db.add(Notification(
            student_id=head.student_id,
            type="registration",
            subject=f"Waitlist promotion — {section.course_code}",
            message=(f"A seat opened in {section.course_code} (section "
                     f"{section.section_number}) and you were auto-enrolled from "
                     f"the waitlist (priority tier {head.priority})."),
            status="Unread",
            created_at=datetime.utcnow(),
            sent_at=datetime.utcnow(),
        ))
        promoted.append({
            "student_id": head.student_id,
            "course_code": section.course_code,
            "section_id": section_id,
            "from_priority_tier": head.priority,
        })

    if promoted:
        await _renumber(section_id, db)
    return promoted
