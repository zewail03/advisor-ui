"""Seed an initial super-admin staff account (idempotent).

Run: python -m scripts.seed_admin
Default credentials (change after first login): admin / admin123
"""
import asyncio

from sqlalchemy import select

from core.database import AsyncSessionLocal
from core.security import get_password_hash
from models.staff import Staff, StaffRole

DEFAULTS = [
    ("admin", "Portal Administrator", "admin@aiu.edu.eg", "admin123", StaffRole.super_admin),
    ("registrar", "Registrar Office", "registrar@aiu.edu.eg", "registrar123", StaffRole.registrar),
    ("viewer", "Read Only Analyst", "viewer@aiu.edu.eg", "viewer123", StaffRole.readonly),
]


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        created = 0
        for username, full_name, email, password, role in DEFAULTS:
            exists = (
                await db.execute(select(Staff).where(Staff.username == username))
            ).scalar_one_or_none()
            if exists:
                continue
            db.add(Staff(
                username=username,
                full_name=full_name,
                email=email,
                hashed_password=get_password_hash(password),
                role=role.value,
                is_active=True,
            ))
            created += 1
        await db.commit()
        print(f"Seeded {created} staff account(s). Existing accounts left untouched.")
        print("Logins: admin/admin123 (super_admin), registrar/registrar123, viewer/viewer123")


if __name__ == "__main__":
    asyncio.run(seed())
