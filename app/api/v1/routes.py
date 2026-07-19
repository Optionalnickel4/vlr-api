from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app import status_meta as meta
from app.core import cache as cache_core
from app.core import db as db_core
from app.core.cache import cache_get
from app.core.http import VlrNotFound
from app.core.db import SessionLocal
from app.jobs import scheduler as sched_mod
from app.models import MatchResult, PlayerSnapshot, RankingSnapshot, TeamSnapshot
from app.ratings.dimensions import compute_dimensions
from app.services import refresh as R
from app.services import search as SR
from app.services import trends as T

router = APIRouter()

# History tables surfaced on the status page, paired with their timestamp column.
# All four models happen to use `captured_at` — wired explicitly, not assumed.
_HISTORY_MODELS = [
    (MatchResult, "match_results", MatchResult.captured_at),
    (RankingSnapshot, "ranking_snapshots", RankingSnapshot.captured_at),
    (PlayerSnapshot, "player_snapshots", PlayerSnapshot.captured_at),
    (TeamSnapshot, "team_snapshots", TeamSnapshot.captured_at),
]

# Fixed, league-wide cache keys only (real namespaced strings; name + TTL never a
# value). On-demand per-team/per-player keys are intentionally NOT enumerated.
_CACHE_KEYS = [
    R.CACHE_RESULTS,
    R.CACHE_UPCOMING,
    R.CACHE_LIVE,
    R.CACHE_RANKINGS.format(region="all"),
    R.CACHE_EVENTS,
    R.CACHE_NEWS,
]


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
    # /stats validates region against an allow-list to prevent bogus values
    # making the scheduled scrape loop forever. Mirror that here: vlr serves
    # a known set of regional slugs, anything else 400s before we cache.
    if region not in R.RANKINGS_REGIONS:
        raise HTTPException(
            400, f"region must be one of {list(R.RANKINGS_REGIONS)}"
        )
    key = R.CACHE_RANKINGS.format(region=region)
    return await _cached_or_refresh(key, lambda: R.refresh_rankings(region))


@router.get("/stats")
async def stats(
    region: str = Query("na"),
    timespan: str = Query("all"),
    min_rnd: int = Query(0, ge=0, le=100000),
):
    """Phase 12: region-wide player leaderboard (VLR R2.0 headline). Reads cache
    only (the scheduler's `stats` job warms every combo); a cold-start miss
    triggers a single-combo refresh, then re-reads. Returns the {data, stale,
    error} envelope — never 500s. `min_rnd` optionally drops tiny-sample players
    (VLR's list already filters, so it's off by default)."""
    region = region.lower()
    if region not in R.STATS_REGIONS:
        raise HTTPException(400, f"region must be one of {list(R.STATS_REGIONS)}")
    if timespan not in R.STATS_TIMESPANS:
        raise HTTPException(400, f"timespan must be one of {list(R.STATS_TIMESPANS)}")

    key = R.CACHE_STATS.format(region=region, timespan=timespan)
    data = await cache_get(key)
    stale = False
    error = None
    if data is None:
        try:
            await R.refresh_stats(region, timespan)
            data = await cache_get(key)
        except Exception as exc:
            error, stale = str(exc), True

    rows = data or []
    if min_rnd > 0:
        rows = [r for r in rows if (r.get("rnd") or 0) >= min_rnd]
    return {"data": rows, "stale": stale, "error": error}


@router.get("/events")
async def events():
    return await _cached_or_refresh(R.CACHE_EVENTS, R.refresh_events)


@router.get("/news")
async def news():
    return await _cached_or_refresh(R.CACHE_NEWS, R.refresh_news)


# ---- dimension-split rating (Phase 13: pure percentile computation over cohort) ----
@router.get("/players/{player_id}/dimensions")
async def player_dimensions(
    player_id: str,
    region: str = Query("na"),
    timespan: str = Query("all"),
):
    """Four-dimension rating breakdown (Firepower/Entry/Consistency/Clutch) as
    0-100 cohort percentiles over the same region+timespan leaderboard /stats uses.
    Never scrapes inline — reads the cached cohort (single-combo refresh on a cold
    miss, exactly like /stats). Returns 404 when the player isn't in that cohort."""
    region = region.lower()
    if region not in R.STATS_REGIONS:
        raise HTTPException(400, f"region must be one of {list(R.STATS_REGIONS)}")
    if timespan not in R.STATS_TIMESPANS:
        raise HTTPException(400, f"timespan must be one of {list(R.STATS_TIMESPANS)}")

    key = R.CACHE_STATS.format(region=region, timespan=timespan)
    cohort = await cache_get(key)
    if cohort is None:
        try:
            await R.refresh_stats(region, timespan)
            cohort = await cache_get(key)
        except Exception as exc:
            raise HTTPException(503, f"cohort unavailable: {exc}")

    # Empty or partial cohort may reflect a mid-rewarm window where the scheduler
    # is repopulating the key. Recompute once and retry before concluding 404.
    player_row = next(
        (r for r in (cohort or []) if str(r.get("player_id")) == str(player_id)), None
    )
    if not cohort or player_row is None:
        try:
            await R.refresh_stats(region, timespan)
            refreshed = await cache_get(key)
            if refreshed:
                cohort = refreshed
        except Exception:
            pass
        if not cohort:
            raise HTTPException(503, "cohort unavailable")
        player_row = next(
            (r for r in cohort if str(r.get("player_id")) == str(player_id)), None
        )
        if player_row is None:
            raise HTTPException(
                404, f"player {player_id} not found in {region}/{timespan} leaderboard"
            )

    dims = compute_dimensions(player_row, cohort)
    return {"player_id": player_id, "region": region, "timespan": timespan, **dims}


# ---- player search (DB-first; VLR autocomplete only on a DB miss, cached) -----
@router.get("/players")
async def players(q: str = Query("", max_length=64)):
    # The service reads PlayerSnapshot (clean DB read) and only touches VLR's
    # typeahead on a DB miss, caching that like the detail endpoints. Returns the
    # { data, stale, error } envelope; never raises (graceful-empty on failure).
    return await SR.search_players(q)


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
        try:
            data = await R.refresh_team(team_id)
        except VlrNotFound:
            # Bug A: an id vlr.gg has no page for used to 500 (unhandled
            # raise_for_status). Return a clean 404 so the frontend's graceful
            # "couldn't load this team" path gets a proper signal.
            raise HTTPException(status_code=404, detail=f"team {team_id} not found")
    return data


# ---- match detail (on-demand: scrape-on-miss, cache; no history snapshot) ----
@router.get("/match/{match_id}")
async def match(match_id: str):
    data = await cache_get(R.CACHE_MATCH.format(id=match_id))
    if data is None:
        try:
            data = await R.refresh_match(match_id)
        except VlrNotFound:
            raise HTTPException(status_code=404, detail=f"match {match_id} not found")
    return data


# ---- trends (analytics over banked history; reads ranking_snapshots + match_results) ----
@router.get("/trends/team/{team_id}")
async def trends_team(team_id: str, days: int = Query(90, ge=1, le=365)):
    return await T.team_trend(team_id, days)


@router.get("/trends/player/{player_id}")
async def trends_player(player_id: str, days: int = Query(90, ge=1, le=365)):
    # Phase 8: rating/ACS trend over banked PlayerSnapshot history. No snapshots at
    # all for this id -> clean 404 (mirrors /history/player; never a 500). Snapshots
    # present but thin/young -> a valid empty series, no crash.
    resp = await T.player_trend(player_id, days)
    if resp is None:
        raise HTTPException(status_code=404, detail=f"no snapshot history for player {player_id}")
    return resp


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


# ---- status (Phase 6: read-only health + progress; never scrapes) -----------
async def build_status() -> dict[str, Any]:
    """Assemble the status payload from read-only core helpers + committed metadata.

    Strictly read-only: it never calls a refresh_/scraper/service-orchestration
    function. Every external touch is defensive — one bad table or a down backend
    degrades a field to null/false, it never 500s the endpoint.
    """
    # postgres: baseline SELECT 1, then per-table counts. A failing table both
    # nulls its own row and flips the postgres check.
    pg_ok = await db_core.check_db()
    history: list[dict[str, Any]] = []
    for model, label, ts_col in _HISTORY_MODELS:
        try:
            rows, newest = await db_core.count_and_newest(model, ts_col)
        except Exception:
            rows, newest, pg_ok = None, None, False
        history.append({"table": label, "rows": rows, "newest": newest})

    redis_ok = await cache_core.ping()
    cache_keys = [
        {"key": key, "ttl": await cache_core.cache_ttl(key)} for key in _CACHE_KEYS
    ]

    sched = sched_mod.get_scheduler()
    scheduler: list[dict[str, Any]] = []
    for job in meta.JOBS:
        next_run = None
        if sched is not None:
            j = sched.get_job(job)
            if j is not None and j.next_run_time is not None:
                next_run = j.next_run_time.isoformat()
        scheduler.append(
            {
                "job": job,
                "last_run": await cache_core.get_last_run(job),
                "next_run": next_run,
            }
        )

    return {
        "service": "vlr-api",
        "commit": meta.COMMIT,
        "deploy": meta.DEPLOY,
        "checks": {"postgres": pg_ok, "redis": redis_ok},
        "history": history,
        "cache_keys": cache_keys,
        "scheduler": scheduler,
    }


@router.get("/status")
async def status():
    return await build_status()
