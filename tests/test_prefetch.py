"""Player pre-scrape job — pure shaping helpers + the CRITICAL cache gate.

The job orchestrates existing fetch paths (no new scraper), so the shaping is pure
and tests on row-like dicts; the orchestrator is exercised with every fetch mocked.
The cache gate is the load-bearing invariant: refresh_player writes a snapshot on
every call with no internal dedup, so the job MUST skip cache-present players —
otherwise it pollutes the very trend history it exists to build. We assert
refresh_player is NOT called for a cached player.
"""
import pytest

from app.services import refresh as R
from app.services.refresh import (
    eta_to_hours,
    match_is_tbd,
    participant_ids_from_match,
    prefetch_upcoming_players,
    roster_ids_from_team,
    upcoming_within_window,
)


# ---- eta parsing ------------------------------------------------------------
def test_eta_to_hours_parses_every_unit():
    assert eta_to_hours("17h 56m") == pytest.approx(17 + 56 / 60)
    assert eta_to_hours("1d 17h") == 41.0
    assert eta_to_hours("15h") == 15.0
    # weeks are summed too — '1w 1d' is 192h, NOT 24h (the probe-script trap)
    assert eta_to_hours("1w 1d") == 192.0


def test_eta_to_hours_none_when_unparseable():
    for bad in (None, "", "soon", "TBD"):
        assert eta_to_hours(bad) is None


# ---- TBD skip + window ------------------------------------------------------
def test_match_is_tbd():
    assert match_is_tbd({"teams": ["TBD", "TBD"]}) is True
    assert match_is_tbd({"teams": ["LEVIATÁN", "TBD"]}) is True
    assert match_is_tbd({"teams": ["", "G2"]}) is True
    assert match_is_tbd({"teams": []}) is True
    assert match_is_tbd({"teams": ["LEVIATÁN", "Team Heretics"]}) is False


def test_upcoming_within_window_filters_tbd_and_far_matches():
    up = [
        {"id": "a", "teams": ["G2", "FUT"], "eta": "15h"},          # in
        {"id": "b", "teams": ["PRX", "VIT"], "eta": "1d 17h"},      # in (41h)
        {"id": "c", "teams": ["TBD", "TBD"], "eta": "10h"},         # TBD -> out
        {"id": "d", "teams": ["AB3", "Chivas"], "eta": "1w 1d"},    # 192h -> out
        {"id": "e", "teams": ["X", "Y"], "eta": None},              # no eta -> out
    ]
    got = [m["id"] for m in upcoming_within_window(up, window_hours=48)]
    assert got == ["a", "b"]


# ---- id extraction ----------------------------------------------------------
def test_participant_ids_from_match_dedupes_across_maps_and_aggregate():
    parsed = {
        "maps": [
            {"teams": [
                {"players": [{"player_id": "1"}, {"player_id": "2"}]},
                {"players": [{"player_id": "3"}, {"player_id": None}]},  # null dropped
            ]},
            {"teams": [
                {"players": [{"player_id": "1"}]},  # repeat across maps -> deduped
                {"players": [{"player_id": "4"}]},
            ]},
        ],
        "all_maps": {"teams": [{"players": [{"player_id": "5"}]}]},
    }
    assert participant_ids_from_match(parsed) == ["1", "2", "3", "4", "5"]


def test_participant_ids_empty_when_no_lineup_posted():
    assert participant_ids_from_match({"maps": [], "all_maps": None}) == []


def test_roster_ids_from_team_excludes_staff():
    team = {"roster": [
        {"player_id": "10", "is_staff": False},
        {"player_id": "11", "is_staff": True},   # coach -> excluded
        {"player_id": None, "is_staff": False},  # no id -> dropped
        {"player_id": "12", "is_staff": False},
    ]}
    assert roster_ids_from_team(team) == ["10", "12"]


# ---- the cache gate (the whole point) ---------------------------------------
def _wire(monkeypatch, *, matches, match_players, cached, fetch_team=None):
    """Mock the four fetch boundaries the orchestrator touches and record which
    player ids reach refresh_player. `cached` is the set of ids that look fresh."""
    async def fake_fetch_upcoming():
        return {"live": [], "upcoming": matches}

    async def fake_fetch_match(mid):
        pids = match_players.get(mid, [])
        return {
            "maps": [{"teams": [{"players": [{"player_id": p} for p in pids]}]}],
            "all_maps": None,
            "teams": [{"id": "t1"}, {"id": "t2"}],  # used only on the fallback path
        }

    async def fake_cache_get(key):
        return {"cached": True} if any(key.endswith(f":{c}") for c in cached) else None

    refreshed: list[str] = []

    async def fake_refresh_player(pid):
        refreshed.append(pid)
        return {"id": pid}

    monkeypatch.setattr(R.mt, "fetch_upcoming", fake_fetch_upcoming)
    monkeypatch.setattr(R.md, "fetch_match", fake_fetch_match)
    monkeypatch.setattr(R, "cache_get", fake_cache_get)
    monkeypatch.setattr(R, "refresh_player", fake_refresh_player)
    if fetch_team is not None:
        monkeypatch.setattr(R.te, "fetch_team", fetch_team)
    return refreshed


async def test_cache_present_player_is_skipped_not_refetched(monkeypatch):
    matches = [
        {"id": "m1", "teams": ["G2", "FUT"], "eta": "15h"},
        {"id": "m2", "teams": ["PRX", "VIT"], "eta": "1d 17h"},
        {"id": "x", "teams": ["TBD", "TBD"], "eta": "10h"},  # skipped before any fetch
    ]
    match_players = {"m1": ["1", "2", "3"], "m2": ["3", "4"]}  # 3 overlaps -> deduped
    refreshed = _wire(monkeypatch, matches=matches, match_players=match_players, cached={"2"})

    summary = await prefetch_upcoming_players(window_hours=48)

    # the cached player ("2") was NEVER handed to refresh_player — no duplicate row
    assert "2" not in refreshed
    assert sorted(refreshed) == ["1", "3", "4"]
    assert summary == {"matches": 2, "players": 4, "fetched": 3, "skipped": 1, "failed": 0}


async def test_all_cached_means_zero_refreshes(monkeypatch):
    matches = [{"id": "m1", "teams": ["G2", "FUT"], "eta": "15h"}]
    refreshed = _wire(
        monkeypatch, matches=matches, match_players={"m1": ["1", "2"]}, cached={"1", "2"}
    )
    summary = await prefetch_upcoming_players()
    assert refreshed == []  # nothing refetched -> no duplicate snapshots
    assert summary["fetched"] == 0 and summary["skipped"] == 2


async def test_falls_back_to_team_rosters_when_no_lineup(monkeypatch):
    async def fake_fetch_team(tid):
        rosters = {
            "t1": {"roster": [
                {"player_id": "10", "is_staff": False},
                {"player_id": "11", "is_staff": True},  # staff excluded
            ]},
            "t2": {"roster": [{"player_id": "12", "is_staff": False}]},
        }
        return rosters[tid]

    matches = [{"id": "m1", "teams": ["G2", "FUT"], "eta": "15h"}]
    # match has NO scoreboard players -> orchestrator falls back to team rosters
    refreshed = _wire(
        monkeypatch, matches=matches, match_players={"m1": []}, cached=set(),
        fetch_team=fake_fetch_team,
    )
    summary = await prefetch_upcoming_players()
    assert sorted(refreshed) == ["10", "12"]  # the two active players, not the coach
    assert summary["fetched"] == 2
