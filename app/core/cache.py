"""Redis access — the API's PRIMARY read source, not a side optimization.

Because routers may not scrape, a cache miss is a real failure mode rather than
a slow path: list endpoints serve whatever the scheduler last wrote, and only
detail endpoints (player/team/match) may refresh inline because there is
genuinely nothing else to serve. So treat eviction pressure as a correctness
concern, not a latency one.

Values are stored as JSON strings, with `default=str` on dump so datetimes
serialize instead of raising. The corollary is that a round-trip is LOSSY —
whatever went in as a datetime comes back as a string. Nothing downstream
depends on the difference today; if you start caching typed objects, that is
the assumption that will bite.

The cache KEY SCHEME lives with the code that owns each dataset, in
services/refresh.py (CACHE_* templates, all `vlr:<entity>[:<params>]`). Keeping
key construction there means a TTL and its key are decided in one place.

Two kinds of key live in this namespace:
  - `vlr:*`         cached payloads, always TTL'd
  - `vlr:lastrun:*` job heartbeats, deliberately NEVER TTL'd (see LASTRUN)
"""
import json
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as redis

from app.core.config import get_settings

_pool: redis.Redis | None = None

# Persistent (no-TTL) key recording when a scheduled job last completed OK.
LASTRUN = "vlr:lastrun:{job}"


def get_redis() -> redis.Redis:
    """The process-wide Redis client, created on first use.

    decode_responses=True so reads come back as `str` and json.loads can take
    them directly — every value in this namespace is JSON or an ISO timestamp,
    never binary.
    """
    global _pool
    if _pool is None:
        _pool = redis.from_url(get_settings().redis_url, decode_responses=True)
    return _pool


async def cache_get(key: str) -> Any | None:
    """Decoded JSON at `key`, or None on a miss.

    Unlike the status helpers below, this does NOT swallow exceptions: on the
    serving path a Redis outage should surface loudly, not be laundered into an
    indistinguishable "miss" that makes every list endpoint quietly return empty.
    """
    raw = await get_redis().get(key)
    return json.loads(raw) if raw is not None else None


async def cache_set(key: str, value: Any, ttl: int) -> None:
    """Store `value` as JSON under `key` with a REQUIRED expiry.

    ttl is not optional by design — an accidentally immortal key in this
    namespace would serve stale data forever with nothing to reveal it. The one
    intentionally persistent key is written by record_job_run, not here.
    """
    await get_redis().set(key, json.dumps(value, default=str), ex=ttl)


# ---- status dashboard read-only helpers (never raise) -----------------------
# These back the /status page, whose entire job is to report what is broken. A
# helper that raised would take down the very page you opened to diagnose the
# outage, so each degrades to None/False instead. Do NOT copy this pattern onto
# the serving path — there, silence is the bug.
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
