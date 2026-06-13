"""Trend analytics: the first view that reads banked history and joins it.

Reads ranking_snapshots (rating/rank over time) + match_results (completed games)
and shapes a team's rating trend joined with its results over a window. READ-ONLY:
no scraping, no writes, no new tables.

CRITICAL: the scraper stores rating/rank/scores as raw TEXT on purpose (lossless).
This layer coerces to numeric defensively at READ time — a point that doesn't parse
is SKIPPED, never guessed — and ratings are NEVER string-compared ("998" < "1024"
is False as strings, which is wrong). The DB query is kept separate from the
shaping so every pure function below tests on row-like dicts without a live DB.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import and_, func, or_, select

from app.core.db import SessionLocal
from app.models import MatchResult, PlayerSnapshot, RankingSnapshot


# ---- coercion (pure) --------------------------------------------------------
def coerce_float(value: Any) -> float | None:
    """Parse raw rating text to float; None if it doesn't parse ('N/A', '', None)."""
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except (ValueError, TypeError):
        return None


def coerce_int(value: Any) -> int | None:
    """Parse raw rank/score text to int; None if it doesn't parse."""
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return None


def _chrono_key(row: dict[str, Any]):
    """Sort key on captured_at that tolerates a missing timestamp (sorts last)."""
    ts = row.get("captured_at")
    return (ts is None, ts)


# ---- shaping (pure) ---------------------------------------------------------
def build_rating_trend(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Coerce snapshot rows -> chronological numeric trend, parseable points only.

    A point is kept only when its rating parses to a float; rank is best-effort
    (may be None without dropping the point). Order is by captured_at, never by
    the (string) rating — so a series like "998","1024","1003" stays in capture
    order with numeric values, not lexicographically reshuffled.
    """
    points = [
        {
            "captured_at": r.get("captured_at"),
            "rating": rating,
            "rank": coerce_int(r.get("rank")),
        }
        for r in rows
        if (rating := coerce_float(r.get("rating"))) is not None
    ]
    points.sort(key=_chrono_key)
    return points


def rating_change(trend: list[dict[str, Any]]) -> float | None:
    """last - first across the trend; None when fewer than 2 parseable points."""
    if len(trend) < 2:
        return None
    return round(trend[-1]["rating"] - trend[0]["rating"], 2)


def latest_team_name(rows: list[dict[str, Any]]) -> str | None:
    """The most recent non-empty team name from snapshot rows (for name-matching
    results). None if no snapshot carried a name."""
    named = [r for r in rows if (r.get("team") or "").strip()]
    if not named:
        return None
    named.sort(key=_chrono_key)
    return named[-1]["team"].strip()


def derive_result(
    team_name: str | None,
    team_a: str | None,
    team_b: str | None,
    score_a: Any,
    score_b: Any,
) -> str | None:
    """win/loss for team_name given which side it was on + the scores. None if the
    scores don't parse or the team can't be matched to a side (never raises)."""
    sa, sb = coerce_int(score_a), coerce_int(score_b)
    if sa is None or sb is None:
        return None
    name = (team_name or "").strip().casefold()
    if not name:
        return None
    if name == (team_a or "").strip().casefold():
        return "win" if sa > sb else "loss"
    if name == (team_b or "").strip().casefold():
        return "win" if sb > sa else "loss"
    return None


def _team_side(
    row: dict[str, Any], team_id: str | None, team_name: str | None
) -> str | None:
    """Which side ('a'/'b') the team is on in this row, or None if it isn't.

    IDs win: if the row carries ANY team id, it's authoritative — match strictly on
    team_id and never fall through to the fuzzy name path (so a rename can't cause a
    false match). Only rows with BOTH ids null fall back to the existing name match.
    """
    tid = str(team_id) if team_id is not None else None
    a_id, b_id = row.get("team_a_id"), row.get("team_b_id")
    if a_id is not None or b_id is not None:
        if tid is not None and a_id == tid:
            return "a"
        if tid is not None and b_id == tid:
            return "b"
        return None
    name = (team_name or "").strip().casefold()
    if not name:
        return None
    if name == (row.get("team_a") or "").strip().casefold():
        return "a"
    if name == (row.get("team_b") or "").strip().casefold():
        return "b"
    return None


def _result_from_scores(my: Any, opp: Any) -> str | None:
    """win/loss from the team's own score vs the opponent's. None if either score
    doesn't parse or they're equal — defensive, never raises (phase-4 contract)."""
    m, o = coerce_int(my), coerce_int(opp)
    if m is None or o is None or m == o:
        return None
    return "win" if m > o else "loss"


def build_results(
    rows: list[dict[str, Any]], team_id: str | None, team_name: str | None
) -> list[dict[str, Any]]:
    """Pick results where the team was a participant, shaped for the response.

    Matching prefers team ids (authoritative) and falls back to fuzzy name match
    only for older rows that have no ids — see _team_side. Scores are coerced
    defensively; an unparseable score yields result=null rather than crashing.
    """
    out: list[dict[str, Any]] = []
    for r in rows:
        side = _team_side(r, team_id, team_name)
        if side is None:
            continue
        a, b = r.get("team_a"), r.get("team_b")
        sa, sb = r.get("score_a"), r.get("score_b")
        if side == "a":
            opponent, my, opp = b, sa, sb
        else:
            opponent, my, opp = a, sb, sa
        score = f"{sa}:{sb}" if sa is not None and sb is not None else None
        out.append(
            {
                "vlr_id": r.get("vlr_id"),
                "opponent": opponent,
                "result": _result_from_scores(my, opp),
                "score": score,
                "event": r.get("event"),
                "captured_at": r.get("captured_at"),
            }
        )
    out.sort(key=_chrono_key)
    return out


def build_response(
    team_id: str,
    window_days: int,
    snapshot_rows: list[dict[str, Any]],
    result_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Assemble the full response from row-like dicts — pure, DB-free.

    summary stats use NUMERIC max/last over coerced ratings; peak_rating must never
    be a string-max (which would wrongly pick "998" over "1024").
    """
    trend = build_rating_trend(snapshot_rows)
    team_name = latest_team_name(snapshot_rows)
    results = build_results(result_rows, team_id, team_name)
    ratings = [p["rating"] for p in trend]

    resp: dict[str, Any] = {
        "team_id": str(team_id),
        "team": team_name,
        "window_days": window_days,
        "rating_trend": trend,
        "rating_change": rating_change(trend),
        "results_in_window": results,
        "summary": {
            "points": len(trend),
            "wins": sum(1 for m in results if m["result"] == "win"),
            "losses": sum(1 for m in results if m["result"] == "loss"),
            "current_rating": ratings[-1] if ratings else None,
            "peak_rating": max(ratings) if ratings else None,
        },
    }
    if team_name is None and not results:
        resp["note"] = (
            "no team name resolved from ranking snapshots for this team_id and no "
            "id-matched results found (results_in_window is empty)"
        )
    return resp


# ---- query (DB) -------------------------------------------------------------
async def team_trend(team_id: str, days: int = 90) -> dict[str, Any]:
    """Read ranking_snapshots + match_results for the window and shape a trend.

    Reads only. Snapshots are fetched chronologically; results are name-matched in
    SQL against the latest resolved team name, then the pure shaping does the rest.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    async with SessionLocal() as session:
        snaps = (
            await session.execute(
                select(RankingSnapshot)
                .where(RankingSnapshot.team_id == str(team_id))
                .where(RankingSnapshot.captured_at >= cutoff)
                .order_by(RankingSnapshot.captured_at.asc())
            )
        ).scalars().all()
        snapshot_rows = [
            {
                "captured_at": s.captured_at,
                "rating": s.rating,
                "rank": s.rank,
                "team": s.team,
            }
            for s in snaps
        ]

        team_name = latest_team_name(snapshot_rows)
        tid = str(team_id)
        # prefer id match on either side; fall back to fuzzy name ONLY for rows that
        # carry no ids at all (older /matches/results rows) — mirrors _team_side.
        conds = [MatchResult.team_a_id == tid, MatchResult.team_b_id == tid]
        if team_name:
            name = team_name.casefold()
            conds.append(
                and_(
                    MatchResult.team_a_id.is_(None),
                    MatchResult.team_b_id.is_(None),
                    or_(
                        func.lower(MatchResult.team_a) == name,
                        func.lower(MatchResult.team_b) == name,
                    ),
                )
            )
        res = (
            await session.execute(
                select(MatchResult)
                .where(MatchResult.captured_at >= cutoff)
                .where(or_(*conds))
                .order_by(MatchResult.captured_at.asc())
            )
        ).scalars().all()
        result_rows = [
            {
                "vlr_id": r.vlr_id,
                "team_a": r.team_a,
                "team_b": r.team_b,
                "team_a_id": r.team_a_id,
                "team_b_id": r.team_b_id,
                "score_a": r.score_a,
                "score_b": r.score_b,
                "event": r.event,
                "captured_at": r.captured_at,
            }
            for r in res
        ]

    return build_response(team_id, days, snapshot_rows, result_rows)


# =============================================================================
# Player trends (Phase 8) — the player analog of the team rating trend above.
#
# Same contract: read-only over banked PlayerSnapshot history, no scraper, no new
# table. A PlayerSnapshot stores per-agent stat rows (agent_stats JSON) captured
# per on-demand /player/{id} fetch; the numeric fields (Rating, ACS, RND, ...) are
# raw TEXT, honest to the scrape. We coerce defensively at READ time, NEVER sort
# or delta on the strings, and time-order on the real captured_at.
#
# A snapshot is per-agent, so to trend a single value per point we aggregate the
# agent rows into one rounds-weighted overall (rating + ACS) — VLR shows only the
# current split, so the drift over time is the net-new signal. Pure + DB-free
# shaping below; the one DB function is at the bottom.
# =============================================================================

# the verbatim agent_stats keys we trend (display-cased, as scraped — see CLAUDE.md)
_RATING_KEY = "Rating"
_ACS_KEY = "ACS"
_ROUNDS_KEY = "RND"


def aggregate_player_stats(agent_stats: Any) -> dict[str, Any] | None:
    """Collapse one snapshot's per-agent rows into a single rounds-weighted point.

    Rating and ACS are averaged across agents weighted by rounds played (RND), so
    a 4000-round main agent dominates a 14-round off-pick — the honest "overall"
    for that capture. An agent row only contributes when its Rating parses; rounds
    are the weight (falls back to 1 when RND won't parse, so a parseable rating is
    never silently dropped). ACS is weighted independently (may be null on a row
    without dropping its rating). Returns None when NO agent row had a parseable
    rating → the caller skips this snapshot rather than inventing a point.
    """
    if not isinstance(agent_stats, list):
        return None
    rating_num = rating_den = 0.0
    acs_num = acs_den = 0.0
    total_rounds = 0
    for row in agent_stats:
        stats = (row or {}).get("stats") or {}
        rating = coerce_float(stats.get(_RATING_KEY))
        if rating is None:
            continue  # the trended stat won't parse → skip this agent row
        rnd = coerce_int(stats.get(_ROUNDS_KEY))
        weight = rnd if (rnd is not None and rnd > 0) else 1
        rating_num += rating * weight
        rating_den += weight
        acs = coerce_float(stats.get(_ACS_KEY))
        if acs is not None:
            acs_num += acs * weight
            acs_den += weight
        if rnd is not None and rnd > 0:
            total_rounds += rnd
    if rating_den <= 0:
        return None
    return {
        "rating": round(rating_num / rating_den, 2),
        "acs": round(acs_num / acs_den, 1) if acs_den > 0 else None,
        "rounds": total_rounds,
    }


def build_player_trend(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Coerce snapshot rows -> chronological numeric trend, one point per snapshot.

    Each row is {captured_at, agent_stats}. A snapshot is kept only when its agent
    rows aggregate to a parseable rating; order is by captured_at, NEVER by the
    (string) rating — so a series like "0.998","1.024","1.003" stays in capture
    order with numeric values, not lexicographically reshuffled.
    """
    points = []
    for r in rows:
        agg = aggregate_player_stats(r.get("agent_stats"))
        if agg is None:
            continue
        points.append({"captured_at": r.get("captured_at"), **agg})
    points.sort(key=_chrono_key)
    return points


def metric_change(trend: list[dict[str, Any]], key: str) -> float | None:
    """last - first over the points that carry `key`; None with fewer than 2.

    `trend` is already chronological, so this reads the earliest vs latest
    parseable value — numeric, never a string delta.
    """
    vals = [p[key] for p in trend if p.get(key) is not None]
    if len(vals) < 2:
        return None
    return round(vals[-1] - vals[0], 2)


def latest_player_field(rows: list[dict[str, Any]], key: str) -> str | None:
    """The most recent non-empty value of a string field (alias/team) across
    snapshot rows. None if no snapshot carried one."""
    named = [r for r in rows if (r.get(key) or "").strip()]
    if not named:
        return None
    named.sort(key=_chrono_key)
    return named[-1][key].strip()


def build_player_response(
    player_id: str,
    window_days: int,
    snapshot_rows: list[dict[str, Any]],
    cutoff: datetime | None = None,
) -> dict[str, Any]:
    """Assemble the player-trend response from row-like dicts — pure, DB-free.

    Mirrors the team-trend shape (rating_trend series + change + summary) so the
    frontend reuses the same Sparkline/TrendPanel. The trend respects `cutoff`
    (window edge) when given, but identity (alias/team) resolves from ALL rows —
    so a player whose only history predates the window still gets a name, never a
    misleading null. summary stats use NUMERIC max/last over coerced values.
    """
    in_window = (
        snapshot_rows
        if cutoff is None
        else [
            r
            for r in snapshot_rows
            if (ts := r.get("captured_at")) is not None and ts >= cutoff
        ]
    )
    trend = build_player_trend(in_window)
    alias = latest_player_field(snapshot_rows, "alias")
    team = latest_player_field(snapshot_rows, "team")
    ratings = [p["rating"] for p in trend if p.get("rating") is not None]
    accs = [p["acs"] for p in trend if p.get("acs") is not None]

    resp: dict[str, Any] = {
        "player_id": str(player_id),
        "player": alias,
        "team": team,
        "window_days": window_days,
        "rating_trend": trend,
        "rating_change": metric_change(trend, "rating"),
        "acs_change": metric_change(trend, "acs"),
        "summary": {
            "points": len(trend),
            "current_rating": ratings[-1] if ratings else None,
            "peak_rating": max(ratings) if ratings else None,
            "current_acs": accs[-1] if accs else None,
            "peak_acs": max(accs) if accs else None,
        },
    }
    if not trend:
        resp["note"] = (
            "no parseable rating in the window for this player_id "
            "(rating_trend is empty) — thin/young history"
        )
    return resp


async def player_trend(player_id: str, days: int = 90) -> dict[str, Any] | None:
    """Read player_snapshots for a player and shape a rating/ACS trend.

    Reads only. Returns None when the player_id has NO banked snapshots at all (the
    route maps that to a clean 404, mirroring /history/player). When snapshots
    exist but the windowed trend is thin/empty, returns a valid empty response —
    the frontend decides the young-history note. All rows are fetched (per-player
    history is sparse) so identity resolves even if it predates the window.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    async with SessionLocal() as session:
        snaps = (
            await session.execute(
                select(PlayerSnapshot)
                .where(PlayerSnapshot.player_id == str(player_id))
                .order_by(PlayerSnapshot.captured_at.asc())
            )
        ).scalars().all()
    if not snaps:
        return None
    snapshot_rows = [
        {
            "captured_at": s.captured_at,
            "alias": s.alias,
            "team": s.team,
            "agent_stats": s.agent_stats,
        }
        for s in snaps
    ]
    return build_player_response(player_id, days, snapshot_rows, cutoff)
