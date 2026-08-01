"""Dimension-split player rating (Phase 13).

Four derived dimensions — Firepower / Entry / Consistency / Clutch — expressed as
0-100 cohort percentile ranks. Pure computation: no scraping, no selectors, no
network. Input stats come from the same region+timespan leaderboard the /stats
endpoint caches. Every raw stat is coerced at call time (null on failure, never NaN).

Weights are LOCKED — do not adjust.

WHAT THESE NUMBERS MEAN (and don't)

Every score is RELATIVE, never absolute. "Firepower 82" means "better than 82%
of this cohort at fragging", not "82% good". The same player scored against
na/all and eu/30d gets different numbers with no change in play, so a score is
only meaningful next to its region+timespan — which is why the route echoes both
back in the response. Comparing scores across cohorts is meaningless.

The cohort is the ENTIRE cached leaderboard for that region+timespan, and the
player being scored is included in it (standard percentile-rank practice, and it
keeps the max of the cohort at exactly 100).

WHY THE OUTPUT IS BOUNDED 0-100

Each dimension is a weighted sum of percentiles whose weights sum to exactly
1.00. Since each percentile is already 0-100, the weighted sum is too — no
normalization step, and none is needed. This is the constraint that makes the
weights "locked" in a stronger sense than taste: adding a fifth stat to a
dimension without taking weight from the others silently changes the scale of
that dimension only, and the four stop being comparable to each other.

THE DIMENSIONS ARE NOT ORTHOGONAL, ON PURPOSE

K:D feeds both Firepower (0.20) and Clutch (0.25), so the two correlate by
construction. That is intended — winning clutches IS partly a fragging skill —
but it means the four scores are not independent axes and should not be summed
into a single composite. VLR's own R2.0 (surfaced by /stats) is the headline
number; these are a breakdown of style, not a competing rating.

MISSING DATA IS SCORED, NOT SKIPPED

A null stat does not drop out of the average — it scores 0 (see pctile). A
player with sparse data is therefore penalized rather than excluded, which keeps
every dimension on the same scale for everyone. The `low_confidence` flags exist
to let the UI say so. The one place this rule inverts is the FDPR term in
Consistency — see the comment there before trusting a Consistency score for a
player with missing first-death data.
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

    The N-1 denominator is what pins the cohort maximum to exactly 100.0 (the
    top value has all N-1 others strictly below it). The more common N
    denominator would top out at (N-1)/N — 99.x on a big cohort — and no player
    would ever score 100 on anything.

    STRICTLY below, so ties share the LOWER rank: five players tied at the top
    all score below 100 together, and nobody is broken out by float noise. Nulls
    are dropped from the denominator entirely, so a stat vlr only fills for half
    the board still ranks sensibly among the half that has it.

    Two deliberate degenerate cases:
      - None value → 0.0, not None. Missing data is scored as worst rather than
        excluded, so every dimension stays on one scale for every player. This
        is why `low_confidence` exists — a thin-history player's low scores are
        partly an artifact of this rule. (Note the inversion trap this creates
        for inverse stats — see the FDPR term in compute_dimensions.)
      - Fewer than 2 values → 50.0, not 0 or 100. There is no ranking to be had
        in a cohort of one, and neutral is the only non-misleading answer.
    """
    if value is None:
        return 0.0
    present = [v for v in all_values if v is not None]
    n = len(present)
    if n < 2:
        return 50.0
    below = sum(1 for v in present if v < value)
    # The cap only bites when `value` is NOT a member of all_values — then
    # `below` can reach N and the ratio exceeds 1. Callers pass a player who IS
    # in the cohort, so this is a guard for reuse, not a live code path.
    return min(100.0, round(100.0 * below / (n - 1), 1))


def _f(stats: dict[str, Any], key: str) -> float | None:
    return parse_numeric(stats.get(key))


def _cohort(cohort: list[dict[str, Any]], key: str) -> list[float | None]:
    return [parse_numeric(r.get(key)) for r in cohort]


def _safe_div(num: float | None, den: float | None) -> float | None:
    """num / max(den, 1) — None propagates from num; den=None treated as 1.

    The max(den, 1) floor does double duty: it prevents division by zero AND it
    stops small denominators from exploding the ratio. A player with 8 first
    kills and 0 first deaths would otherwise be undefined; here they score 8.0,
    which ranks at the top without becoming an outlier that flattens everyone
    else's percentile. All the denominators used here are counting stats, so
    clamping at 1 never distorts a legitimate value.

    The None asymmetry is deliberate: a missing NUMERATOR means we know nothing
    about the player's output, so the result is None (and pctile scores it 0);
    a missing DENOMINATOR would otherwise throw away a numerator we do have, so
    it degrades to 1 and the ratio becomes the raw count.
    """
    if num is None:
        return None
    d = den if den is not None else 1.0
    return num / max(d, 1.0)


def _clutch_vol(cl_won: float | None, cl_played: float | None) -> float | None:
    """cl_won * (cl_won / max(cl_played, 1)). None when cl_won is None.

    Volume-adjusted clutch: effectively cl_won² / cl_played, i.e. clutch wins
    scaled by clutch win RATE. This exists to stop small samples from topping
    the dimension — a 1-for-1 player is at 100% and would otherwise outrank
    everyone, while here they score 1.0 against a 12-for-30 player's 4.8. Rate
    alone rewards luck; volume alone rewards playing a lot of losing rounds;
    the product needs both.
    """
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

    Cost note: every pctile() call is a full scan of the cohort, and there are
    ~13 of them, so this is O(13N) per player — fine for a few hundred
    leaderboard rows computed on demand for ONE player, but do not call it in a
    loop over the whole cohort without hoisting the per-stat cohort lists out.
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

    # The three derived stats must be recomputed across the WHOLE cohort, not
    # just for this player: a percentile needs the same derivation applied to
    # every row to rank against. This is why they can't be read off the
    # leaderboard like acs/kpr — vlr publishes fk and fd, not fk/fd.
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
    # ACS carries the most weight because it already blends kills, damage and
    # multi-kills into vlr's own per-round impact number. KPR and K:D are rate
    # and efficiency; KMAX is the smallest weight on purpose — a single 30-kill
    # map says something about ceiling, but it is one map.
    firepower = (
        0.40 * pctile(_f(player_stats, "acs"),  _cohort(cohort, "acs"))
        + 0.25 * pctile(_f(player_stats, "kpr"),  _cohort(cohort, "kpr"))
        + 0.20 * pctile(_f(player_stats, "kd"),   _cohort(cohort, "kd"))
        + 0.15 * pctile(_f(player_stats, "kmax"), _cohort(cohort, "kmax"))
    )

    # ---- ENTRY: first-blood impact ----
    # FK/FD ratio leads because entrying is a trade: taking first bloods matters
    # only against how often you give them away. FKPR is volume (are you the one
    # taking the duel at all), and fk_share asks what fraction of a player's
    # kills are openers — which is what separates an entry role from a duelist
    # who happens to frag a lot.
    entry = (
        0.45 * pctile(fk_fd_ratio, c_fk_fd)
        + 0.30 * pctile(_f(player_stats, "fkpr"), _cohort(cohort, "fkpr"))
        + 0.25 * pctile(fk_share, c_fk_share)
    )

    # ---- CONSISTENCY: reliable round-to-round contribution ----
    # KAST dominates because it IS the consistency stat — the share of rounds
    # where a player did something useful at all. APR credits the contribution
    # that never shows up in a frag count.
    #
    # FDPR is inverse: fewer first-deaths is better, so invert the rank.
    #
    # ⚠️ The inversion collides with pctile's missing-data rule. Everywhere else
    # a null stat scores 0 (worst); here a null FDPR gives pctile 0.0, which
    # inverts to 100.0 — the FULL 0.20 contribution, identical to having the
    # best first-death rate in the cohort. So a player with no FDPR data scores
    # HIGHER on Consistency than one with a measured-but-mediocre rate. Reachable
    # whenever vlr leaves the column empty (scrapers/stats.py nulls absent cells).
    # Left as-is deliberately — changing it moves every published Consistency
    # score, and the weights are locked.
    fdpr_pctile = pctile(_f(player_stats, "fdpr"), _cohort(cohort, "fdpr"))
    consistency = (
        0.55 * pctile(_f(player_stats, "kast"), _cohort(cohort, "kast"))
        + 0.25 * pctile(_f(player_stats, "apr"),  _cohort(cohort, "apr"))
        + 0.20 * (100.0 - fdpr_pctile)
    )

    # ---- CLUTCH: win-when-it-matters ----
    # Rate and volume-adjusted volume are split nearly evenly so neither a
    # perfect tiny sample nor sheer quantity can carry the score alone. K:D
    # reappears here (it is also 0.20 of Firepower) because surviving a clutch
    # is mostly winning the duels — the correlation is intended, see the module
    # docstring.
    clutch = (
        0.40 * pctile(_f(player_stats, "clutch_pct"), _cohort(cohort, "clutch_pct"))
        + 0.35 * pctile(clutch_vol_adj, c_clutch_vol)
        + 0.25 * pctile(_f(player_stats, "kd"), _cohort(cohort, "kd"))
    )

    # ---- low-confidence flags ----
    # ADVISORY ONLY — the scores are computed and returned regardless. These say
    # "this number is built on thin evidence", and the UI decides whether to
    # caveat or hide it. Suppressing the scores here instead would leave the
    # frontend unable to distinguish "no data" from "genuinely bad".
    #
    # The two thresholds are different in kind: "clutch" flags one dimension
    # whose input is sparse by nature (few clutch situations arise), while "all"
    # flags every dimension because a player under ~100 rounds has too little of
    # everything for any percentile to mean much.
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
