import json
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as redis

from app.core.config import get_settings

_pool: redis.Redis | None = None

# Persistent (no-TTL) key recording when a scheduled job last completed OK.
LASTRUN = "vlr:lastrun:{job}"


def get_redis() -> redis.Redis:
    global _pool
    if _pool is None:
        _pool = redis.from_url(get_settings().redis_url, decode_responses=True)
    return _pool


async def cache_get(key: str) -> Any | None:
    raw = await get_redis().get(key)
    return json.loads(raw) if raw is not None else None


async def cache_set(key: str, value: Any, ttl: int) -> None:
    await get_redis().set(key, json.dumps(value, default=str), ex=ttl)


# ---- status dashboard read-only helpers (never raise) -----------------------
async def record_job_run(job_name: str) -> None:
    """Record a scheduled job's successful completion. No TTL — the status page
    must be able to read 'last ran' long after the run, so this key must persist."""
    await get_redis().set(
        LASTRUN.format(job=job_name), datetime.now(timezone.utc).isoformat()
    )


async def get_last_run(job_name: str) -> str | None:
    """ISO timestamp of the job's last successful run, or None if never/unavailable."""
    try:
        return await get_redis().get(LASTRUN.format(job=job_name))
    except Exception:
        return None


async def ping() -> bool:
    """Redis reachability. False on any exception, never raises."""
    try:
        return bool(await get_redis().ping())
    except Exception:
        return False


async def cache_ttl(key: str) -> int | None:
    """Remaining TTL (seconds) for a cache key. Redis returns -2 for a missing key
    and -1 for a key with no expiry; both are reported as null. False on error."""
    try:
        ttl = await get_redis().ttl(key)
    except Exception:
        return None
    return ttl if ttl is not None and ttl >= 0 else None
