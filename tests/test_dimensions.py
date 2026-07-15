"""Phase 13 — dimension-split rating: pctile helper + four-dimension formulas.

Tests cover:
  - pctile correctness (min→0, max→100, median→50, None→0, singleton→50)
  - inverse-stat handling (FDPR inverted in CONSISTENCY)
  - each dimension formula with hand-computed values from the stats fixture cohort
  - low_confidence flag thresholds
  - null/missing stats coerce safely, never NaN
  - INVARIANT: top-R2.0 player in the fixture cohort scores >70 on ≥2 dimensions
  - route envelope: shape, player-not-found 404, bad-region 400
"""
import math
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api.v1 import routes
from app.ratings.dimensions import compute_dimensions, pctile
from app.scrapers.stats import parse_stats
from app.services import refresh as R

FIX = Path(__file__).parent / "fixtures"


def load_cohort() -> list[dict]:
    """The 3-row hand-built cohort (no network). Deliberately its own fixture,
    separate from tests/fixtures/stats_na.html (which is a live-captured,
    real-data fixture for scraper structure tests) — the formulas below hand-
    verify exact percentile arithmetic and need fixed, round-numbered values."""
    return parse_stats((FIX / "dimensions_cohort.html").read_text())


# ---------- pctile helper ----------

def test_pctile_min_zero():
    assert pctile(1.0, [1.0, 2.0, 3.0]) == 0.0


def test_pctile_max_100():
    assert pctile(3.0, [1.0, 2.0, 3.0]) == 100.0


def test_pctile_median_50():
    assert pctile(2.0, [1.0, 2.0, 3.0]) == 50.0


def test_pctile_none_value_returns_zero():
    # None value → no evidence → bottom of cohort
    assert pctile(None, [1.0, 2.0, 3.0]) == 0.0


def test_pctile_empty_or_singleton_cohort_returns_50():
    assert pctile(5.0, []) == 50.0
    assert pctile(5.0, [5.0]) == 50.0
    assert pctile(5.0, [None]) == 50.0


def test_pctile_none_values_excluded_from_denominator():
    # 3 values but one is None → effective N=2, so min→0, max→100
    assert pctile(10.0, [10.0, None, 20.0]) == 0.0
    assert pctile(20.0, [10.0, None, 20.0]) == 100.0


# ---------- dimension formulas (hand-computed against dimensions_cohort fixture) ----------
#
# Cohort (3 rows from dimensions_cohort.html after parse_stats):
#   TenZ   (id=9):    acs=256.4, kd=1.62, kpr=0.82, kmax=34,  kast=78.0, apr=0.31
#                     fdpr=0.09, fkpr=0.12, clutch_pct=20.0, cl_won=3,  cl_played=15
#                     rnd=512, k=20, d=14, fk=2, fd=1
#   aspas  (id=9999): acs=198.1, kd=1.10, kpr=0.75, kmax=30,  kast=71.0, apr=0.28
#                     fdpr=0.11, fkpr=0.10, clutch_pct=18.0, cl_won=19, cl_played=104
#                     rnd=480, k=18, d=16, fk=3, fd=2
#   lowsample (id=123): acs=180.0, kd=0.95, kpr=0.60, kmax=None, kast=65.0, apr=0.20
#                     fdpr=0.08, fkpr=0.05, clutch_pct=None, cl_won=None, rnd=40
#
# pctile formula: (# values strictly below v) / (N-1) * 100 over non-None values.
# N=3 cohort → denominator = 2; N=2 (when one None) → denominator = 1.

def test_firepower_formula():
    cohort = load_cohort()
    tenz = cohort[0]
    # acs=256.4 highest of [256.4,198.1,180.0] → 2/2*100 = 100
    # kpr=0.82  highest of [0.82,0.75,0.60]    → 100
    # kd=1.62   highest of [1.62,1.10,0.95]    → 100
    # kmax=34   highest of [34,30] (N=2)        → 1/1*100 = 100
    # FIREPOWER = 0.40*100 + 0.25*100 + 0.20*100 + 0.15*100 = 100.0
    dims = compute_dimensions(tenz, cohort)
    assert dims["firepower"] == 100.0


def test_entry_formula():
    cohort = load_cohort()
    tenz = cohort[0]
    # fk_fd_ratio = 2/max(1,1) = 2.0; cohort: [2.0, 1.5, 1.0] → 2/2*100 = 100
    # fkpr=0.12 highest of [0.12,0.10,0.05]    → 100
    # fk_share = 2/20 = 0.10; cohort: [0.10, 0.1667, 0.10]
    #   → below=0 (tie at min) → 0/2*100 = 0.0
    # ENTRY = 0.45*100 + 0.30*100 + 0.25*0 = 75.0
    dims = compute_dimensions(tenz, cohort)
    assert dims["entry"] == 75.0


def test_consistency_formula():
    cohort = load_cohort()
    tenz = cohort[0]
    # kast=78.0 highest → 100
    # apr=0.31  highest → 100
    # fdpr: [0.09,0.11,0.08] → tenz=0.09, below=1 → 1/2*100 = 50 → inverted = 50
    # CONSISTENCY = 0.55*100 + 0.25*100 + 0.20*50 = 90.0
    dims = compute_dimensions(tenz, cohort)
    assert dims["consistency"] == 90.0


def test_clutch_formula():
    cohort = load_cohort()
    tenz = cohort[0]
    # clutch_pct: [20.0,18.0] (N=2, None excluded) → tenz=20.0 highest → 1/1*100=100
    # clutch_vol_adj: tenz=3*(3/15)=0.6; aspas=19*(19/104)≈3.47; lowsample=None
    #   present=[0.6,3.47] (N=2) → tenz below=0 → 0/1*100=0
    # kd=1.62 highest → 100
    # CLUTCH = 0.40*100 + 0.35*0 + 0.25*100 = 65.0
    dims = compute_dimensions(tenz, cohort)
    assert dims["clutch"] == 65.0


def test_fdpr_inverse_in_consistency():
    # A player with the LOWEST fdpr (fewest first-deaths) should score best on
    # the FDPR component. lowsample has fdpr=0.08 (lowest in cohort).
    cohort = load_cohort()
    lowsample = cohort[2]
    dims_low = compute_dimensions(lowsample, cohort)
    # fdpr=0.08 is the minimum → pctile=0.0 → 100-0=100 for the FDPR component
    # Manually: kast=65.0 lowest→0, apr=0.20 lowest→0, fdpr-inverted=100
    # CONSISTENCY = 0.55*0 + 0.25*0 + 0.20*100 = 20.0
    assert dims_low["consistency"] == 20.0


# ---------- low_confidence flags ----------

def test_low_confidence_clutch_fires_at_threshold():
    stats = {"cl_played": 4, "rnd": 200}
    dims = compute_dimensions(stats, [stats])
    assert "clutch" in dims["low_confidence"]


def test_low_confidence_clutch_absent_at_threshold():
    stats = {"cl_played": 5, "rnd": 200}
    dims = compute_dimensions(stats, [stats])
    assert "clutch" not in dims["low_confidence"]


def test_low_confidence_all_fires_at_threshold():
    stats = {"rnd": 99, "cl_played": 10}
    dims = compute_dimensions(stats, [stats])
    assert "all" in dims["low_confidence"]


def test_low_confidence_none_cl_played_fires_clutch():
    stats = {"rnd": 200}  # cl_played absent
    dims = compute_dimensions(stats, [stats])
    assert "clutch" in dims["low_confidence"]


def test_low_confidence_both_flags_for_lowsample():
    cohort = load_cohort()
    lowsample = cohort[2]  # rnd=40 <100, cl_played=None <5
    dims = compute_dimensions(lowsample, cohort)
    assert "clutch" in dims["low_confidence"]
    assert "all" in dims["low_confidence"]


def test_low_confidence_empty_for_full_sample():
    cohort = load_cohort()
    tenz = cohort[0]  # rnd=512, cl_played=15
    dims = compute_dimensions(tenz, cohort)
    assert dims["low_confidence"] == []


# ---------- null / missing stats ----------

def test_null_stats_never_nan():
    # A completely empty row must produce finite scores, never NaN, never crash.
    result = compute_dimensions({}, [{}])
    for key in ("firepower", "entry", "consistency", "clutch"):
        v = result[key]
        assert v is not None
        assert isinstance(v, float)
        assert math.isfinite(v)


def test_missing_stat_coerces_safely():
    # Partial rows (some stats missing) must not crash and must not produce NaN.
    partial = {"acs": 250.0, "kd": 1.5}  # most stats absent
    result = compute_dimensions(partial, [partial, {"acs": 200.0, "kd": 1.0}])
    for key in ("firepower", "entry", "consistency", "clutch"):
        v = result[key]
        assert math.isfinite(v)


# ---------- invariant: top-R2.0 player is highly rated on multiple dimensions ----------

def test_top_r2_player_high_on_at_least_two_dimensions():
    """TenZ has the highest R2.0 in the fixture cohort. A rating system that
    captures the source of excellence must score him >70 on ≥2 of the four
    dimensions. Catching 'missing the source of rating' regressions."""
    cohort = load_cohort()
    tenz = cohort[0]
    assert tenz["r2"] == max(r["r2"] for r in cohort if r.get("r2") is not None)
    dims = compute_dimensions(tenz, cohort)
    high = sum(
        1 for key in ("firepower", "entry", "consistency", "clutch")
        if dims[key] > 70
    )
    assert high >= 2, f"Expected ≥2 dims >70, got {dims}"


# ---------- route ----------

async def test_route_bad_region_400():
    async def fake_cache_get(_key):
        return None
    import app.api.v1.routes as r_mod
    monkeypatch_cache = None  # handled inline below

    with pytest.raises(HTTPException) as ei:
        await routes.player_dimensions("9", region="world", timespan="all")
    assert ei.value.status_code == 400


async def test_route_bad_timespan_400():
    with pytest.raises(HTTPException) as ei:
        await routes.player_dimensions("9", region="na", timespan="7d")
    assert ei.value.status_code == 400


async def test_route_player_not_in_cohort_404(monkeypatch):
    cohort = load_cohort()

    async def fake_cache_get(_key):
        return cohort

    async def fake_refresh_stats(_region, _timespan):
        pass

    monkeypatch.setattr(routes, "cache_get", fake_cache_get)
    monkeypatch.setattr(R, "refresh_stats", fake_refresh_stats)
    with pytest.raises(HTTPException) as ei:
        await routes.player_dimensions("99999", region="na", timespan="all")
    assert ei.value.status_code == 404


async def test_route_cache_race_fallback_resolves(monkeypatch):
    """Empty initial cohort (mid-rewarm) triggers one recompute and succeeds."""
    cohort = load_cohort()
    cache_calls = [0]

    async def fake_cache_get(_key):
        cache_calls[0] += 1
        if cache_calls[0] == 1:
            return []  # empty on first read — scheduler is mid-rewarm
        return cohort  # populated after recompute

    async def fake_refresh_stats(_region, _timespan):
        pass

    monkeypatch.setattr(routes, "cache_get", fake_cache_get)
    monkeypatch.setattr(R, "refresh_stats", fake_refresh_stats)

    resp = await routes.player_dimensions("9", region="na", timespan="all")
    assert resp["player_id"] == "9"
    assert "firepower" in resp
    assert cache_calls[0] == 2  # initial empty read + post-recompute read


async def test_route_returns_dimension_shape(monkeypatch):
    cohort = load_cohort()

    async def fake_cache_get(_key):
        return cohort

    monkeypatch.setattr(routes, "cache_get", fake_cache_get)
    resp = await routes.player_dimensions("9", region="na", timespan="all")
    assert resp["player_id"] == "9"
    assert resp["region"] == "na"
    for key in ("firepower", "entry", "consistency", "clutch", "low_confidence"):
        assert key in resp
    assert isinstance(resp["low_confidence"], list)
