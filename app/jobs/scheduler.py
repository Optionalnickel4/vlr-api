import logging
from collections.abc import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.cache import record_job_run
from app.services import refresh as R

log = logging.getLogger("vlr.scheduler")

# The scheduler instance live in this process, if any. The status dashboard reads
# next_run_time off it. None when scraping runs elsewhere (VLR_ENABLE_SCHEDULER=
# false, or a separate worker) — then the status page shows last_run only.
_active: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler | None:
    return _active


def _tracked(job_name: str, fn: Callable[[], Awaitable]) -> Callable[[], Awaitable]:
    """Wrap a scheduled callable so it records its last-run timestamp on SUCCESS
    only. A raise propagates without writing the key — failures don't look fresh."""

    async def runner():
        result = await fn()
        await record_job_run(job_name)
        return result

    runner.__name__ = f"tracked_{job_name}"
    return runner


def build_scheduler() -> AsyncIOScheduler:
    global _active
    sched = AsyncIOScheduler(timezone="UTC")
    sched.add_job(_tracked("upcoming", R.refresh_upcoming), "interval", seconds=60, id="upcoming", max_instances=1)
    # live match detail: re-scrape each currently-LIVE match every 30s so the cache
    # (and the page poll that reads it) stays fresh. Bounded by the live list;
    # max_instances=1 so a slow run never overlaps. No-op when nothing is live.
    sched.add_job(_tracked("live_matches", R.refresh_live_matches), "interval", seconds=30, id="live_matches", max_instances=1)
    sched.add_job(_tracked("results", R.refresh_results), "interval", minutes=10, id="results", max_instances=1)
    sched.add_job(_tracked("news", R.refresh_news), "interval", minutes=15, id="news", max_instances=1)
    sched.add_job(_tracked("events", R.refresh_events), "interval", hours=6, id="events", max_instances=1)
    sched.add_job(_tracked("rankings", R.refresh_rankings), "interval", hours=6, id="rankings", max_instances=1)
    # player pre-scrape: twice daily at fixed wall-clock hours (cron, not interval,
    # so it lands at predictable times); max_instances=1 so a long run never overlaps.
    sched.add_job(_tracked("player_prefetch", R.prefetch_upcoming_players), "cron", hour="5,17", id="player_prefetch", max_instances=1)
    # stats leaderboard: season-aggregate player rankings (R2.0 et al) over na/eu ×
    # 4 windows. Slow cadence (6h) — these barely move and it's 8 light scrapes per
    # run; max_instances=1 so a slow run never overlaps. Records vlr:lastrun:stats.
    sched.add_job(_tracked("stats", R.refresh_all_stats), "interval", hours=6, id="stats", max_instances=1)
    _active = sched
    return sched
