"""CS2 (HLTV) refresh orchestrator.

Parallel to app/services/refresh.py but for the CS2 source. Owns the CS2
Redis cache keys and persists completed-match rows to the cs2_match_results
history table. Never called from a public route — only the scheduler
(app/jobs/run_cs2.py in Phase B-2) and the on-demand /_cached_or_refresh
helper from the route layer invoke these.

Layering (per CLAUDE.md):
    routes (read cache/db)  ->  this module (orchestrate)
                            ->  scrapers (pure HTML parsing)
                            ->  http (cloudscraper)

Cache keys (source-named per the locked-in decision):
    hltv:results                — most recent /results scrape
    hltv:upcoming               — most recent /matches scrape (split)
    hltv:live                   — live subset of /matches scrape
    hltv:rankings:{region}      — HLTV rankings for one region (Phase C)
    hltv:events                 — events list (Phase C)
    hltv:news                   — news list (Phase C)
    hltv:team:{id}              — team profile (Phase C)
    hltv:player:{id}            — player profile (Phase C)
    hltv:match:{id}             — match detail (Phase C)

Cadences (mirror the VLR cadences per the plan):
    results  : every 10m
    upcoming : every 60s (single scrape serves both `upcoming` and `live`)
    rankings : every 6h
    events   : every 6h
    news     : every 15m
"""
import logging

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.cache import cache_set
from app.core.db import SessionLocal
from app.cs2 import matches as cs2_matches
from app.models import Cs2MatchResult

log = logging.getLogger("cs2.refresh")

CACHE_RESULTS = "hltv:results"
CACHE_UPCOMING = "hltv:upcoming"
CACHE_LIVE = "hltv:live"
CACHE_RANKINGS = "hltv:rankings:{region}"
CACHE_EVENTS = "hltv:events"
CACHE_NEWS = "hltv:news"
CACHE_TEAM = "hltv:team:{id}"
CACHE_PLAYER = "hltv:player:{id}"
CACHE_MATCH = "hltv:match:{id}"


async def refresh_results() -> int:
    """Scrape HLTV /results, cache it, and upsert into cs2_match_results.

    Returns the number of rows returned by HLTV (whether or not they were
    new in the DB — on_conflict_do_nothing keeps the table stable across
    repeated scrapes).

    TTL = 600s (10 minutes) — same cadence as VLR's results refresh. The
    TTLs will be lifted into HltvSettings.ttl_* in a later phase so the
    HLTV env file can override them without touching VLR_* vars.
    """
    data = await cs2_matches.fetch_results()
    await cache_set(CACHE_RESULTS, data, 600)
    rows = [
        {
            "hltv_id": str(m["id"]),
            "team_a": m["team_a"],
            "team_b": m["team_b"],
            "score_a": m["score_a"],
            "score_b": m["score_b"],
            "winner": m["winner"],
            "event": m["event"] or None,
            "format": m["format"] or None,
            "stars": m["stars"],
            "match_slug": m["match_slug"] or None,
            "url": m["url"],
            "unix_ms": m["unix_ms"],
        }
        for m in data
        if m.get("id") is not None
    ]
    if rows:
        async with SessionLocal() as session:
            stmt = pg_insert(Cs2MatchResult).values(rows)
            stmt = stmt.on_conflict_do_nothing(index_elements=["hltv_id"])
            await session.execute(stmt)
            await session.commit()
    log.info("cs2.refresh.results: %d rows (HLTV), %d upserted", len(data), len(rows))
    return len(data)


async def refresh_upcoming() -> dict[str, int]:
    """Scrape HLTV /matches, split into live + upcoming, cache both.

    Returns {"live": N, "upcoming": M} so the scheduler can log both counts
    in one shot. We cache upcoming with a short TTL (60s) — it changes fast
    as matches move from upcoming -> live -> completed — and live with an
    even shorter TTL (30s) when HLTV is actually rendering live matches via
    the static markup path. Today the live list is always empty (HLTV renders
    live via scorebot JS, not /matches HTML), but the cache key is wired so
    v2's scorebot integration has a drop-in cache layer.

    NOTE: this does NOT write to cs2_match_results. Upcoming matches aren't
    completed yet — they only land in the history table once /results picks
    them up after the match finishes.
    """
    data = await cs2_matches.fetch_upcoming()
    await cache_set(CACHE_UPCOMING, data["upcoming"], 60)
    await cache_set(CACHE_LIVE, data["live"], 30)
    log.info(
        "cs2.refresh.upcoming: %d upcoming + %d live",
        len(data["upcoming"]),
        len(data["live"]),
    )
    return {"live": len(data["live"]), "upcoming": len(data["upcoming"])}