"""Orchestration: scrape vlr -> write cache -> persist history.

The API never calls these directly for live requests; the scheduler does.
API reads from cache (and DB for history).
"""
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.cache import cache_set
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models import MatchResult, PlayerSnapshot, RankingSnapshot
from app.scrapers import events as ev
from app.scrapers import matches as mt
from app.scrapers import players as pl
from app.scrapers import rankings as rk

CACHE_RESULTS = "vlr:results"
CACHE_UPCOMING = "vlr:upcoming"
CACHE_LIVE = "vlr:live"
CACHE_RANKINGS = "vlr:rankings:{region}"
CACHE_EVENTS = "vlr:events"
CACHE_NEWS = "vlr:news"
CACHE_PLAYER = "vlr:player:{id}"


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
