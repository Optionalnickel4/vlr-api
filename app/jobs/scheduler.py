import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.services import refresh as R

log = logging.getLogger("vlr.scheduler")


def build_scheduler() -> AsyncIOScheduler:
    sched = AsyncIOScheduler(timezone="UTC")
    sched.add_job(R.refresh_upcoming, "interval", seconds=60, id="upcoming", max_instances=1)
    sched.add_job(R.refresh_results, "interval", minutes=10, id="results", max_instances=1)
    sched.add_job(R.refresh_news, "interval", minutes=15, id="news", max_instances=1)
    sched.add_job(R.refresh_events, "interval", hours=6, id="events", max_instances=1)
    sched.add_job(R.refresh_rankings, "interval", hours=6, id="rankings", max_instances=1)
    return sched
