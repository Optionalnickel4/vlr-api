"""LXC 221 preview only: live API inputs, isolated prediction records."""
import asyncio

from app.core.cache import get_redis
from app.core.config import get_settings
from app.core.http import aclose_client
from app.services import predictions, refresh


async def main():
    settings = get_settings()
    if (settings.redis_url != "redis://127.0.0.1:6381/0"
            or not settings.database_url.endswith("/vlr_predictions_preview")):
        raise RuntimeError("This runner requires isolated preview storage")
    target = get_redis()
    try:
        upcoming = await predictions._live_api("/matches/upcoming")
        if not isinstance(upcoming, list) or any(not isinstance(row, dict) for row in upcoming):
            raise RuntimeError("Live API upcoming response is invalid")
        from app.core.cache import cache_set
        await cache_set(refresh.CACHE_UPCOMING, upcoming, 90)
        # Timer refreshes display data each minute; inference at most every 10m.
        generated = 0
        if await target.set("vlr:preview:prediction-window", "1", nx=True, ex=600):
            generated = await predictions.refresh_predictions()
        print(f"Loaded {len(upcoming)} live API fixtures; published {generated} preview analyses.")
    finally:
        await aclose_client()


if __name__ == "__main__":
    asyncio.run(main())
