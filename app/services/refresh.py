"""Orchestration: scrape vlr -> write cache -> persist history.

The one place that is allowed to scrape. Everything above it reads; everything
below it parses. If you are adding a new dataset, it gets a refresh_* here, a
CACHE_* key, a TTL in core/config.py, and (if scheduled) a job in app/jobs.

CACHE IS WRITTEN BEFORE THE DB, ALWAYS. The cache is what serves requests, so
getting fresh data in front of readers takes priority over banking it. The
consequence is worth internalizing: a DB write that fails is INVISIBLE to
readers — the API keeps serving correct, fresh data while history silently stops
accumulating. That is exactly how the SQL_ASCII encoding trap hides (see
app/core/db.py), and it is why the /status page reports row counts per table
rather than trusting that "the API works" means writes are landing.

TWO TRIGGERS, one module:
  - SCHEDULED (app/jobs/scheduler.py) — the list endpoints. results, upcoming,
    live matches, news, events, rankings, stats. These keep the cache warm so a
    request never has to scrape.
  - ON-DEMAND (called by a router on a cache miss) — the detail endpoints.
    refresh_player, refresh_team, refresh_match. There is no cadence that could
    cover every player and team on vlr.gg, so a cold detail page pays for one
    scrape. This is the deliberate exception to "the API never scrapes"; it is
    bounded by the TTL and by the politeness throttle in core/http.py.
  - The exception to the exception: prefetch_upcoming_players walks the next
    ~48h of fixtures on a schedule so trend history accumulates before anyone
    asks. See its docstring for the cache gate that keeps it from duplicating
    snapshots.

HISTORY WRITES AND THEIR DEDUP (all append-only — see app/models):
  match_results     <- refresh_results, refresh_team. Dedup: UNIQUE vlr_id via
                       ON CONFLICT DO NOTHING, so re-scraping is a cheap no-op.
  ranking_snapshots <- refresh_rankings. NO dedup by design — every scrape is a
                       new point; that IS the time series.
  player_snapshots  <- refresh_player. NO internal dedup: every call writes a
                       row. Callers must gate on the cache (see the prefetch job).
  team_snapshots    <- refresh_team. Dedup: skip if a row for this team landed
                       inside ttl_teams, since rosters barely change.

Return values are counts/summaries for the scheduler's logs, not data — nothing
reads them for correctness.
"""
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.cache import cache_get, cache_set
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.models import MatchResult, PlayerSnapshot, RankingSnapshot, TeamSnapshot
from app.scrapers import events as ev
from app.scrapers import match_detail as md
from app.scrapers import matches as mt
from app.scrapers import players as pl
from app.scrapers import rankings as rk
from app.scrapers import stats as st
from app.scrapers import teams as te

log = logging.getLogger("vlr.refresh")

# Cache keys. Scheme: "vlr:<entity>[:<discriminator>...]". Every parameter that
# changes the payload MUST be in the key — region and timespan below are there
# because /stats?region=eu and ?region=na are different datasets, not different
# views of one. Templates (not f-strings at the call site) so the key for a
# dataset is defined once, next to the TTL that governs it.
CACHE_RESULTS = "vlr:results"
CACHE_UPCOMING = "vlr:upcoming"
CACHE_LIVE = "vlr:live"
CACHE_RANKINGS = "vlr:rankings:{region}"
CACHE_EVENTS = "vlr:events"
CACHE_NEWS = "vlr:news"
CACHE_PLAYER = "vlr:player:{id}"
CACHE_TEAM = "vlr:team:{id}"
CACHE_MATCH = "vlr:match:{id}"
CACHE_STATS = "vlr:stats:{region}:{timespan}"

# vlr only serves regional leaderboards for an explicit region — a value-less
# region (World) 500s — so we scrape na/eu × the four windows and no more.
STATS_REGIONS = ("na", "eu")
STATS_TIMESPANS = ("30d", "60d", "90d", "all")

# vlr.gg ranking slugs (/rankings/<region>; "all" is the bare /rankings page).
# Unknown slugs 404 upstream, and the route triggers an inline refresh on a
# cache miss — so a bogus ?region= would otherwise keep failing against vlr on
# every request. The route rejects anything not listed here.
RANKINGS_REGIONS = (
    "all", "north-america", "europe", "brazil", "asia-pacific", "korea",
    "china", "japan", "la-s", "la-n", "oceania", "gc", "mena", "collegiate",
)


async def refresh_results() -> int:
    """Scheduled (10m): cache the completed-results feed and bank new matches.

    The rolling feed only shows the most recent ~50 matches globally, so this is
    a sampling of history, not a complete one — a busy day can push a tier-1
    series off the feed between ticks. refresh_team's backfill is what fills
    those gaps for teams anyone actually looks at.

    Rows here carry NO team ids: the results cards expose only names (see
    scrapers/matches.py), which is why the trend join has a name-matching
    fallback for id-less rows.
    """
    s = get_settings()
    data = await mt.fetch_results()
    await cache_set(CACHE_RESULTS, data, s.ttl_results)
    # persist completed matches (idempotent upsert on vlr_id)
    # The index juggling below is defensive, not decorative: `teams`/`scores` are
    # whatever the card had, and a malformed or in-progress card can yield fewer
    # than 2 of either. Banking a partial row beats dropping the match.
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
    """Scheduled (60s): ONE /matches scrape feeding TWO caches at different TTLs.

    The live list gets ttl_live (~30s) because a match starting or ending changes
    it; the upcoming list gets the longer ttl_results because a fixture list days
    out doesn't move. Splitting the TTLs rather than the scrape is the point —
    the same page serves both, so a shorter TTL on `live` costs nothing extra
    upstream. Note ttl_live is shorter than this job's 60s cadence, so the live
    key can briefly expire between ticks; refresh_live_matches repopulates it
    rather than skipping a cycle.
    """
    s = get_settings()
    split = await mt.fetch_upcoming()
    await cache_set(CACHE_LIVE, split["live"], s.ttl_live)
    await cache_set(CACHE_UPCOMING, split["upcoming"], s.ttl_results)
    return len(split["live"]) + len(split["upcoming"])


async def refresh_rankings(region: str = "all") -> int:
    """Scheduled (6h, "all") + on-demand per region: cache standings, bank a snapshot.

    Every run appends a fresh row per team — no dedup, because the whole point is
    the time series. That makes this the one job whose history grows unbounded
    with cadence, so the 6h interval is a storage decision as much as a
    politeness one.

    Note the scheduler only runs the default "all" region; other regions are
    banked only when someone requests them (the route refreshes on a cache miss),
    so regional series are as sparse as their traffic.
    """
    s = get_settings()
    data = await rk.fetch_rankings(region)
    await cache_set(CACHE_RANKINGS.format(region=region), data, s.ttl_rankings)
    # Unnamed rows are parse debris (a layout row, or a selector that half-broke);
    # banking them would put nameless points in the series forever.
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


async def refresh_stats(region: str = "na", timespan: str = "all") -> int:
    """Scrape one region×timespan leaderboard and cache it (no history table —
    the leaderboard is a point-in-time aggregate view, like rankings' cache)."""
    s = get_settings()
    data = await st.fetch_stats(region, timespan)
    await cache_set(CACHE_STATS.format(region=region, timespan=timespan), data, s.ttl_stats)
    return len(data)


async def refresh_all_stats() -> int:
    """Scheduled (~6h): warm every region×timespan leaderboard combo. Season-
    aggregate stats barely move, so the cadence is slow and polite (8 light
    scrapes per run). A failure on one combo is logged and skipped, never
    aborting the rest. Returns the total rows written across all combos."""
    total = 0
    for region in STATS_REGIONS:
        for timespan in STATS_TIMESPANS:
            try:
                total += await refresh_stats(region, timespan)
            except Exception:
                log.warning("refresh_stats: failed for %s/%s", region, timespan, exc_info=True)
    log.info("refresh_all_stats: cached %d leaderboard rows across %d combos",
             total, len(STATS_REGIONS) * len(STATS_TIMESPANS))
    return total


async def refresh_player(player_id: str) -> dict[str, Any]:
    """On-demand: scrape a player detail page, cache it, and persist a snapshot.

    Detail pages are not scheduled — this runs on a cache miss from the route.
    Each scrape writes one PlayerSnapshot so agent-stat trends can be charted.

    ⚠️ There is NO dedup here: every call appends a snapshot row. That is correct
    for the route (a cache miss means ttl_players has elapsed, so the point is
    genuinely new), but it makes this function unsafe to call in a loop. Any
    batch caller must gate on the cache first — see prefetch_upcoming_players.
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


async def refresh_match(match_id: str) -> dict[str, Any]:
    """On-demand (route) + scheduled (live-refresh job): scrape a match-detail page
    and cache it. No history table — match detail is a point-in-time view.

    TTL is status-aware: a LIVE match churns every round, so cache it SHORT
    (ttl_live, ~30s) — that way even outside the live-refresh job a read never
    serves 10-min-stale scores. A completed match is immutable, so keep the long
    ttl_matches. The live-refresh job overwrites the cache every ~30s; the short
    TTL is the backstop for when it isn't running / between ticks."""
    s = get_settings()
    data = await md.fetch_match(match_id)
    ttl = s.ttl_live if data.get("status") == "live" else s.ttl_matches
    await cache_set(CACHE_MATCH.format(id=match_id), data, ttl)
    return data


async def refresh_live_matches() -> int:
    """Scheduled (~30s): keep every currently-LIVE match's detail cache fresh so
    the match page's poll (and a plain reload) returns live scores/stats instead
    of scrape-on-miss-stale data. Bounded by the live list (usually 0–4 matches).

    Reads the live list from cache (the `upcoming` job owns the list scrape); the
    list is written on a longer cadence than its own TTL, so repopulate it here on
    a miss rather than skip a whole cycle. Each live match is re-scraped via
    refresh_match, which overwrites its cache with the live (short) TTL — and if a
    match has just FINALED, that same call caches it with the long TTL and the page
    poll stops on its own."""
    live = await cache_get(CACHE_LIVE)
    if live is None:
        await refresh_upcoming()  # list expired → repopulate (one cheap list scrape)
        live = await cache_get(CACHE_LIVE)
    if not live:
        return 0
    refreshed = 0
    for m in live:
        mid = m.get("id")
        if not mid:
            continue
        try:
            await refresh_match(str(mid))  # re-scrape + overwrite cache
            refreshed += 1
        except Exception:
            log.warning("refresh_live_matches: failed to refresh %s", mid, exc_info=True)
    log.info("refresh_live_matches: refreshed %d live match(es)", refreshed)
    return refreshed


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


# ---- player pre-scrape (scheduled twice daily) ------------------------------
# Banks a PlayerSnapshot for every player in the next ~48h of matches so trend
# history accumulates ahead of time, instead of waiting for someone to open each
# player page. NO new scraper: it orchestrates the existing match/team/player
# fetch paths. The shaping helpers below are pure (no network) so they test on
# row-like dicts; the orchestrator at the bottom does the fetching + cache gate.

PREFETCH_WINDOW_HOURS = 48.0  # bound the job to the imminent matches (stays small)

# vlr eta strings: "15h 1m", "1d 17h", "1w 1d" -> hours (weeks counted too).
_ETA_UNIT_HOURS = {"w": 168.0, "d": 24.0, "h": 1.0, "m": 1.0 / 60.0}


def eta_to_hours(eta: str | None) -> float | None:
    """Parse a vlr eta string to hours; None when nothing parses (e.g. a TBD card
    with no eta). Sums every unit token so '1w 1d' is 192h, not 24h."""
    if not eta:
        return None
    total = 0.0
    matched = False
    for value, unit in re.findall(r"(\d+)\s*([wdhm])", eta):
        total += int(value) * _ETA_UNIT_HOURS[unit]
        matched = True
    return total if matched else None


def match_is_tbd(match: dict[str, Any]) -> bool:
    """True for a bracket placeholder whose teams aren't resolved yet (TBD/empty)
    — those carry no players, so the job skips them."""
    teams = [(t or "").strip() for t in (match.get("teams") or [])]
    return len(teams) < 2 or any(not t or t.upper() == "TBD" for t in teams)


def upcoming_within_window(
    upcoming: list[dict[str, Any]], window_hours: float = PREFETCH_WINDOW_HOURS
) -> list[dict[str, Any]]:
    """The real (non-TBD) upcoming matches whose eta is inside the window."""
    out: list[dict[str, Any]] = []
    for m in upcoming:
        if match_is_tbd(m):
            continue
        hours = eta_to_hours(m.get("eta"))
        if hours is not None and hours <= window_hours:
            out.append(m)
    return out


def participant_ids_from_match(parsed: dict[str, Any]) -> list[str]:
    """Participant player IDs off a parsed match's scoreboard (per-map tables +
    the all-maps aggregate), de-duped with order preserved. Empty when no lineup
    has been posted yet — the caller then falls back to the team rosters."""
    ids: list[str] = []
    seen: set[str] = set()
    groups: list[dict[str, Any]] = list(parsed.get("maps") or [])
    if parsed.get("all_maps"):
        groups.append(parsed["all_maps"])
    for grp in groups:
        for team in grp.get("teams") or []:
            for p in team.get("players") or []:
                pid = p.get("player_id")
                if pid and str(pid) not in seen:
                    seen.add(str(pid))
                    ids.append(str(pid))
    return ids


def roster_ids_from_team(team_data: dict[str, Any]) -> list[str]:
    """Active (non-staff) roster player IDs from a parsed team page."""
    ids: list[str] = []
    for m in team_data.get("roster") or []:
        pid = m.get("player_id")
        if pid and not m.get("is_staff"):
            ids.append(str(pid))
    return ids


async def _match_player_ids(match: dict[str, Any]) -> list[str]:
    """One match -> its participant player IDs. ONE match-detail fetch yields both
    the scoreboard participants (primary) and the header team IDs (fallback): if
    the lineup isn't posted yet, fetch the two team pages and take their rosters."""
    mid = match.get("id")
    if not mid:
        return []
    try:
        parsed = await md.fetch_match(mid)
    except Exception:
        log.warning("player_prefetch: match fetch failed for %s", mid, exc_info=True)
        return []

    ids = participant_ids_from_match(parsed)
    if ids:
        return ids

    # fallback: header team ids -> roster player ids (current active roster)
    out: list[str] = []
    for team in parsed.get("teams") or []:
        tid = team.get("id")
        if not tid:
            continue
        try:
            team_data = await te.fetch_team(tid)
        except Exception:
            log.warning("player_prefetch: team fetch failed for %s", tid, exc_info=True)
            continue
        out.extend(roster_ids_from_team(team_data))
    return out


async def prefetch_upcoming_players(
    window_hours: float = PREFETCH_WINDOW_HOURS,
) -> dict[str, int]:
    """Scheduled twice daily. Collect every player in the next ~window_hours of
    matches and bank a PlayerSnapshot per player so trend history accumulates.

    CACHE-GATED (critical): refresh_player writes a snapshot on EVERY call with no
    internal dedup, so calling it blindly would pollute the history with duplicate
    rows. We replicate the route's gate per player — cache_get(vlr:player:{id});
    if present, the detail was fetched recently (on-demand or by a prior run within
    ttl_players=1h) and a snapshot already exists -> SKIP; only a cache MISS calls
    refresh_player. So snapshots never duplicate within or across runs, and the job
    cooperates with on-demand page views. Returns a run summary (also logged)."""
    split = await mt.fetch_upcoming()
    matches = upcoming_within_window(split.get("upcoming") or [], window_hours)

    # unique player ids across the whole window (order preserved)
    player_ids: list[str] = []
    seen: set[str] = set()
    for m in matches:
        for pid in await _match_player_ids(m):
            if pid not in seen:
                seen.add(pid)
                player_ids.append(pid)

    fetched = skipped = failed = 0
    for pid in player_ids:
        if await cache_get(CACHE_PLAYER.format(id=pid)) is not None:
            skipped += 1  # recently fetched -> snapshot exists; don't duplicate
            continue
        try:
            await refresh_player(pid)  # fetch + cache + exactly one snapshot
            fetched += 1
        except Exception:
            failed += 1
            log.warning("player_prefetch: player fetch failed for %s", pid, exc_info=True)

    summary = {
        "matches": len(matches),
        "players": len(player_ids),
        "fetched": fetched,
        "skipped": skipped,
        "failed": failed,
    }
    log.info(
        "player_prefetch: scanned %d matches, %d unique players "
        "(%d fetched, %d skipped/cache-hit, %d failed)",
        summary["matches"], summary["players"], fetched, skipped, failed,
    )
    return summary
