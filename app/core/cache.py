import json
from typing import Any

import redis.asyncio as redis

from app.core.config import get_settings

_pool: redis.Redis | None = None


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
