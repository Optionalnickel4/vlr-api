"""Postgres engine, session factory, and startup schema setup.

Postgres holds HISTORY, not the serving state — Redis serves reads. Losing the
DB costs you trends and backfill, not the API.

⚠️ THE CLUSTER MUST BE UTF8. On a SQL_ASCII cluster, asyncpg raises
UntranslatableCharacterError the moment a row carries an accented name
("LEVIATÁN", "Türkiye", "Ričardas Lukaševičius") and those records are silently
never banked. It hides well: refreshes write the CACHE BEFORE THE DB, so reads
stay correct and a retry looks like it self-healed while history quietly loses
every non-ASCII entity. A per-database `ENCODING 'UTF8'` is NOT sufficient —
template1 inherits the cluster encoding and keeps minting broken databases.
`SHOW server_encoding;` must say UTF8. Full recovery steps are in README.md.

The engine is constructed at import, but SQLAlchemy connects lazily, so
importing this module in a test with no Postgres running is fine.
"""
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, InstrumentedAttribute

from app.core.config import get_settings

# pool_pre_ping because this runs against a long-lived local Postgres: without
# it, connections idle out overnight and the first scrape of the morning dies on
# a stale socket.
engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
# expire_on_commit=False so ORM objects stay readable after commit — the write
# paths in services/refresh.py commit and then keep using the instance.
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a session scoped to one request."""
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    """Create missing tables, then apply the additive migrations. Runs at startup.

    Schema management is deliberately this small — create_all plus a hand-rolled
    IF NOT EXISTS list — because the schema is a handful of append-only snapshot
    tables that change rarely. There is no Alembic here; if you add a column,
    add it to the model AND to app/core/migrations.py, or existing deployments
    keep the old shape (create_all never alters an existing table).
    """
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
