from copy import deepcopy
from unittest.mock import AsyncMock

import pytest

from app.services.prediction_evidence import add_history, enrich


def fixture():
    evidence = {"teams": [{"id": "1"}, {"id": "2"}], "limitations": [], "facts": [
        {"team_id": tid, "matches": [{"match_id": "100", "date": "2026-10-07", "result": result}]}
        for tid, result in (("1", "win"), ("2", "loss"))]}
    teams = [{"id": tid, "name": tid, "roster": [{"player_id": pid, "alias": "Player", "is_staff": False},
                                                       {"player_id": "99", "is_staff": True}]}
             for tid, pid in (("1", "10"), ("2", "20"))]
    match = {"id": "100", "status": "final", "teams": [
        {"id": "1", "name": "1", "score": 2}, {"id": "2", "name": "2", "score": 0}],
        "maps": [{"game_id": "5", "name": "Haven", "scores": [13, 7], "teams": [
            {"name": "1", "players": [{"player_id": pid, "stats": {"ACS": {"value": 250}}} for pid in ("10", "99", "88")]},
            {"name": "2", "players": [{"player_id": "20", "stats": {"ACS": {"value": 180}}}]}]}]}
    return evidence, teams, match


def test_h2h_map_and_current_roster_stats_are_corroborated_and_deduplicated():
    evidence, teams, match = fixture()
    match["maps"].append(deepcopy(match["maps"][0]))
    result = add_history(evidence, teams, {"100": match})
    facts = {f["id"]: f for f in result["facts"][2:]}
    assert set(facts) == {f"{kind}:{tid}" for kind in ("h2h", "maps", "players") for tid in ("1", "2")}
    assert len(facts["maps:1"]["samples"]["Haven"]) == 1
    assert set(facts["players:1"]["samples"]) == {"10"}
    assert "250.00 over 1 maps" in facts["players:1"]["text"]
    assert "0 wins and 1 losses" in facts["h2h:2"]["text"]


@pytest.mark.parametrize("change", [{"id": "101"}, {"status": "live"},
    {"teams": [{"id": "3", "score": 2}, {"id": "4", "score": 0}]},
    {"teams": [{"id": "1", "score": 0}, {"id": "2", "score": 2}]}])
def test_wrong_identity_status_and_conflicting_results_excluded(change):
    evidence, teams, match = fixture()
    assert len(add_history(evidence, teams, {"100": match | change})["facts"]) == 2


@pytest.mark.parametrize("change", [{"name": None}, {"scores": [0, 0]}, {"scores": [13, 12]},
                                   {"scores": [float('nan'), 13]}, {"teams": []}])
def test_unplayed_unnamed_and_malformed_maps_excluded(change):
    evidence, teams, match = fixture()
    match["maps"][0].update(change)
    facts = add_history(evidence, teams, {"100": match})["facts"][2:]
    assert [f["id"] for f in facts] == ["h2h:1", "h2h:2"]


def test_missing_roster_does_not_import_historical_players():
    evidence, teams, match = fixture()
    teams[0]["roster"] = []
    result = add_history(evidence, teams, {"100": match})
    assert "players:1" not in {f.get("id") for f in result["facts"]}
    assert any("current-roster" in s for s in result["limitations"])


@pytest.mark.asyncio
async def test_optional_api_failure_preserves_form_and_explicit_missing_coverage():
    evidence, teams, _ = fixture()
    load = AsyncMock(side_effect=TimeoutError)
    result = await enrich(evidence, teams, load)
    load.assert_awaited_once_with("100")
    assert len(result["facts"]) == 2
    assert any("no verified head-to-head" in s for s in result["limitations"])
