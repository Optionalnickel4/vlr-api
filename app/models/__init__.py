from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MatchResult(Base):
    """A completed match, captured once. Dedup on vlr match id."""

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
    """Team ranking captured per scrape, so you can chart rating over time."""

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
    can be charted over time. The per-agent stat rows are stored as JSON verbatim."""

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


class Cs2MatchResult(Base):
    """A completed CS2 (HLTV) match, captured once. Dedup on hltv match id.

    Parallel to MatchResult but for the CS2 source. Tablename is
    `cs2_match_results` so it's clearly separable in psql / metrics dashboards
    from the VLR `match_results` table. Columns mirror VLR where the semantics
    overlap (team_a, team_b, score_a, score_b, event, url) and add CS2-specific
    fields where the markup gave us extras (format, stars, unix_ms).
    """

    __tablename__ = "cs2_match_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    hltv_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    team_a: Mapped[str | None] = mapped_column(String(128))
    team_b: Mapped[str | None] = mapped_column(String(128))
    score_a: Mapped[int | None] = mapped_column(Integer)
    score_b: Mapped[int | None] = mapped_column(Integer)
    winner: Mapped[str | None] = mapped_column(String(8))  # "team_a" | "team_b"
    event: Mapped[str | None] = mapped_column(String(256))
    format: Mapped[str | None] = mapped_column(String(8))  # "bo1" | "bo3" | "bo5"
    stars: Mapped[int | None] = mapped_column(Integer)  # HLTV importance 0-5
    match_slug: Mapped[str | None] = mapped_column(String(256))
    url: Mapped[str | None] = mapped_column(Text)
    unix_ms: Mapped[int | None] = mapped_column(
        Integer, index=True
    )  # match start time, ms since epoch
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, index=True
    )