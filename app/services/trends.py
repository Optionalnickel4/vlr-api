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

from sqlalchemy import func, or_, select

from app.core.db import SessionLocal
from app.models import MatchResult, RankingSnapshot


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


def build_results(rows: list[dict[str, Any]], team_name: str | None) -> list[dict[str, Any]]:
    """Pick results where team_name was a participant, shaped for the response.

    Name-matching is fuzzy by nature (renames, casing) — that's a known limit we
    surface, not solve. Scores are coerced defensively; an unparseable score yields
    result=null rather than crashing.
    """
    name = (team_name or "").strip().casefold()
    if not name:
        return []
    out: list[dict[str, Any]] = []
    for r in rows:
        a, b = r.get("team_a"), r.get("team_b")
        if name == (a or "").strip().casefold():
            opponent = b
        elif name == (b or "").strip().casefold():
            opponent = a
        else:
            continue
        sa, sb = r.get("score_a"), r.get("score_b")
        score = f"{sa}:{sb}" if sa is not None and sb is not None else None
        out.append(
            {
                "vlr_id": r.get("vlr_id"),
                "opponent": opponent,
                "result": derive_result(team_name, a, b, sa, sb),
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
    results = build_results(result_rows, team_name)
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
    if team_name is None:
        resp["note"] = (
            "no team name resolved from ranking snapshots for this team_id; "
            "results could not be name-matched (results_in_window is empty)"
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
        result_rows: list[dict[str, Any]] = []
        if team_name:
            name = team_name.casefold()
            res = (
                await session.execute(
                    select(MatchResult)
                    .where(MatchResult.captured_at >= cutoff)
                    .where(
                        or_(
                            func.lower(MatchResult.team_a) == name,
                            func.lower(MatchResult.team_b) == name,
                        )
                    )
                    .order_by(MatchResult.captured_at.asc())
                )
            ).scalars().all()
            result_rows = [
                {
                    "vlr_id": r.vlr_id,
                    "team_a": r.team_a,
                    "team_b": r.team_b,
                    "score_a": r.score_a,
                    "score_b": r.score_b,
                    "event": r.event,
                    "captured_at": r.captured_at,
                }
                for r in res
            ]

    return build_response(team_id, days, snapshot_rows, result_rows)
