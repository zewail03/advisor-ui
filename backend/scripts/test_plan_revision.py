"""Smoke test: term_caps plan revision is rules-engine validated.

Run:  cd backend && .\\venv\\Scripts\\python.exe scripts\\test_plan_revision.py
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ai.nodes.tool_nodes import _extract_term_caps  # noqa: E402
from core.database import AsyncSessionLocal  # noqa: E402
from models.student import Student  # noqa: E402
from services.degree_planner import compare_degree_plans  # noqa: E402


def test_extractor():
    cases = [
        ("can i make Fall 2027 more lightly load", {"Fall 2027": 12}),
        ("make fall 2027 lighter", {"Fall 2027": 12}),
        ("cap Spring 2027 at 14 hours", {"Spring 2027": 14}),
        ("make Fall 2027 only 15", {"Fall 2027": 15}),
        ("reduce summer 2027", {"Summer 2027": 12}),
        # must NOT trigger:
        ("can i graduate in fall 2027 ?", {}),
        ("is it easier to graduate in Fall 2027?", {}),
        ("i wanna graduate early", {}),
        ("plan to early graduation", {}),
        ("what courses in Fall 2026?", {}),
    ]
    ok = True
    for msg, want in cases:
        got = _extract_term_caps(msg)
        status = "OK " if got == want else "FAIL"
        if got != want:
            ok = False
        print(f"  [{status}] {msg!r} -> {got} (want {want})")
    return ok


async def test_planner():
    async with AsyncSessionLocal() as db:
        walid = await db.get(Student, 2)  # 25100002
        payload = await compare_degree_plans(walid, db, term_caps={"Fall 2027": 12})

    ok = True
    for mode in ("normal", "fastest"):
        plan = payload[mode]
        print(f"\n{mode.upper()} -> graduates {plan['graduation_term']}, caps applied: {plan['applied_term_caps']}")
        for t in plan["terms"]:
            mark = ""
            if t["term"] == "Fall 2027" and t["credits"] > 12:
                mark, ok = "  <-- VIOLATES requested cap", False
            if t["type"] == "Summer" and t["credits"] > 9:
                mark, ok = "  <-- VIOLATES summer cap", False
            codes = ", ".join(c["course_code"] for c in t["courses"])
            note = f"  [{t['note']}]" if t.get("note") else ""
            print(f"  {t['term']}: {t['credits']} CH ({codes}){note}{mark}")
        if plan.get("unplannable"):
            print(f"  unplannable: {plan['unplannable']}")
    print(f"\ntop-level applied_term_caps: {payload.get('applied_term_caps')}")
    print(f"load_rules: {payload.get('load_rules')}")
    return ok


if __name__ == "__main__":
    print("=== extractor ===")
    ok1 = test_extractor()
    print("\n=== planner with Fall 2027 capped at 12 (Walid) ===")
    ok2 = asyncio.run(test_planner())
    print(f"\nRESULT: {'ALL OK' if ok1 and ok2 else 'FAILURES'}")
    sys.exit(0 if ok1 and ok2 else 1)
