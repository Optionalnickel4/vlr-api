from copy import deepcopy
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from app.services import predictions as P

NOW = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)


def detail():
    return {"starts_at": (NOW + timedelta(hours=24)).isoformat(), "status": "upcoming",
            "teams": [{"id": "1", "name": "Alpha"}, {"id": "2", "name": "Beta"}], "maps": []}


def team(tid, wins):
    return {"id": tid, "results": [
        {"id": str(100 + n), "date": (NOW - timedelta(days=n + 1)).date().isoformat(),
         "result": "win" if n < wins else "loss", "opponent": "Opponent"}
        for n in range(5)]}


def evidence():
    return P.build_evidence("999", detail(), [team("1", 4), team("2", 2)], NOW)


def answer():
    return {"winner_id": "1", "explanation": "Alpha has stronger recent results in this sample.",
            "evidence_ids": ["form:1", "form:2"], "caveats": ["Opponents differ."]}


@pytest.mark.parametrize("change", [
    {"starts_at": None}, {"starts_at": NOW.isoformat()}, {"status": "live"},
    {"starts_at": (NOW + timedelta(days=8)).isoformat()},
    {"maps": [{"rounds": [{"winner": 1}]}]},
    {"teams": [{"id": "1", "name": "Alpha"}, {"id": "2", "name": "TBD"}]},
])
def test_unknown_started_and_unconfirmed_fixtures_abstain(change):
    candidate = detail() | change
    assert not P.eligible_detail(candidate, NOW)


def test_seven_day_window_includes_boundary_but_excludes_later_matches():
    assert P.eligible_detail(detail() | {"starts_at": (NOW + timedelta(days=7)).isoformat()}, NOW)
    assert not P.eligible_detail(detail() | {"starts_at": (NOW + timedelta(days=7, seconds=1)).isoformat()}, NOW)


def test_evidence_excludes_same_day_future_target_and_duplicate_results():
    first = team("1", 4)
    first["results"] += [deepcopy(first["results"][0]),
        {"id": "999", "date": "2026-10-07", "result": "win"},
        {"id": "888", "date": "2026-10-08", "result": "win"},
        {"id": "777", "date": "2026-10-09", "result": "win"}]
    snapshot = P.build_evidence("999", detail(), [first, team("2", 2)], NOW)
    matches = snapshot["facts"][0]["matches"]
    assert len(matches) == 5
    assert {m["match_id"] for m in matches} == {str(100 + n) for n in range(5)}


def test_sparse_or_wrong_team_history_cannot_reach_model():
    sparse = team("1", 2)
    sparse["results"] = sparse["results"][:2]
    with pytest.raises(P.EvidenceUnavailable):
        P.build_evidence("999", detail(), [sparse, team("2", 2)], NOW)
    with pytest.raises(P.EvidenceUnavailable):
        P.build_evidence("999", detail(), [team("3", 4), team("2", 2)], NOW)


@pytest.mark.parametrize("change", [
    {"winner_id": "3"}, {"evidence_ids": ["form:1", "invented"]},
    {"evidence_ids": ["form:1", "form:1"]}, {"explanation": "Alpha has a 70% chance."},
    {"explanation": "Alpha will win 2-0."}, {"caveats": []}, {"extra": "unexpected"},
])
def test_invalid_or_out_of_scope_model_output_is_rejected(change):
    with pytest.raises(ValueError):
        P.validate_answer(answer() | change, evidence())


def test_no_pick_is_supported_without_inventing_a_winner():
    assert P.validate_answer(answer() | {"winner_id": None}, evidence())["winner_id"] is None


async def test_changed_fixture_after_inference_is_not_saved(monkeypatch):
    monkeypatch.setattr(P.R, "refresh_match", AsyncMock(return_value={}))
    current = detail()
    current["teams"][1] = {"id": "3", "name": "Gamma"}
    monkeypatch.setattr(P, "_exists", AsyncMock(return_value=False))
    monkeypatch.setattr(P, "_fresh_detail", AsyncMock(side_effect=[detail(), current]))
    monkeypatch.setattr(P, "_team", AsyncMock(side_effect=[team("1", 4), team("2", 2)]))
    monkeypatch.setattr(P, "request_prediction", AsyncMock(return_value=answer()))
    save = AsyncMock()
    monkeypatch.setattr(P, "_save", save)
    class Clock(datetime):
        @staticmethod
        def now(tz):
            return NOW
    monkeypatch.setattr(P, "datetime", Clock)
    assert await P.generate_one("999", "lease", "owner") is False
    save.assert_not_awaited()
