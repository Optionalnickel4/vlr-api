from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
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
