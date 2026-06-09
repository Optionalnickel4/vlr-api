from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.core.cache import cache_get
from app.core.db import SessionLocal
from app.models import MatchResult, PlayerSnapshot, RankingSnapshot, TeamSnapshot
from app.services import refresh as R
from app.services import trends as T

router = APIRouter()


async def _cached_or_refresh(key: str, refresher) -> Any:
    """Read from cache; if empty (cold start), trigger a refresh once."""
    data = await cache_get(key)
    if data is None:
        await refresher()
        data = await cache_get(key)
    return data if data is not None else []


@router.get("/matches/results")
async def results():
    return await _cached_or_refresh(R.CACHE_RESULTS, R.refresh_results)


@router.get("/matches/upcoming")
async def upcoming():
    return await _cached_or_refresh(R.CACHE_UPCOMING, R.refresh_upcoming)


@router.get("/matches/live")
async def live():
    return await _cached_or_refresh(R.CACHE_LIVE, R.refresh_upcoming)


@router.get("/rankings")
async def rankings(region: str = Query("all")):
    key = R.CACHE_RANKINGS.format(region=region)
    return await _cached_or_refresh(key, lambda: R.refresh_rankings(region))


@router.get("/events")
async def events():
    return await _cached_or_refresh(R.CACHE_EVENTS, R.refresh_events)


@router.get("/news")
async def news():
    return await _cached_or_refresh(R.CACHE_NEWS, R.refresh_news)


# ---- player detail (on-demand: scrape-on-miss, cache, persist a snapshot) ----
@router.get("/player/{player_id}")
async def player(player_id: str):
    data = await cache_get(R.CACHE_PLAYER.format(id=player_id))
    if data is None:
        data = await R.refresh_player(player_id)
    return data


# ---- team detail (on-demand: scrape-on-miss, cache, persist a snapshot) ----
@router.get("/team/{team_id}")
async def team(team_id: str):
    data = await cache_get(R.CACHE_TEAM.format(id=team_id))
    if data is None:
        data = await R.refresh_team(team_id)
    return data


# ---- trends (analytics over banked history; reads ranking_snapshots + match_results) ----
@router.get("/trends/team/{team_id}")
async def trends_team(team_id: str, days: int = Query(90, ge=1, le=365)):
    return await T.team_trend(team_id, days)


# ---- history (from Postgres) ----
@router.get("/history/results")
async def history_results(limit: int = Query(50, le=500)):
    async with SessionLocal() as session:
        rows = await session.execute(
            select(MatchResult).order_by(MatchResult.captured_at.desc()).limit(limit)
        )
        return [
            {
                "vlr_id": r.vlr_id, "team_a": r.team_a, "team_b": r.team_b,
                "score_a": r.score_a, "score_b": r.score_b,
                "event": r.event, "series": r.series, "url": r.url,
                "captured_at": r.captured_at,
            }
            for r in rows.scalars().all()
        ]


@router.get("/history/rankings/{team_id}")
async def history_rankings(team_id: str, limit: int = Query(100, le=1000)):
    async with SessionLocal() as session:
        rows = await session.execute(
            select(RankingSnapshot)
            .where(RankingSnapshot.team_id == team_id)
            .order_by(RankingSnapshot.captured_at.asc())
            .limit(limit)
        )
        snaps = rows.scalars().all()
        if not snaps:
            raise HTTPException(404, "no ranking history for that team_id")
        return [
            {"rank": s.rank, "rating": s.rating, "record": s.record,
             "region": s.region, "captured_at": s.captured_at}
            for s in snaps
        ]


@router.get("/history/player/{player_id}")
async def history_player(player_id: str, limit: int = Query(100, le=1000)):
    async with SessionLocal() as session:
        rows = await session.execute(
            select(PlayerSnapshot)
            .where(PlayerSnapshot.player_id == player_id)
            .order_by(PlayerSnapshot.captured_at.asc())
            .limit(limit)
        )
        snaps = rows.scalars().all()
        if not snaps:
            raise HTTPException(404, "no snapshots for that player_id")
        return [
            {"alias": s.alias, "real_name": s.real_name, "team": s.team,
             "team_id": s.team_id, "country": s.country,
             "agent_stats": s.agent_stats, "captured_at": s.captured_at}
            for s in snaps
        ]


@router.get("/history/team/{team_id}")
async def history_team(team_id: str, limit: int = Query(100, le=1000)):
    async with SessionLocal() as session:
        rows = await session.execute(
            select(TeamSnapshot)
            .where(TeamSnapshot.team_id == team_id)
            .order_by(TeamSnapshot.captured_at.asc())
            .limit(limit)
        )
        snaps = rows.scalars().all()
        if not snaps:
            raise HTTPException(404, "no snapshots for that team_id")
        return [
            {"name": s.name, "region": s.region, "roster": s.roster,
             "captured_at": s.captured_at}
            for s in snaps
        ]
