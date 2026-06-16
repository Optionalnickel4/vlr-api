"""Dimension-split player rating (Phase 13).

Four derived dimensions — Firepower / Entry / Consistency / Clutch — expressed as
0-100 cohort percentile ranks. Pure computation: no scraping, no selectors, no
network. Input stats come from the same region+timespan leaderboard the /stats
endpoint caches. Every raw stat is coerced at call time (null on failure, never NaN).

Weights are LOCKED — do not adjust.
"""
from __future__ import annotations

from typing import Any

from app.scrapers._util import parse_numeric


def pctile(value: float | None, all_values: list[float | None]) -> float:
    """Percentile rank of *value* within *all_values*: 0–100.

    Uses the strict-below formula over non-None values:
        rank = (# values strictly below v) / (N - 1) * 100

    Properties:
      min value in cohort → 0.0
      max value in cohort → 100.0
      median value        → ~50.0
    A None *value* returns 0.0 (no evidence → bottom of cohort).
    A cohort of fewer than 2 non-None values returns 50.0 (can't rank).
    """
    if value is None:
        return 0.0
    present = [v for v in all_values if v is not None]
    n = len(present)
    if n < 2:
        return 50.0
    below = sum(1 for v in present if v < value)
    return min(100.0, round(100.0 * below / (n - 1), 1))


def _f(stats: dict[str, Any], key: str) -> float | None:
    return parse_numeric(stats.get(key))


def _cohort(cohort: list[dict[str, Any]], key: str) -> list[float | None]:
    return [parse_numeric(r.get(key)) for r in cohort]


def _safe_div(num: float | None, den: float | None) -> float | None:
    """num / max(den, 1) — None propagates from num; den=None treated as 1."""
    if num is None:
        return None
    d = den if den is not None else 1.0
    return num / max(d, 1.0)


def _clutch_vol(cl_won: float | None, cl_played: float | None) -> float | None:
    """cl_won * (cl_won / max(cl_played, 1)). None when cl_won is None."""
    if cl_won is None:
        return None
    return cl_won * _safe_div(cl_won, cl_played)  # type: ignore[arg-type]


def compute_dimensions(
    player_stats: dict[str, Any],
    cohort: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute four dimension scores (0-100 cohort percentiles) for one player.

    player_stats — one leaderboard row dict (the player being scored).
    cohort       — the full leaderboard list (the player is included, consistent
                   with standard percentile-rank practice).

    Returns {"firepower", "entry", "consistency", "clutch", "low_confidence"}.
    """
    # ---- per-player derived stats ----
    fk = _f(player_stats, "fk")
    fd = _f(player_stats, "fd")
    k = _f(player_stats, "k")
    cl_won = _f(player_stats, "cl_won")
    cl_played = _f(player_stats, "cl_played")

    fk_fd_ratio = _safe_div(fk, fd)
    fk_share = _safe_div(fk, k)
    clutch_vol_adj = _clutch_vol(cl_won, cl_played)

    # ---- same derived stats across the full cohort (vectorised) ----
    c_fk_fd: list[float | None] = [
        _safe_div(parse_numeric(r.get("fk")), parse_numeric(r.get("fd")))
        for r in cohort
    ]
    c_fk_share: list[float | None] = [
        _safe_div(parse_numeric(r.get("fk")), parse_numeric(r.get("k")))
        for r in cohort
    ]
    c_clutch_vol: list[float | None] = [
        _clutch_vol(parse_numeric(r.get("cl_won")), parse_numeric(r.get("cl_played")))
        for r in cohort
    ]

    # ---- FIREPOWER: raw fragging output ----
    firepower = (
        0.40 * pctile(_f(player_stats, "acs"),  _cohort(cohort, "acs"))
        + 0.25 * pctile(_f(player_stats, "kpr"),  _cohort(cohort, "kpr"))
        + 0.20 * pctile(_f(player_stats, "kd"),   _cohort(cohort, "kd"))
        + 0.15 * pctile(_f(player_stats, "kmax"), _cohort(cohort, "kmax"))
    )

    # ---- ENTRY: first-blood impact ----
    entry = (
        0.45 * pctile(fk_fd_ratio, c_fk_fd)
        + 0.30 * pctile(_f(player_stats, "fkpr"), _cohort(cohort, "fkpr"))
        + 0.25 * pctile(fk_share, c_fk_share)
    )

    # ---- CONSISTENCY: reliable round-to-round contribution ----
    # FDPR is inverse: fewer first-deaths is better, so invert the rank.
    fdpr_pctile = pctile(_f(player_stats, "fdpr"), _cohort(cohort, "fdpr"))
    consistency = (
        0.55 * pctile(_f(player_stats, "kast"), _cohort(cohort, "kast"))
        + 0.25 * pctile(_f(player_stats, "apr"),  _cohort(cohort, "apr"))
        + 0.20 * (100.0 - fdpr_pctile)
    )

    # ---- CLUTCH: win-when-it-matters ----
    clutch = (
        0.40 * pctile(_f(player_stats, "clutch_pct"), _cohort(cohort, "clutch_pct"))
        + 0.35 * pctile(clutch_vol_adj, c_clutch_vol)
        + 0.25 * pctile(_f(player_stats, "kd"), _cohort(cohort, "kd"))
    )

    # ---- low-confidence flags ----
    low_confidence: list[str] = []
    if cl_played is None or cl_played < 5:
        low_confidence.append("clutch")
    rnd = _f(player_stats, "rnd")
    if rnd is None or rnd < 100:
        low_confidence.append("all")

    return {
        "firepower": round(firepower, 1),
        "entry": round(entry, 1),
        "consistency": round(consistency, 1),
        "clutch": round(clutch, 1),
        "low_confidence": low_confidence,
    }
