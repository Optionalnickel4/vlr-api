"""Standalone scheduler process (alternative to running it inside the API).

Use this if you run the API with VLR_ENABLE_SCHEDULER=false and want scraping
in its own process (e.g. multiple uvicorn workers).

    python -m app.jobs.run
"""
import asyncio
import logging

from app.core.db import init_db
from app.core.http import aclose_client
from app.jobs.scheduler import build_scheduler

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    await init_db()
    sched = build_scheduler()
    sched.start()
    logging.getLogger("vlr.scheduler").info("scheduler started")
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        sched.shutdown()
        await aclose_client()


if __name__ == "__main__":
    asyncio.run(main())
