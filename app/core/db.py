from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, InstrumentedAttribute

from app.core.config import get_settings

engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    from app import models  # noqa: F401 ensure models imported
    from app.core.migrations import run_migrations

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # additive, idempotent: brings pre-existing tables up to the current shape
        # (new nullable id columns) without touching banked rows.
        await run_migrations(conn)


# ---- status dashboard read-only helpers -------------------------------------
async def check_db() -> bool:
    """Postgres reachability. SELECT 1; False on any exception, never raises."""
    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def count_and_newest(
    model: Any, ts_col: InstrumentedAttribute
) -> tuple[int, str | None]:
    """Row count and newest timestamp for one history table, in a single query.

    Raises on db failure — the caller wraps per-table so one bad table reports
    null/null rather than 500-ing the whole status endpoint.
    """
    async with SessionLocal() as session:
        cnt, newest = (await session.execute(select(func.count(), func.max(ts_col)))).one()
    return int(cnt), (newest.isoformat() if newest is not None else None)
