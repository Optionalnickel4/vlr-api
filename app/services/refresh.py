"""Orchestration: scrape vlr -> write cache -> persist history.

The API never calls these directly for live requests; the scheduler does.
API reads from cache (and DB for history).
"""
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.cache import cache_set
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models import MatchResult, PlayerSnapshot, RankingSnapshot, TeamSnapshot
from app.scrapers import events as ev
from app.scrapers import matches as mt
from app.scrapers import players as pl
from app.scrapers import rankings as rk
from app.scrapers import teams as te

CACHE_RESULTS = "vlr:results"
CACHE_UPCOMING = "vlr:upcoming"
CACHE_LIVE = "vlr:live"
CACHE_RANKINGS = "vlr:rankings:{region}"
CACHE_EVENTS = "vlr:events"
CACHE_NEWS = "vlr:news"
CACHE_PLAYER = "vlr:player:{id}"
CACHE_TEAM = "vlr:team:{id}"


async def refresh_results() -> int:
    s = get_settings()
    data = await mt.fetch_results()
    await cache_set(CACHE_RESULTS, data, s.ttl_results)
    # persist completed matches (idempotent upsert on vlr_id)
    rows = [
        {
            "vlr_id": m["id"],
            "team_a": (m["teams"] or [None, None])[0],
            "team_b": (m["teams"] + [None, None])[1] if len(m["teams"]) > 1 else None,
            "score_a": (m["scores"] or [None, None])[0] if m["scores"] else None,
            "score_b": m["scores"][1] if len(m["scores"]) > 1 else None,
            "event": m["event"],
            "series": m["series"],
            "url": m["url"],
        }
        for m in data
        if m["id"]
    ]
    if rows:
        async with SessionLocal() as session:
            stmt = pg_insert(MatchResult).values(rows)
            stmt = stmt.on_conflict_do_nothing(index_elements=["vlr_id"])
            await session.execute(stmt)
            await session.commit()
    return len(data)


async def refresh_upcoming() -> int:
    s = get_settings()
    split = await mt.fetch_upcoming()
    await cache_set(CACHE_LIVE, split["live"], s.ttl_live)
    await cache_set(CACHE_UPCOMING, split["upcoming"], s.ttl_results)
    return len(split["live"]) + len(split["upcoming"])


async def refresh_rankings(region: str = "all") -> int:
    s = get_settings()
    data = await rk.fetch_rankings(region)
    await cache_set(CACHE_RANKINGS.format(region=region), data, s.ttl_rankings)
    snaps = [
        RankingSnapshot(
            team_id=r["team_id"], team=r["team"], region=region,
            rank=r["rank"], rating=r["rating"], record=r["record"],
        )
        for r in data if r["team"]
    ]
    if snaps:
        async with SessionLocal() as session:
            session.add_all(snaps)
            await session.commit()
    return len(data)


async def refresh_events() -> int:
    s = get_settings()
    data = await ev.fetch_events()
    await cache_set(CACHE_EVENTS, data, s.ttl_events)
    return len(data)


async def refresh_news() -> int:
    s = get_settings()
    data = await ev.fetch_news()
    await cache_set(CACHE_NEWS, data, s.ttl_news)
    return len(data)


async def refresh_player(player_id: str) -> dict[str, Any]:
    """On-demand: scrape a player detail page, cache it, and persist a snapshot.

    Detail pages are not scheduled — this runs on a cache miss from the route.
    Each scrape writes one PlayerSnapshot so agent-stat trends can be charted.
    """
    s = get_settings()
    data = await pl.fetch_player(player_id)
    await cache_set(CACHE_PLAYER.format(id=player_id), data, s.ttl_players)
    snap = PlayerSnapshot(
        player_id=str(player_id),
        alias=data.get("alias"),
        real_name=data.get("real_name"),
        country=data.get("country"),
        team=data.get("team"),
        team_id=data.get("team_id"),
        agent_stats=data.get("agent_stats") or [],
    )
    async with SessionLocal() as session:
        session.add(snap)
        await session.commit()
    return data


def _split_score(raw: Any) -> tuple[str | None, str | None]:
    """Split a raw 'a:b' score into its two raw halves (no numeric coercion here —
    that stays a read-time concern in trends). Malformed -> (None, None), no crash."""
    if raw is None or ":" not in str(raw):
        return None, None
    a, _, b = str(raw).partition(":")
    return (a.strip() or None), (b.strip() or None)


def team_results_to_match_rows(
    team_id: str | None, team_name: str | None, results: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Pure: shape a team page's parsed completed results into match_results rows.

    The page's own team is side A and ALWAYS carries its id (that's what makes the
    id-preferred trend join work); the opponent is side B with the id from its href
    when the card exposed one, else null. Scores are kept as raw text, split on the
    'a:b' separator. Rows without a vlr match id are dropped (can't dedup them)."""
    rows: list[dict[str, Any]] = []
    for m in results:
        if not m.get("id"):
            continue
        score_a, score_b = _split_score(m.get("score"))
        rows.append(
            {
                "vlr_id": m["id"],
                "team_a": team_name,
                "team_b": m.get("opponent"),
                "team_a_id": str(team_id) if team_id is not None else None,
                "team_b_id": m.get("opponent_id"),
                "score_a": score_a,
                "score_b": score_b,
                "event": m.get("event"),
                "series": None,
                "url": m.get("url"),
            }
        )
    return rows


async def refresh_team(team_id: str) -> dict[str, Any]:
    """On-demand: scrape a team detail page, cache it, persist a snapshot, and
    backfill the team's completed results into match_results.

    Detail pages are not scheduled — this runs on a cache miss from the route.
    Dedup is per-TTL per team: a snapshot is written only if none has landed for
    this team inside the teams TTL window, so repeat fetches never duplicate rows.
    The match backfill dedups on vlr_id (on_conflict_do_nothing), so re-fetching a
    team never duplicates its matches — and it fills the gap where a tier-1 team's
    real games almost never surface in the rolling global /matches/results feed.
    """
    s = get_settings()
    data = await te.fetch_team(team_id)
    await cache_set(CACHE_TEAM.format(id=team_id), data, s.ttl_teams)

    match_rows = team_results_to_match_rows(
        data.get("id"), data.get("name"), data.get("results") or []
    )
    if match_rows:
        async with SessionLocal() as session:
            stmt = pg_insert(MatchResult).values(match_rows)
            stmt = stmt.on_conflict_do_nothing(index_elements=["vlr_id"])
            await session.execute(stmt)
            await session.commit()

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=s.ttl_teams)
    async with SessionLocal() as session:
        recent = await session.execute(
            select(TeamSnapshot.id)
            .where(TeamSnapshot.team_id == str(team_id))
            .where(TeamSnapshot.captured_at >= cutoff)
            .limit(1)
        )
        if recent.first() is None:
            session.add(
                TeamSnapshot(
                    team_id=str(team_id),
                    name=data.get("name"),
                    region=data.get("country"),
                    roster=data.get("roster") or [],
                )
            )
            await session.commit()
    return data
