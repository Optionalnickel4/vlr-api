"""Live match auto-refresh — status-aware match TTL + the live-refresh job.

Mirrors the other service suites: every fetch boundary is mocked, no network, no
DB. Two pieces: refresh_match picks a SHORT ttl for a live match and the LONG ttl
otherwise; refresh_live_matches re-scrapes each currently-live match (and only
those), repopulating the live list on a cache miss.
"""
from app.core.config import get_settings
from app.services import refresh as R


# ---- status-aware TTL on refresh_match --------------------------------------
async def _capture_ttl(monkeypatch, status):
    captured: dict = {}

    async def fake_fetch(mid):
        return {"id": mid, "status": status, "maps": []}

    async def fake_set(key, val, ttl):
        captured["key"] = key
        captured["ttl"] = ttl

    monkeypatch.setattr(R.md, "fetch_match", fake_fetch)
    monkeypatch.setattr(R, "cache_set", fake_set)
    await R.refresh_match("670473")
    return captured


async def test_live_match_caches_with_short_ttl(monkeypatch):
    cap = await _capture_ttl(monkeypatch, "live")
    s = get_settings()
    assert cap["ttl"] == s.ttl_live  # ~30s, not the 10-min default
    assert cap["ttl"] != s.ttl_matches
    assert cap["key"] == R.CACHE_MATCH.format(id="670473")


async def test_completed_match_keeps_long_ttl(monkeypatch):
    cap = await _capture_ttl(monkeypatch, "final")
    assert cap["ttl"] == get_settings().ttl_matches


async def test_unknown_status_keeps_long_ttl(monkeypatch):
    # status None (an upcoming / unparsed match) is not live -> long ttl
    cap = await _capture_ttl(monkeypatch, None)
    assert cap["ttl"] == get_settings().ttl_matches


# ---- the live-refresh job ---------------------------------------------------
async def test_refresh_live_matches_refreshes_only_live_matches(monkeypatch):
    live = [{"id": "670473"}, {"id": "670472"}, {"id": None}]  # null id skipped
    refreshed: list[str] = []

    async def fake_cache_get(key):
        assert key == R.CACHE_LIVE  # reads the live list, nothing else
        return live

    async def fake_refresh_match(mid):
        refreshed.append(mid)
        return {"id": mid}

    async def boom_upcoming():
        raise AssertionError("must not repopulate when the live list is present")

    monkeypatch.setattr(R, "cache_get", fake_cache_get)
    monkeypatch.setattr(R, "refresh_match", fake_refresh_match)
    monkeypatch.setattr(R, "refresh_upcoming", boom_upcoming)

    n = await R.refresh_live_matches()
    assert refreshed == ["670473", "670472"]  # both live ids, the null skipped
    assert n == 2


async def test_refresh_live_matches_noop_when_nothing_live(monkeypatch):
    async def empty_list(key):
        return []

    async def boom(*a, **k):
        raise AssertionError("no match refresh when the live list is empty")

    monkeypatch.setattr(R, "cache_get", empty_list)
    monkeypatch.setattr(R, "refresh_match", boom)
    assert await R.refresh_live_matches() == 0


async def test_refresh_live_matches_repopulates_list_on_cache_miss(monkeypatch):
    # CACHE_LIVE is written on a longer cadence than its TTL, so a miss must
    # repopulate (one list scrape) rather than skip the whole cycle.
    calls = {"upcoming": 0}
    state: dict = {"live": None}

    async def fake_cache_get(key):
        return state["live"]

    async def fake_upcoming():
        calls["upcoming"] += 1
        state["live"] = [{"id": "9"}]  # now populated

    refreshed: list[str] = []

    async def fake_refresh_match(mid):
        refreshed.append(mid)

    monkeypatch.setattr(R, "cache_get", fake_cache_get)
    monkeypatch.setattr(R, "refresh_upcoming", fake_upcoming)
    monkeypatch.setattr(R, "refresh_match", fake_refresh_match)

    n = await R.refresh_live_matches()
    assert calls["upcoming"] == 1 and refreshed == ["9"] and n == 1
