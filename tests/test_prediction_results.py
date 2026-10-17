from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services.prediction_results import confirmed_result

NOW = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)


def record():
    return SimpleNamespace(match_id="123", starts_at=NOW-timedelta(hours=2),
        generated_at=NOW-timedelta(days=1), evidence={"teams": [{"id": "1"}, {"id": "2"}]})


def detail():
    return {"id": "123", "status": "final", "teams": [
        {"id": "1", "score": 1, "won": False}, {"id": "2", "score": 2, "won": True}]}


def test_final_winner_is_verified_by_id_even_when_sides_swap():
    d = detail()
    d["teams"].reverse()
    assert confirmed_result(record(), d, NOW) == {"match_id": "123", "winner_id": "2",
        "scores": {"2": 2, "1": 1}, "checked_at": NOW}


@pytest.mark.parametrize("change", [{"status": "live"}, {"status": "upcoming"},
    {"status": "cancelled"}, {"id": "999"}, {"teams": []},
    {"teams": [{"id": "1", "score": 0}, {"id": "3", "score": 2}]},
    {"teams": [{"id": "1", "score": 2}, {"id": "2", "score": 2}]},
    {"teams": [{"id": "1", "score": None}, {"id": "2", "score": 2}]},
    {"teams": [{"id": "1", "score": True}, {"id": "2", "score": 2}]},
    {"teams": [{"id": "1", "score": 1.5}, {"id": "2", "score": 2}]},
    {"teams": [{"id": "1", "score": 1, "won": True}, {"id": "2", "score": 2}]}])
def test_unconfirmed_and_inconsistent_results_are_not_graded(change):
    assert confirmed_result(record(), detail() | change, NOW) is None


def test_future_and_post_start_predictions_are_not_graded():
    r = record()
    r.starts_at = NOW+timedelta(hours=1)
    assert confirmed_result(r, detail(), NOW) is None
    r = record()
    r.generated_at = r.starts_at
    assert confirmed_result(r, detail(), NOW) is None
