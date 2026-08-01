"""FastAPI application wiring — the process entry point (`uvicorn app.main:app`).

Deliberately thin: build the app, mount the routers, and own process lifetime.
All behaviour lives in the layers below.

Mounted surface:
    /api/v1/*   the JSON API (app/api/v1/routes.py) — reads cache/DB, never scrapes
    /, /status  a self-contained HTML dashboard (app/api/status_html.py)
    /health     unauthenticated liveness for systemd/uptime checks

Note there is no CORS middleware. The frontend never calls this service from the
browser — its Next.js route handlers proxy server-side (frontend/src/app/api/*),
so the API only ever needs to answer same-host requests and can stay unexposed.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.status_html import router as status_html_router
from app.api.v1.routes import router as v1_router
from app.core.config import get_settings
from app.core.db import init_db
from app.core.http import aclose_client
from app.jobs.scheduler import build_scheduler

logging.basicConfig(level=logging.INFO)
settings = get_settings()
_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown: schema, scheduler, and the shared HTTP client.

    init_db runs BEFORE the scheduler starts — the first cron tick can fire
    almost immediately, and it will try to write history into tables that must
    already exist.

    Teardown is in `finally` so it runs even on a failed startup. The scheduler
    is stopped with wait=False: a job mid-scrape is holding the politeness lock
    and could block shutdown for seconds, and losing one cycle costs nothing
    (the next run re-scrapes the same pages). aclose_client releases the shared
    httpx client's connection pool, which otherwise leaks on reload.
    """
    global _scheduler
    await init_db()
    if settings.enable_scheduler:
        _scheduler = build_scheduler()
        _scheduler.start()
    try:
        yield
    finally:
        if _scheduler:
            _scheduler.shutdown(wait=False)
        await aclose_client()


app = FastAPI(title="vlr-api", version="0.1.0", lifespan=lifespan)
app.include_router(v1_router, prefix=settings.api_prefix)
# status dashboard HTML at the root (no api prefix): GET / and GET /status
app.include_router(status_html_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
