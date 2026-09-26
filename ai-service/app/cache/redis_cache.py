"""
Cache-aside Redis layer for the AI Service (Redis DB 1).

The cache is optional: every function fails soft. If Redis is down, callers see
a miss and fall through to Product Service / the LLM, and we stop trying Redis
for BACKOFF_SECONDS so requests don't each wait on a connect timeout.

Invalidation: every key embeds a version number (ai:v<N>:...). invalidate()
bumps the version, so all older keys stop being read at once and expire on
their own TTL. A request that read the old version before a product change
writes under that old version, so it can't put stale data in the new one.
"""
import hashlib
import json
import logging
import re
import time
from typing import Any, Optional

import redis.asyncio as redis
from prometheus_client import Counter

from app.config import settings

logger = logging.getLogger(__name__)

VERSION_KEY = "ai:cache:version"
BACKOFF_SECONDS = 30

CACHE_REQUESTS = Counter(
    "ai_cache_requests_total", "AI Service cache lookups", ["kind", "result"]  # result: hit | miss
)

_redis: Optional[redis.Redis] = None
_down_until = 0.0


def _get_redis() -> Optional[redis.Redis]:
    """Lazy-initialize the Redis client. None when the cache is disabled or Redis recently failed."""
    global _redis
    if not settings.CACHE_ENABLED or time.monotonic() < _down_until:
        return None
    if _redis is None:
        _redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
    return _redis


def _mark_down(e: Exception) -> None:
    global _down_until
    _down_until = time.monotonic() + BACKOFF_SECONDS
    logger.warning("Redis cache unavailable, bypassing for %ss: %s", BACKOFF_SECONDS, e)


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip().casefold()


async def make_key(kind: str, *parts: str) -> Optional[str]:
    """
    Build a versioned key, e.g. ai:v3:rec:<hash of normalized parts>.
    Returns None if Redis is unavailable (callers treat that as a miss).
    """
    r = _get_redis()
    if r is None:
        return None
    try:
        version = await r.get(VERSION_KEY) or "0"
    except (redis.RedisError, OSError) as e:
        _mark_down(e)
        return None
    key = f"ai:v{version}:{kind}"
    if parts:
        digest = hashlib.sha256("\x1f".join(_normalize(p) for p in parts).encode()).hexdigest()[:32]
        key += f":{digest}"
    return key


async def get_json(key: Optional[str], kind: str) -> Any:
    """Return the cached value, or None on miss / Redis failure."""
    r = _get_redis()
    if key is None or r is None:
        return None
    try:
        raw = await r.get(key)
    except (redis.RedisError, OSError) as e:
        _mark_down(e)
        return None
    if raw is None:
        CACHE_REQUESTS.labels(kind=kind, result="miss").inc()
        return None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        CACHE_REQUESTS.labels(kind=kind, result="miss").inc()
        return None
    CACHE_REQUESTS.labels(kind=kind, result="hit").inc()
    return value


async def set_json(key: Optional[str], value: Any, ttl: int) -> None:
    """Store a value with a TTL. Silently skipped if Redis is unavailable."""
    r = _get_redis()
    if key is None or r is None:
        return
    try:
        await r.set(key, json.dumps(value), ex=ttl)
    except (redis.RedisError, OSError, TypeError, ValueError) as e:
        if isinstance(e, (redis.RedisError, OSError)):
            _mark_down(e)
        else:
            logger.warning("Value for %s is not JSON-serializable, not caching: %s", key, e)


async def invalidate() -> None:
    """Invalidate every cached entry by bumping the version."""
    r = _get_redis()
    if r is None:
        return
    try:
        version = await r.incr(VERSION_KEY)
        logger.info("AI cache invalidated (now v%s)", version)
    except (redis.RedisError, OSError) as e:
        _mark_down(e)


async def close() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
