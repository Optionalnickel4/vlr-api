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
# stats_na.html holds 5 REAL rows captured live (region=na, timespan=all,
# 2026-07-14): slowly/keiko/Derke/FT/Neon. Deliberately picked for a spread of
# invariant states (clutched vs never-clutched, Rnd 105..630) — but every
# assertion below checks STRUCTURE/TYPE/invariant, never a specific live
# rating/ACS/K:D number, since those drift on every future recapture.
def test_parse_stats_row_count_and_full_key_set():
    rows = parse_stats(load("stats_na.html"))
    assert len(rows) == 5
    # every row carries the complete, stable key set (null where absent)
    for r in rows:
        assert set(r.keys()) == set(_ROW_KEYS)


def test_parse_stats_identity_and_headline():
    rows = parse_stats(load("stats_na.html"))
    for r in rows:
        assert isinstance(r["player"], str) and r["player"].strip()
        assert r["player_id"] and r["player_id"].isdigit()
    # "R" (formerly "R2.0") is VLR's own rating headline — a float, at 100% fill
    assert all(isinstance(r["r2"], float) for r in rows)


def test_parse_stats_prefers_mod_both_when_side_split_present():
    # vlr's current /stats markup no longer side-splits value cells (plain td
    # text now), but the coercion helper still prefers span.mod-both when
    # present — the same contract MATCH_SB_VAL_BOTH relies on for the match
    # scoreboard — in case vlr reintroduces the split. Raw td.text() would
    # wrongly concatenate mod-both/mod-t/mod-ct into "20119".
    html = """
    <table class="st-table"><thead><tr>
      <th class="mod-player">Player</th><th data-col="k">K</th>
    </tr></thead><tbody><tr>
      <td class="mod-player"><a href="/player/1/x"><div class="text-of">x</div></a></td>
      <td data-col="k"><span class="mod-both">20</span><span class="mod-t">11</span><span class="mod-ct">9</span></td>
    </tr></tbody></table>
    """
    rows = parse_stats(html)
    assert rows[0]["k"] == 20.0
    assert rows[0]["k"] != 20119


def test_parse_stats_percent_columns_stripped():
    rows = parse_stats(load("stats_na.html"))
    # every row on this slice has KAST/HS filled — a clean %-strip to a 0..100 float
    for r in rows:
        for key in ("kast", "hs"):
            assert isinstance(r[key], float) and 0.0 <= r[key] <= 100.0
    # CL% is null exactly where the row never clutched (see clutch-fraction test)
    for r in rows:
        assert r["clutch_pct"] is None or (isinstance(r["clutch_pct"], float) and 0.0 <= r["clutch_pct"] <= 100.0)


def test_parse_stats_clutch_fraction_split():
    rows = parse_stats(load("stats_na.html"))
    by_player = {r["player"]: r for r in rows}
    # keiko/Derke/Neon clutched at least once this window -> a clean won/played split
    for name in ("keiko", "Derke", "Neon"):
        r = by_player[name]
        assert isinstance(r["cl_won"], int) and isinstance(r["cl_played"], int)
        assert 0 <= r["cl_won"] <= r["cl_played"]
    # slowly/FT never clutched -> td class="mod-empty" -> both null, never a false 0
    for name in ("slowly", "FT"):
        r = by_player[name]
        assert r["cl_won"] is None and r["cl_played"] is None


def test_parse_stats_empty_clutch_does_not_break_other_fields():
    # a null CL/CL% is column-local — every OTHER stat on the same row still
    # coerces normally around it (present values parse fine around the empties).
    rows = parse_stats(load("stats_na.html"))
    by_player = {r["player"]: r for r in rows}
    for name in ("slowly", "FT"):
        r = by_player[name]
        assert r["clutch_pct"] is None
        assert isinstance(r["r2"], float)
        assert isinstance(r["acs"], float)


def test_parse_stats_never_nan():
    rows = parse_stats(load("stats_na.html"))
    numeric = [k for k in _ROW_KEYS if k not in ("player", "player_id", "team", "agents")]
    for r in rows:
        for k in numeric:
            v = r[k]
            assert v is None or (isinstance(v, (int, float)) and math.isfinite(v))


def test_parse_stats_team_present_for_every_row():
    rows = parse_stats(load("stats_na.html"))
    assert all(isinstance(r["team"], str) and r["team"].strip() for r in rows)


def test_parse_stats_alias_no_team_bleed():
    # Alias must come from div.text-of only — the team tag in div.st-pl-country
    # must never concatenate into the alias string (raw cell text is e.g.
    # "slowlyTYL", "keikoNRG" — exactly the label-bleed trap this guards against).
    rows = parse_stats(load("stats_na.html"))
    for r in rows:
        assert r["player"] and r["team"]
        assert not r["player"].endswith(r["team"])
        assert r["team"] not in r["player"]


def test_parse_stats_team_null_when_div_absent():
    # a genuinely teamless (free-agent) row has no div.st-pl-country at all —
    # team must resolve to None, never crash. None of the five real rows in
    # stats_na.html happen to be teamless, so this exercises the null-safe
    # guard directly against a minimal synthetic snippet.
    html = """
    <table class="st-table"><thead><tr><th class="mod-player">Player</th></tr></thead>
    <tbody><tr><td class="mod-player"><a href="/player/1/loner">
      <div class="text-of">loner</div></a></td></tr></tbody></table>
    """
    rows = parse_stats(html)
    assert rows[0]["team"] is None


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
    assert len(resp["data"]) == 5


async def test_stats_route_min_rnd_filters(monkeypatch):
    rows = parse_stats(load("stats_na.html"))  # rnd = 280, 404, 383, 105, 630

    async def fake_cache_get(key):
        return rows

    monkeypatch.setattr(routes, "cache_get", fake_cache_get)

    resp = await routes.stats(region="na", timespan="all", min_rnd=300)
    # the two players below the 300-round threshold (105, 280) are dropped
    assert len(resp["data"]) == 3
    assert all((r["rnd"] or 0) >= 300 for r in resp["data"])


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
