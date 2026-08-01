"""SQLAlchemy history tables — the append-only record behind trends and backfill.

These tables are NOT the serving state (Redis is). Nothing here is read on the
hot path; they exist so that data which vlr.gg only ever shows as "right now"
can be charted over time, and so a team's match history survives falling off
vlr's own results feed.

Two conventions run through all four tables and explain most of the column types:

  - SNAPSHOT, don't mutate. Every write is a new row stamped with captured_at;
    nothing is ever updated in place. A trend query is therefore just an
    ordered read, and a bad scrape adds one wrong row instead of corrupting the
    series. The cost is dedup at write time (services/refresh.py), which is why
    MatchResult has a unique vlr_id and the snapshot tables are written at most
    once per TTL per entity.

  - Numbers are stored as STRINGS (rank, rating, score_a/score_b, record). vlr
    renders "1", "1234", "13", but also "–", "TBD" and occasional blanks, and
    the value we want to preserve is what vlr actually said. Coercing at write
    time would force a lossy choice on every odd value; coercing at read time
    keeps the raw record intact and lets a null degrade one chart point instead
    of failing an insert.

Rich nested data (agent stats, rosters) goes in JSONB verbatim rather than being
normalized into child tables: its shape is vlr's, it changes when vlr changes,
and no query joins into it.

⚠️ The cluster must be UTF8 or accented names silently fail to persist here —
see the warning in app/core/db.py.
"""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _now() -> datetime:
    """Timezone-AWARE UTC. Naive datetimes into a timestamptz column get
    interpreted as server-local time, which silently skews every trend."""
    return datetime.now(timezone.utc)


class MatchResult(Base):
    """A completed match, captured once. Dedup on vlr match id.

    The only non-snapshot table: a finished match is immutable, so `vlr_id` is
    UNIQUE and re-scraping the results feed (every 10 minutes, over a page that
    barely changes) is a cheap no-op instead of thousands of duplicate rows.

    Fed from two directions — the /matches/results feed and per-team backfill —
    which is why the team_id columns are nullable: the feed's cards expose no
    team ids at all, while a team-page backfill knows the page team's id but not
    the opponent's (see TEAM_MATCH_OPPONENT_LINK in scrapers/selectors.py).
    """

    __tablename__ = "match_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vlr_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    team_a: Mapped[str | None] = mapped_column(String(128))
    team_b: Mapped[str | None] = mapped_column(String(128))
    # vlr team ids per side, when known (team-page backfill always sets the page
    # team's; opponent + the /matches/results feed may be null on older rows).
    team_a_id: Mapped[str | None] = mapped_column(String(32), index=True)
    team_b_id: Mapped[str | None] = mapped_column(String(32), index=True)
    score_a: Mapped[str | None] = mapped_column(String(16))
    score_b: Mapped[str | None] = mapped_column(String(16))
    event: Mapped[str | None] = mapped_column(String(256))
    series: Mapped[str | None] = mapped_column(String(256))
    url: Mapped[str | None] = mapped_column(Text)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class RankingSnapshot(Base):
    """Team ranking captured per scrape, so you can chart rating over time.

    vlr shows only the current standings; this table is the entire reason a
    rating history exists. `region` is part of the identity, not a label — the
    world and regional ranking views assign a team different ranks, so rows must
    be filtered by region before they mean anything as a series.
    """

    __tablename__ = "ranking_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[str | None] = mapped_column(String(32), index=True)
    team: Mapped[str | None] = mapped_column(String(128))
    region: Mapped[str | None] = mapped_column(String(32), index=True)
    rank: Mapped[str | None] = mapped_column(String(16))
    rating: Mapped[str | None] = mapped_column(String(16))
    record: Mapped[str | None] = mapped_column(String(64))
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, index=True
    )


class PlayerSnapshot(Base):
    """A player's detail page captured per on-demand fetch, so agent-stat trends
    can be charted over time. The per-agent stat rows are stored as JSON verbatim.

    "On-demand" is load-bearing: unlike rankings, nothing crawls every player on
    a cadence, so a player's history starts the first time someone asks for them
    and has gaps wherever no one did. Treat the series as irregularly sampled —
    never assume evenly spaced points.

    agent_stats keeps vlr's own keys (which come from the table's header text —
    see scrapers/players.py), so a vlr header rename shows up as new keys in new
    rows while old rows keep the old ones.
    """

    __tablename__ = "player_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[str] = mapped_column(String(32), index=True)
    alias: Mapped[str | None] = mapped_column(String(128))
    real_name: Mapped[str | None] = mapped_column(String(128))
    country: Mapped[str | None] = mapped_column(String(8))
    team: Mapped[str | None] = mapped_column(String(128))
    team_id: Mapped[str | None] = mapped_column(String(32))
    agent_stats: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, index=True
    )


class TeamSnapshot(Base):
    """A team's detail page captured per on-demand fetch. Intentionally lean: roster
    churn is infrequent (vlr already logs transactions), so the value is being
    queryable/joinable against match results and ranking history — not novel data.
    Dedup is per-TTL per team so it never fills with near-identical rows."""

    __tablename__ = "team_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[str] = mapped_column(String(32), index=True)
    name: Mapped[str | None] = mapped_column(String(128))
    region: Mapped[str | None] = mapped_column(String(64))
    roster: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, index=True
    )
