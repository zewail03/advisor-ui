import asyncio
import os

os.environ["DATABASE_URL"] = "postgresql+asyncpg://aiu:aiu_dev@localhost:5433/aiu"
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def main():
    e = create_async_engine(os.environ["DATABASE_URL"])
    async with e.connect() as c:
        tables = [r[0] for r in (await c.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
        ))).all()]
        print("=== TABLES + ROWS ===")
        for t in tables:
            n = (await c.execute(text(f'SELECT COUNT(*) FROM "{t}"'))).scalar()
            print(f"{t}: {n}")
        print("\n=== FOREIGN KEYS ===")
        fks = (await c.execute(text("""
            SELECT tc.table_name, kcu.column_name,
                   ccu.table_name AS ref_table, ccu.column_name AS ref_col
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema='public'
            ORDER BY tc.table_name
        """))).all()
        for t, col, rt, rc in fks:
            print(f"{t}.{col} -> {rt}.{rc}")
    await e.dispose()


asyncio.run(main())
