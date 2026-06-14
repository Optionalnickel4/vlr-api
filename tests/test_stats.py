"""Stats leaderboard (Phase 12) — scraper coercion + service cache-write + route.

Mirrors the other suites: parse a saved structural fixture (no network), assert
STRUCTURE + coercion invariants (never volatile values), and mock every fetch /
cache boundary for the service + route. The coercion checks are the point — this
is the label-bleed / silently-wrong-numbers bug class:
  - span.mod-both is read, never raw td.text() (the K cell would be "20119"),
  - the CL fraction '3/15' splits into two ints (never a single number),
  - %-columns strip the sign, empties become null (never NaN, never a crash).
"""
from pathlib import Path

import math

import pytest
from fastapi import HTTPException

from app.api.v1 import routes
from app.scrapers._util import coerce_int, parse_fraction
from app.scrapers.stats import _ROW_KEYS, parse_stats
from app.services import refresh as R

FIX = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIX / name).read_text()


# ---------- coercion helpers ----------
def test_parse_fraction_splits_won_played():
    assert parse_fraction("3/15") == (3, 15)
    assert parse_fraction("19/104") == (19, 104)  # valid two-digit/three-digit


def test_parse_fraction_null_not_crash():
    # empty / no-slash / malformed -> (None, None), never a single number, never NaN
    for bad in ["", "  ", None, "-", "5", "N/A"]:
        assert parse_fraction(bad) == (None, None)


def test_coerce_int_null_not_nan():
    assert coerce_int("15") == 15
    assert coerce_int("15.0") == 15
    assert isinstance(coerce_int("7"), int)
    for bad in ["", "  ", None, "-", "nan", "inf"]:
        assert coerce_int(bad) is None


# ---------- scraper ----------
def test_parse_stats_row_count_and_full_key_set():
    rows = parse_stats(load("stats_na.html"))
    assert len(rows) == 3
    # every row carries the complete, stable key set (null where absent)
    for r in rows:
        assert set(r.keys()) == set(_ROW_KEYS)


def test_parse_stats_identity_and_headline():
    rows = parse_stats(load("stats_na.html"))
    top = rows[0]
    assert top["player"] == "TenZ"          # alias from text-of, NOT "TenZSEN"
    assert top["player_id"] == "9"          # from the /player/{id} link
    # R2.0 is VLR's own rating headline — a float, at 100% fill
    assert top["r2"] == 1.24
    assert isinstance(top["r2"], float)
    assert all(r["r2"] is not None for r in rows)


def test_parse_stats_reads_mod_both_not_raw_text():
    # the K cell holds mod-both=20 + mod-t=11 + mod-ct=9; raw td.text() would
    # concatenate to "20119" (silently wrong). mod-both gives the right 20.
    rows = parse_stats(load("stats_na.html"))
    assert rows[0]["k"] == 20.0
    assert rows[0]["k"] != 20119


def test_parse_stats_percent_columns_stripped():
    top = parse_stats(load("stats_na.html"))[0]
    assert top["kast"] == 78.0          # '78%' -> 78.0
    assert top["hs"] == 27.0
    assert top["clutch_pct"] == 20.0


def test_parse_stats_clutch_fraction_split():
    rows = parse_stats(load("stats_na.html"))
    assert (rows[0]["cl_won"], rows[0]["cl_played"]) == (3, 15)
    assert (rows[1]["cl_won"], rows[1]["cl_played"]) == (19, 104)
    assert rows[1]["player_id"] == "9999"


def test_parse_stats_empty_cells_become_null():
    low = parse_stats(load("stats_na.html"))[2]
    assert low["hs"] is None
    assert low["clutch_pct"] is None
    assert low["cl_won"] is None and low["cl_played"] is None
    assert low["kmax"] is None
    assert low["r2"] == 0.98  # present values still parse around the empties


def test_parse_stats_never_nan():
    rows = parse_stats(load("stats_na.html"))
    numeric = [k for k in _ROW_KEYS if k not in ("player", "player_id", "agents")]
    for r in rows:
        for k in numeric:
            v = r[k]
            assert v is None or (isinstance(v, (int, float)) and math.isfinite(v))


def test_parse_stats_no_table_returns_empty():
    assert parse_stats("<html><body>no table here</body></html>") == []


# ---------- service cache-write (the scheduled job) ----------
async def test_refresh_stats_writes_cache_with_ttl(monkeypatch):
    from app.core.config import get_settings

    captured: dict = {}

    async def fake_fetch(region, timespan):
        assert (region, timespan) == ("na", "all")
        return [{"player": "TenZ", "r2": 1.24}]

    async def fake_set(key, val, ttl):
        captured.update(key=key, val=val, ttl=ttl)

    monkeypatch.setattr(R.st, "fetch_stats", fake_fetch)
    monkeypatch.setattr(R, "cache_set", fake_set)

    n = await R.refresh_stats("na", "all")
    assert n == 1
    assert captured["key"] == R.CACHE_STATS.format(region="na", timespan="all")
    assert captured["ttl"] == get_settings().ttl_stats
    assert captured["val"] == [{"player": "TenZ", "r2": 1.24}]


async def test_refresh_all_stats_covers_every_combo(monkeypatch):
    seen: list[tuple[str, str]] = []

    async def fake_fetch(region, timespan):
        seen.append((region, timespan))
        return [{"player": "x"}]

    async def fake_set(key, val, ttl):
        pass

    monkeypatch.setattr(R.st, "fetch_stats", fake_fetch)
    monkeypatch.setattr(R, "cache_set", fake_set)

    total = await R.refresh_all_stats()
    assert set(seen) == {
        (region, ts) for region in R.STATS_REGIONS for ts in R.STATS_TIMESPANS
    }
    assert total == len(R.STATS_REGIONS) * len(R.STATS_TIMESPANS)


async def test_refresh_all_stats_skips_a_failing_combo(monkeypatch):
    async def fake_fetch(region, timespan):
        if (region, timespan) == ("na", "30d"):
            raise RuntimeError("vlr hiccup")
        return [{"player": "x"}]

    async def fake_set(key, val, ttl):
        pass

    monkeypatch.setattr(R.st, "fetch_stats", fake_fetch)
    monkeypatch.setattr(R, "cache_set", fake_set)

    # one combo raising does not abort the rest (7 of 8 succeed, 1 row each)
    total = await R.refresh_all_stats()
    assert total == len(R.STATS_REGIONS) * len(R.STATS_TIMESPANS) - 1


# ---------- route (reads cache only; envelope shape) ----------
async def test_stats_route_envelope_from_cache(monkeypatch):
    rows = parse_stats(load("stats_na.html"))

    async def fake_cache_get(key):
        assert key == R.CACHE_STATS.format(region="na", timespan="all")
        return rows

    monkeypatch.setattr(routes, "cache_get", fake_cache_get)

    resp = await routes.stats(region="na", timespan="all", min_rnd=0)
    assert set(resp.keys()) == {"data", "stale", "error"}
    assert resp["stale"] is False and resp["error"] is None
    assert len(resp["data"]) == 3


async def test_stats_route_min_rnd_filters(monkeypatch):
    rows = parse_stats(load("stats_na.html"))  # rnd = 512, 480, 40

    async def fake_cache_get(key):
        return rows

    monkeypatch.setattr(routes, "cache_get", fake_cache_get)

    resp = await routes.stats(region="na", timespan="all", min_rnd=100)
    # the 40-round low-sample player is dropped; the two real ones remain
    assert len(resp["data"]) == 2
    assert all((r["rnd"] or 0) >= 100 for r in resp["data"])


async def test_stats_route_uppercases_and_rejects_bad_region(monkeypatch):
    async def fake_cache_get(key):
        return []

    monkeypatch.setattr(routes, "cache_get", fake_cache_get)

    with pytest.raises(HTTPException) as ei:
        await routes.stats(region="world", timespan="all", min_rnd=0)
    assert ei.value.status_code == 400

    with pytest.raises(HTTPException):
        await routes.stats(region="na", timespan="7d", min_rnd=0)


async def test_stats_route_cold_miss_triggers_single_refresh(monkeypatch):
    calls = {"refresh": 0}
    state = {"cache": None}

    async def fake_cache_get(key):
        return state["cache"]

    async def fake_refresh(region, timespan):
        calls["refresh"] += 1
        state["cache"] = [{"player": "TenZ", "rnd": 500}]

    monkeypatch.setattr(routes, "cache_get", fake_cache_get)
    monkeypatch.setattr(R, "refresh_stats", fake_refresh)

    resp = await routes.stats(region="eu", timespan="90d", min_rnd=0)
    assert calls["refresh"] == 1
    assert resp["data"] == [{"player": "TenZ", "rnd": 500}]
