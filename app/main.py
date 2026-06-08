import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.routes import router as v1_router
from app.core.config import get_settings
from app.core.db import init_db
from app.jobs.scheduler import build_scheduler

logging.basicConfig(level=logging.INFO)
settings = get_settings()
_scheduler = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler
    await init_db()
    if settings.enable_scheduler:
        _scheduler = build_scheduler()
        _scheduler.start()
    yield
    if _scheduler:
        _scheduler.shutdown(wait=False)


app = FastAPI(title="vlr-api", version="0.1.0", lifespan=lifespan)
app.include_router(v1_router, prefix=settings.api_prefix)


@app.get("/health")
async def health():
    return {"status": "ok"}
