"""Lightweight web search (DuckDuckGo, no API key) for grounding answers in real,
current web data — e.g. real job-market requirements on the Career Path Advisor.

Synchronous by nature (ddgs blocks), so call `research_role`/`search_web` via
`asyncio.to_thread(...)` from async endpoints. Results are TTL-cached so a demo
stays fast and stable, and every failure degrades gracefully to an empty list.
"""
import time
from typing import Dict, List

_CACHE: Dict[str, tuple] = {}
_TTL = 1800.0  # 30 min — keeps a demo session's searches stable + fast


def _cache_get(key: str):
    hit = _CACHE.get(key)
    if hit and hit[0] > time.time():
        return hit[1]
    return None


def search_web(query: str, max_results: int = 6) -> List[Dict]:
    """Return [{title, url, snippet}] for a query. Never raises."""
    key = f"{query}|{max_results}"
    cached = _cache_get(key)
    if cached is not None:
        return cached
    out: List[Dict] = []
    try:
        from ddgs import DDGS

        for r in DDGS().text(query, max_results=max_results) or []:
            url = r.get("href") or r.get("url") or ""
            if not url:
                continue
            out.append({
                "title": (r.get("title") or "").strip(),
                "url": url,
                "snippet": (r.get("body") or "").strip(),
            })
    except Exception:
        out = []
    _CACHE[key] = (time.time() + _TTL, out)
    return out


def research_role(role: str, max_results: int = 8) -> List[Dict]:
    """Search several job-market angles for a target role and merge/dedupe by URL."""
    queries = [
        f"{role} job required skills and qualifications 2026",
        f"{role} job description requirements LinkedIn Indeed",
        f"{role} most in-demand skills and tools hiring",
    ]
    seen, merged = set(), []
    for q in queries:
        for r in search_web(q, max_results=4):
            if r["url"] in seen:
                continue
            seen.add(r["url"])
            merged.append(r)
            if len(merged) >= max_results:
                return merged
    return merged
