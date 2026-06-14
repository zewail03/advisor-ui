"""Create an admin-portal staff login for every instructor (idempotent).

One Staff row per distinct instructor_name on `sections`, so each Dr./Eng. can
sign in to the admin portal. Run from backend/:  python -m scripts.seed_instructor_staff

Roles (per request):
  super_admin -> Dr. Ashraf Elsayed, Dr. Mostafa Elnainay
  registrar   -> every other Dr.
  readonly    -> every Eng. / TA
The "University Staff" placeholder bucket is skipped (not a real person).

Email/username = firstname.lastname@aiu.edu.eg (title stripped, spaces -> dots).
Shared default password for all: aiu12345  (change after first login).
"""
import asyncio
import re

from sqlalchemy import select, text

from core.database import AsyncSessionLocal
from core.security import get_password_hash
from models.staff import Staff, StaffRole

DEFAULT_PASSWORD = "aiu12345"
EMAIL_DOMAIN = "aiu.edu.eg"
SUPER_ADMINS = {"Dr. Ashraf Elsayed", "Dr. Mostafa Elnainay"}


def slug(name: str) -> str:
    base = re.sub(r"^(Dr\.|Eng\.)\s*", "", name).strip()
    return ".".join(base.lower().split())


def role_for(name: str) -> StaffRole:
    if name in SUPER_ADMINS:
        return StaffRole.super_admin
    if name.startswith("Dr."):
        return StaffRole.registrar
    return StaffRole.readonly


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        names = [
            r[0]
            for r in (
                await db.execute(
                    text(
                        "SELECT DISTINCT instructor_name FROM sections "
                        "WHERE instructor_name LIKE 'Dr.%' OR instructor_name LIKE 'Eng.%' "
                        "ORDER BY instructor_name"
                    )
                )
            ).all()
        ]

        hashed = get_password_hash(DEFAULT_PASSWORD)  # reuse one hash for all
        created, skipped = [], []
        for name in names:
            username = slug(name)
            email = f"{username}@{EMAIL_DOMAIN}"
            role = role_for(name)
            exists = (
                await db.execute(
                    select(Staff).where(
                        (Staff.username == username) | (Staff.email == email)
                    )
                )
            ).scalar_one_or_none()
            if exists:
                skipped.append((username, exists.role))
                continue
            db.add(
                Staff(
                    username=username,
                    full_name=name,
                    email=email,
                    hashed_password=hashed,
                    role=role.value,
                    is_active=True,
                )
            )
            created.append((username, email, role.value))
        await db.commit()

        print(f"Created {len(created)} instructor staff account(s); skipped {len(skipped)} existing.")
        print(f"Shared password: {DEFAULT_PASSWORD}\n")
        for username, email, role in sorted(created, key=lambda x: (x[2], x[0])):
            print(f"  {role:<12} {username:<22} {email}")
        if skipped:
            print("\nAlready existed (left untouched):")
            for username, role in skipped:
                print(f"  {role:<12} {username}")


if __name__ == "__main__":
    asyncio.run(seed())
