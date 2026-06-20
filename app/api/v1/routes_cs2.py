"""CS2 (HLTV) API routes — mounted at /api/v1/cs2/* by app/main.py.

Phase B ships ONE endpoint: GET /api/v1/cs2/matches/results. Each subsequent
phase adds more (matches/upcoming, matches/live, rankings, events, news,
team/{id}, player/{id}, match/{id}) following the same pattern.

Pattern (mirrors app/api/v1/routes.py):
    1. Read from cache (`cache_get(key)`).
    2. If empty (cold start), trigger the refresh_cs2 refresher ONCE.
    3. Re-read from cache; if still empty, return [] (don't 500).
    4. NEVER scrape inline. The public API only reads.

Why a separate router file:
- Per the plan: "do not abstract prematurely" — no `Game = Literal[...]`
  threading through shared routes. Each game gets its own router.
- Keeps the VLR routes untouched (lower risk, easier review).
- The CS2 router can evolve independently as HLTV surfaces grow.
"""
import logging
from typing import Any

from fastapi import APIRouter

from app.core.cache import cache_get
from app.services import refresh_cs2 as R

log = logging.getLogger("cs2.routes")

router = APIRouter(prefix="/cs2", tags=["cs2"])


async def _cached_or_refresh(key: str, refresher) -> Any:
    """Read from cache; if empty (cold start), trigger a refresh once.

    Mirrors the helper in app/api/v1/routes.py. Returns [] when both reads
    fail (refresher errored or the cache layer is unreachable), so the
    endpoint never 500s on a transient scheduler hiccup.
    """
    data = await cache_get(key)
    if data is None:
        try:
            await refresher()
        except Exception as exc:
            # Log but don't propagate — the route stays useful when the
            # scheduler is mid-cycle or HLTV is briefly down. The frontend
            # already handles the {data, stale, error} envelope contract;
            # for v1 we keep the shape identical to VLR's list endpoints.
            log.warning("cs2.routes cold-start refresh failed for %s: %s", key, exc)
        data = await cache_get(key)
    return data if data is not None else []


@router.get("/matches/results")
async def results():
    """Most recent HLTV /results scrape (completed CS2 matches).

    Returns a list of match-row dicts in the shape produced by
    app.cs2.matches.parse_results (see tests/cs2/test_matches.py for the
    full schema). Empty list when the scheduler hasn't populated yet.
    """
    return await _cached_or_refresh(R.CACHE_RESULTS, R.refresh_results)


@router.get("/matches/upcoming")
async def upcoming():
    """Upcoming CS2 matches from HLTV /matches.

    Same dict shape as parse_upcoming. Filters out matches where live=True
    so this endpoint only surfaces future / unscheduled ones. The frontend
    reads /matches/upcoming for the "upcoming" tab and /matches/live for
    the live tab (the latter is always empty in v1 — see live endpoint).
    """
    # refresh_upcoming populates BOTH CACHE_UPCOMING and CACHE_LIVE; we read
    # only CACHE_UPCOMING here. A future optimization could read both lists
    # in one refresh and avoid the second cache key, but v1 keeps the split
    # so the live cache has its own TTL (30s vs 60s).
    return await _cached_or_refresh(R.CACHE_UPCOMING, R.refresh_upcoming)


@router.get("/matches/live")
async def live():
    """Live CS2 matches from HLTV.

    Returns [] in v1. HLTV renders live matches via the scorebot websocket
    on /live (data-scoreboturls on the live page), not via static HTML on
    /matches. The /matches live="true" attribute is the only static-marker
    we found, and it didn't carry any matches at our capture time. v2
    wires the scorebot websocket so this endpoint returns real data.

    The endpoint exists now so the frontend can wire to it without churn;
    it's just always empty.
    """
    return await _cached_or_refresh(R.CACHE_LIVE, R.refresh_upcoming)