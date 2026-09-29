"""Redis access — the API's PRIMARY read source, not a side optimization.

List and detail endpoints can refresh inline on a miss. Rankings and events
also retain the last successful payload independently of freshness, so an
upstream outage need not turn expired data into unavailable data.

Values are stored as JSON strings, with `default=str` on dump so datetimes
serialize instead of raising. The corollary is that a round-trip is LOSSY —
whatever went in as a datetime comes back as a string. Nothing downstream
depends on the difference today; if you start caching typed objects, that is
the assumption that will bite.

The cache KEY SCHEME lives with the code that owns each dataset, in
services/refresh.py (CACHE_* templates, all `vlr:<entity>[:<params>]`). Keeping
key construction there means a TTL and its key are decided in one place.

Key families in this namespace:
  - `vlr:*`         cached payloads, always TTL'd
  - `vlr:lastrun:*` job heartbeats, deliberately NEVER TTL'd (see LASTRUN)
  - `<key>:retained` last successful rankings/events payload, no expiry
  - `<key>:refresh` distributed refresh lease or short failure backoff
"""
import asyncio
import json
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

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


async def cache_get_many(keys: list[str]) -> list[Any | None]:
    """Decode several JSON cache entries in one Redis round trip.

    The returned list is position-aligned with ``keys``.  This is used by team
    identity enrichment so a page with many rows never becomes one Redis
    request per team or match.
    """
    if not keys:
        return []
    raw_values = await get_redis().mget(keys)
    return [json.loads(raw) if raw is not None else None for raw in raw_values]


async def cache_set(key: str, value: Any, ttl: int) -> None:
    """Store `value` as JSON under `key` with a REQUIRED expiry.

    ttl is not optional: this helper always writes a freshness-limited payload.
    Persistent retained copies and job heartbeats use separate helpers below.
    """
    await get_redis().set(key, json.dumps(value, default=str), ex=ttl)


# Only rankings/events opt into retention. Existing keys keep their original
# bare JSON and freshness TTLs, including the /status TTL contract. Retained
# copies intentionally last until replaced or explicitly evicted/deleted.
REFRESH_TIMEOUT = 120
REFRESH_LEASE = 125  # longer than the bounded scrape, including throttle/retries
REFRESH_BACKOFF = 30

# Fence publication by lease ownership: a paused/expired worker must never
# overwrite a newer owner's result. Both copies and lease release are atomic.
_PUBLISH_RETAINED = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end
redis.call('SET', KEYS[2], ARGV[2], 'EX', ARGV[3])
redis.call('SET', KEYS[3], ARGV[2])
redis.call('DEL', KEYS[1])
return 1
"""
_FINISH_REFRESH = """
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end
if ARGV[2] == 'failed' then
    redis.call('SET', KEYS[1], 'failed', 'EX', ARGV[3])
else
    redis.call('DEL', KEYS[1])
end
return 1
"""


class RefreshUnavailable(Exception):
    """Refresh failed, is in progress, or is cooling down; no fabricated data."""


async def refresh_retained(
    key: str, ttl: int, fetcher: Callable[[], Awaitable[list]],
) -> tuple[list, bool]:
    """Return (payload, scraped_here), coalescing API and scheduler refreshes.

    Fresh callers skip scraping. One Redis lease owner refreshes inline; stale
    followers immediately signal the caller to use its retained copy. Cold
    followers wait for the same result, never start a second scrape. Failures
    leave both payload keys untouched and install a short shared retry backoff.
    Redis failures propagate: retention cannot promise availability without Redis.
    """
    fresh = await cache_get(key)
    if fresh is not None:
        return fresh, False

    client = get_redis()
    lease = key + ":refresh"
    token = uuid4().hex
    if not await client.set(lease, token, nx=True, ex=REFRESH_LEASE):
        if await cache_get(key + ":retained") is not None:
            raise RefreshUnavailable("Refresh already in progress or cooling down")
        try:
            async with asyncio.timeout(REFRESH_TIMEOUT):
                while True:
                    fresh = await cache_get(key)
                    if fresh is not None:
                        return fresh, False
                    state = await client.get(lease)
                    if state is None or state == "failed":
                        # Owner may have published between our two reads.
                        fresh = await cache_get(key)
                        if fresh is not None:
                            return fresh, False
                        raise RefreshUnavailable("Refresh did not produce data")
                    await asyncio.sleep(0.05)
        except TimeoutError as exc:
            raise RefreshUnavailable("Refresh wait timed out") from exc

    failed = True
    try:
        async with asyncio.timeout(REFRESH_TIMEOUT):
            # Another owner could have published between our first read and NX.
            fresh = await cache_get(key)
            if fresh is not None:
                failed = False
                return fresh, False
            data = await fetcher()
            if not isinstance(data, list):
                raise RefreshUnavailable("Refresh did not return a list")
            published = await client.eval(
                _PUBLISH_RETAINED, 3, lease, key, key + ":retained",
                token, json.dumps(data, default=str), ttl,
            )
            if not published:
                raise RefreshUnavailable("Refresh lease expired")
            failed = False
            return data, True
    except Exception as exc:
        raise RefreshUnavailable("Refresh failed") from exc
    finally:
        # Also runs on cancellation. Token check protects any replacement owner;
        # expiry recovers from a process crash or failed cleanup.
        await client.eval(
            _FINISH_REFRESH, 1, lease, token,
            "failed" if failed else "done", REFRESH_BACKOFF,
        )


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
