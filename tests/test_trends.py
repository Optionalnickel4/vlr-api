"""Pure-function tests for the team trend shaping — no DB, no network.

The service splits the DB query from the shaping so everything below runs on
row-like dicts. The point of these tests is the data-shape contract: rating/rank/
scores arrive as raw TEXT and must be coerced numerically and defensively.
"""
from datetime import datetime, timedelta, timezone

from app.services.trends import (
    build_response,
    build_rating_trend,
    build_results,
    coerce_float,
    coerce_int,
    derive_result,
    rating_change,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def at(days: int) -> datetime:
    return T0 + timedelta(days=days)


def snap(rating, rank="1", team="Sentinels", days=0):
    return {"captured_at": at(days), "rating": rating, "rank": rank, "team": team}


# ---- coercion ---------------------------------------------------------------
def test_rating_coercion_parses_numeric_string():
    assert coerce_float("1024") == 1024.0
    assert coerce_float("  998 ") == 998.0


def test_rating_coercion_skips_garbage():
    for bad in ("N/A", "", None, "abc"):
        assert coerce_float(bad) is None


def test_int_coercion():
    assert coerce_int("3") == 3
    assert coerce_int("N/A") is None
    assert coerce_int(None) is None


def test_unparseable_rating_point_is_skipped_not_crashed():
    rows = [snap("1024", days=0), snap("N/A", days=1), snap("", days=2), snap("1031", days=3)]
    trend = build_rating_trend(rows)
    assert [p["rating"] for p in trend] == [1024.0, 1031.0]  # the two parseable only


# ---- rating_change ----------------------------------------------------------
def test_rating_change_last_minus_first():
    trend = build_rating_trend([snap("998", days=0), snap("1024", days=1)])
    assert rating_change(trend) == 26.0


def test_rating_change_null_with_fewer_than_two_points():
    assert rating_change([]) is None
    assert rating_change(build_rating_trend([snap("1024", days=0)])) is None


# ---- win/loss derivation ----------------------------------------------------
def test_win_when_on_side_a_with_higher_score():
    assert derive_result("Sentinels", "Sentinels", "NRG", "2", "1") == "win"


def test_loss_when_on_side_a_with_lower_score():
    assert derive_result("Sentinels", "Sentinels", "NRG", "0", "2") == "loss"


def test_win_when_on_side_b():
    assert derive_result("Sentinels", "NRG", "Sentinels", "1", "2") == "win"


def test_result_is_case_insensitive_on_name():
    assert derive_result("sentinels", "SENTINELS", "NRG", "2", "0") == "win"


def test_unparseable_score_yields_null_result_no_crash():
    assert derive_result("Sentinels", "Sentinels", "NRG", "TBD", "1") is None


def test_result_null_when_team_on_neither_side():
    assert derive_result("Sentinels", "NRG", "LOUD", "2", "1") is None


# ---- string-sort trap guard -------------------------------------------------
def test_string_sort_trap_ratings_ordered_numerically_not_lexically():
    # As strings, max(["998","1024","1003"]) == "998" (wrong) and they'd sort
    # 1003,1024,998. Numerically peak is 1024 and current (chrono last) is 1003.
    rows = [snap("998", days=0), snap("1024", days=1), snap("1003", days=2)]
    resp = build_response("2", 90, rows, [])
    assert [p["rating"] for p in resp["rating_trend"]] == [998.0, 1024.0, 1003.0]
    assert resp["summary"]["peak_rating"] == 1024.0   # numeric max, not "998"
    assert resp["summary"]["current_rating"] == 1003.0
    # and the parseable set ordered numerically is the spec's expectation
    assert sorted(p["rating"] for p in resp["rating_trend"]) == [998.0, 1003.0, 1024.0]


def test_trend_is_chronological_even_if_rows_arrive_unordered():
    rows = [snap("1024", days=2), snap("998", days=0), snap("1003", days=1)]
    trend = build_rating_trend(rows)
    assert [p["captured_at"] for p in trend] == [at(0), at(1), at(2)]
    assert [p["rating"] for p in trend] == [998.0, 1003.0, 1024.0]


# ---- empty / garbage input --------------------------------------------------
def test_empty_input_is_valid_empty_response():
    resp = build_response("2", 90, [], [])
    assert resp["team_id"] == "2"
    assert resp["team"] is None
    assert resp["rating_trend"] == []
    assert resp["rating_change"] is None
    assert resp["results_in_window"] == []
    assert resp["summary"] == {
        "points": 0, "wins": 0, "losses": 0,
        "current_rating": None, "peak_rating": None,
    }
    assert "note" in resp  # no name resolved -> surfaced, not an error


def test_all_garbage_ratings_produce_no_points_no_crash():
    rows = [snap("N/A", days=0), snap("", days=1), snap(None, days=2)]
    resp = build_response("2", 90, rows, [])
    assert resp["rating_trend"] == []
    assert resp["summary"]["points"] == 0
    assert resp["team"] == "Sentinels"  # name still resolves from the rows


# ---- results matching + full response ---------------------------------------
def test_build_results_matches_by_name_and_counts_win_loss():
    rows = [
        {"vlr_id": "1", "team_a": "Sentinels", "team_b": "NRG",
         "score_a": "2", "score_b": "0", "event": "VCT", "captured_at": at(1)},
        {"vlr_id": "2", "team_a": "LOUD", "team_b": "Sentinels",
         "score_a": "2", "score_b": "1", "event": "VCT", "captured_at": at(2)},
        {"vlr_id": "3", "team_a": "G2", "team_b": "C9",  # not our team -> excluded
         "score_a": "2", "score_b": "0", "event": "VCT", "captured_at": at(3)},
    ]
    out = build_results(rows, "Sentinels")
    assert [m["vlr_id"] for m in out] == ["1", "2"]
    assert out[0] == {
        "vlr_id": "1", "opponent": "NRG", "result": "win",
        "score": "2:0", "event": "VCT", "captured_at": at(1),
    }
    assert out[1]["opponent"] == "LOUD" and out[1]["result"] == "loss"


def test_full_response_summary_counts():
    snaps = [snap("1000", days=0), snap("1031", days=1), snap("1024", days=2)]
    results = [
        {"vlr_id": "1", "team_a": "Sentinels", "team_b": "NRG",
         "score_a": "2", "score_b": "0", "event": "VCT", "captured_at": at(1)},
        {"vlr_id": "2", "team_a": "Sentinels", "team_b": "LOUD",
         "score_a": "0", "score_b": "2", "event": "VCT", "captured_at": at(2)},
    ]
    resp = build_response("2", 90, snaps, results)
    assert resp["team"] == "Sentinels"
    assert resp["rating_change"] == 24.0  # 1024 - 1000
    assert resp["summary"]["peak_rating"] == 1031.0
    assert resp["summary"]["current_rating"] == 1024.0
    assert resp["summary"]["wins"] == 1 and resp["summary"]["losses"] == 1
