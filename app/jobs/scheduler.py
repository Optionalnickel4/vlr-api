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
    sched.add_job(_tracked("results", R.refresh_results), "interval", minutes=10, id="results", max_instances=1)
    sched.add_job(_tracked("news", R.refresh_news), "interval", minutes=15, id="news", max_instances=1)
    sched.add_job(_tracked("events", R.refresh_events), "interval", hours=6, id="events", max_instances=1)
    sched.add_job(_tracked("rankings", R.refresh_rankings), "interval", hours=6, id="rankings", max_instances=1)
    _active = sched
    return sched
