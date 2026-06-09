"""Tiny, idempotent additive migrations run at startup.

create_all builds tables that don't exist yet (with their current columns), but it
NEVER alters a table that already exists — so banked history needs explicit, safe
ADD COLUMN / CREATE INDEX steps. Every statement is `IF NOT EXISTS`, so re-running
the whole list is a no-op: never drop or recreate match_results (it holds history).
"""
from __future__ import annotations

from sqlalchemy import text

# Index names match SQLAlchemy's default `ix_<table>_<column>` so a fresh create_all
# and this migration converge on the same object (no duplicate index).
_STATEMENTS: tuple[str, ...] = (
    "ALTER TABLE match_results ADD COLUMN IF NOT EXISTS team_a_id VARCHAR(32)",
    "ALTER TABLE match_results ADD COLUMN IF NOT EXISTS team_b_id VARCHAR(32)",
    "CREATE INDEX IF NOT EXISTS ix_match_results_team_a_id "
    "ON match_results (team_a_id)",
    "CREATE INDEX IF NOT EXISTS ix_match_results_team_b_id "
    "ON match_results (team_b_id)",
)


def migration_statements() -> list[str]:
    """The ordered SQL to run. Pure + deterministic so idempotency is testable
    without a DB: each statement is `IF NOT EXISTS`, so applying twice is safe."""
    return list(_STATEMENTS)


async def run_migrations(conn) -> None:
    """Apply the additive migrations on an already-open (begin) connection."""
    for stmt in migration_statements():
        await conn.execute(text(stmt))
