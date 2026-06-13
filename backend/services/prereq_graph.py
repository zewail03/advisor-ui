"""Prerequisite-chain analysis.

A course that unlocks a long chain (CSE015 -> CSE111 -> CSE221 -> ...) is more
critical than one that unlocks nothing: delaying it delays everything behind
it. `chain_unlock_counts` counts ALL transitive descendants of each course in
the prerequisite graph, optionally restricted to a set the student still owes.
"""
from typing import Dict, Iterable, List, Optional, Set, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.course import Prerequisite


def chain_unlock_counts(
    prereq_pairs: Iterable[Tuple[str, str]],
    restrict_to: Optional[Set[str]] = None,
) -> Dict[str, int]:
    """pairs are (course, its_prerequisite). Returns prereq -> number of
    distinct courses it transitively unlocks (within `restrict_to` if given)."""
    dependents: Dict[str, List[str]] = {}
    nodes: Set[str] = set()
    for course, prereq in prereq_pairs:
        dependents.setdefault(prereq, []).append(course)
        nodes.add(course)
        nodes.add(prereq)

    counts: Dict[str, int] = {}
    for node in nodes:
        seen: Set[str] = set()
        stack = list(dependents.get(node, ()))
        while stack:
            nxt = stack.pop()
            if nxt in seen:
                continue
            seen.add(nxt)
            stack.extend(dependents.get(nxt, ()))
        if restrict_to is not None:
            seen &= restrict_to
        counts[node] = len(seen)
    return counts


async def load_chain_unlocks(
    db: AsyncSession, restrict_to: Optional[Set[str]] = None
) -> Dict[str, int]:
    rows = (await db.execute(
        select(Prerequisite.course_code, Prerequisite.prerequisite_course_code)
    )).all()
    return chain_unlock_counts(rows, restrict_to=restrict_to)
