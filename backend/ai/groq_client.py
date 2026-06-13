import hashlib
import json
import time
from typing import AsyncIterator, List, Optional

from groq import AsyncGroq

from core.config import settings

_groq_client: Optional[AsyncGroq] = None

_CACHE: dict[str, tuple[float, str]] = {}
_CACHE_TTL = 3600.0
_CACHE_MAX = 256

PRIMARY_MODEL = "llama-3.3-70b-versatile"
FAST_MODEL = "llama-3.1-8b-instant"


def _groq() -> AsyncGroq:
    global _groq_client
    if _groq_client is None:
        _groq_client = AsyncGroq(api_key=settings.groq_api_key)
    return _groq_client


def _cache_key(model: str, messages: List[dict], temperature: float) -> str:
    raw = json.dumps(
        {"m": model, "t": temperature, "msgs": messages},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _cache_get(key: str) -> Optional[str]:
    hit = _CACHE.get(key)
    if not hit:
        return None
    exp, val = hit
    if exp < time.time():
        _CACHE.pop(key, None)
        return None
    return val


def _cache_set(key: str, val: str) -> None:
    if len(_CACHE) >= _CACHE_MAX:
        # drop oldest-ish entry
        _CACHE.pop(next(iter(_CACHE)), None)
    _CACHE[key] = (time.time() + _CACHE_TTL, val)


async def complete(
    messages: List[dict],
    *,
    model: str = PRIMARY_MODEL,
    temperature: float = 0.3,
    max_tokens: int = 1024,
    use_cache: bool = True,
) -> str:
    key = _cache_key(model, messages, temperature) if use_cache else ""
    if use_cache:
        cached = _cache_get(key)
        if cached is not None:
            return cached

    resp = await _groq().chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = resp.choices[0].message.content or ""

    if use_cache:
        _cache_set(key, content)
    return content


async def stream(
    messages: List[dict],
    *,
    model: str = PRIMARY_MODEL,
    temperature: float = 0.3,
    max_tokens: int = 1024,
) -> AsyncIterator[str]:
    resp = await _groq().chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    async for chunk in resp:
        delta = chunk.choices[0].delta.content if chunk.choices else None
        if delta:
            yield delta
