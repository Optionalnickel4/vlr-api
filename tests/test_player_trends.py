"""Pure-function tests for the player trend shaping (Phase 8) — no DB, no network.

Mirrors tests/test_trends.py: the service splits the DB query from the shaping, so
everything below runs on row-like dicts. The contract is the same data-shape
discipline as team trends — per-agent stats arrive as raw TEXT and must be coerced
numerically and defensively, ordered on captured_at, never string-compared.
"""
from datetime import datetime, timedelta, timezone

from app.services.trends import (
    aggregate_player_stats,
    build_player_response,
    build_player_trend,
    latest_player_field,
    metric_change,
)

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def at(days: int) -> datetime:
    return T0 + timedelta(days=days)


def agent(rating, acs="250", rnd="100", name="jett"):
    """One per-agent stat row as the scraper stores it (raw TEXT values)."""
    return {"agent": name, "stats": {"Rating": rating, "ACS": acs, "RND": rnd}}


def psnap(rating, acs="250", rnd="100", alias="TenZ", team="Sentinels", days=0):
    """A player snapshot row with a single agent stat row."""
    return {
        "captured_at": at(days),
        "alias": alias,
        "team": team,
        "agent_stats": [agent(rating, acs, rnd)],
    }


# ---- aggregation (per-agent -> one rounds-weighted point) --------------------
def test_aggregate_is_rounds_weighted_across_agents():
    # 1.20 over 100 rounds vs 1.00 over 100 rounds -> 1.10; a 4000-round agent
    # would dominate, which is the point (honest overall, not a flat mean).
    rows = [agent("1.20", "300", "100"), agent("1.00", "200", "100")]
    out = aggregate_player_stats(rows)
    assert out["rating"] == 1.10
    assert out["acs"] == 250.0
    assert out["rounds"] == 200


def test_aggregate_weight_dominated_by_high_round_agent():
    rows = [agent("1.40", "300", "900"), agent("0.40", "100", "100")]
    out = aggregate_player_stats(rows)
    # (1.40*900 + 0.40*100) / 1000 = 1.30, not the flat mean 0.90
    assert out["rating"] == 1.30


def test_aggregate_string_values_coerced_to_numbers():
    out = aggregate_player_stats([agent("1.17", "263.8", "4306")])
    assert isinstance(out["rating"], float) and out["rating"] == 1.17
    assert isinstance(out["acs"], float) and out["acs"] == 263.8
    assert out["rounds"] == 4306


def test_aggregate_skips_agent_row_whose_rating_wont_parse():
    rows = [agent("N/A", "999", "100"), agent("1.00", "200", "100")]
    out = aggregate_player_stats(rows)
    assert out["rating"] == 1.00  # the garbage row contributed nothing
    assert out["acs"] == 200.0
    assert out["rounds"] == 100


def test_aggregate_none_when_no_agent_row_parses():
    assert aggregate_player_stats([agent("N/A"), agent(""), agent(None)]) is None
    assert aggregate_player_stats([]) is None
    assert aggregate_player_stats(None) is None


def test_aggregate_rounds_fallback_weight_when_rnd_unparseable():
    # rating parses but RND doesn't -> weight falls back to 1 so it still counts;
    # (1.0*1 + 2.0*3)/4 = 1.75. total rounds counts only the parseable RND (3).
    rows = [agent("1.00", "200", "N/A"), agent("2.00", "300", "3")]
    out = aggregate_player_stats(rows)
    assert out["rating"] == 1.75
    assert out["rounds"] == 3


def test_aggregate_acs_null_without_dropping_rating():
    out = aggregate_player_stats([agent("1.10", "N/A", "100")])
    assert out["rating"] == 1.10
    assert out["acs"] is None  # ACS unparseable -> null, rating still kept


# ---- chronological ordering / string-sort trap ------------------------------
def test_trend_is_chronological_even_if_rows_arrive_unordered():
    rows = [psnap("1.10", days=2), psnap("0.95", days=0), psnap("1.03", days=1)]
    trend = build_player_trend(rows)
    assert [p["captured_at"] for p in trend] == [at(0), at(1), at(2)]
    assert [p["rating"] for p in trend] == [0.95, 1.03, 1.10]  # capture order, not value


def test_string_sort_trap_acs_ordered_numerically_not_lexically():
    # The lexical trap bites on ACS magnitudes: as strings "1024" < "998" (since
    # '1' < '9') and max(["998","1024","1003"]) == "998" (wrong). Numerically peak
    # is 1024 and current (chrono last) is 1003 — must hold despite scrambled input.
    rows = [psnap("1.00", "1024", days=1), psnap("1.00", "998", days=0), psnap("1.00", "1003", days=2)]
    resp = build_player_response("9", 90, rows)
    assert [p["acs"] for p in resp["rating_trend"]] == [998.0, 1024.0, 1003.0]
    assert resp["summary"]["peak_acs"] == 1024.0  # numeric max, not "998"
    assert resp["summary"]["current_acs"] == 1003.0
    assert sorted(p["acs"] for p in resp["rating_trend"]) == [998.0, 1003.0, 1024.0]


# ---- metric_change ----------------------------------------------------------
def test_metric_change_last_minus_first():
    trend = build_player_trend([psnap("1.00", acs="200", days=0), psnap("1.20", acs="260", days=1)])
    assert metric_change(trend, "rating") == 0.20
    assert metric_change(trend, "acs") == 60.0


def test_metric_change_null_with_fewer_than_two_points():
    assert metric_change([], "rating") is None
    assert metric_change(build_player_trend([psnap("1.00", days=0)]), "rating") is None


# ---- full response shape + summary ------------------------------------------
def test_response_shape_mirrors_team_trend():
    rows = [psnap("1.00", acs="200", days=0), psnap("1.31", acs="280", days=1), psnap("1.24", acs="260", days=2)]
    resp = build_player_response("9", 90, rows)
    assert resp["player_id"] == "9"
    assert resp["player"] == "TenZ"
    assert resp["team"] == "Sentinels"
    assert resp["window_days"] == 90
    assert resp["rating_change"] == 0.24  # 1.24 - 1.00
    assert resp["acs_change"] == 60.0  # 260 - 200
    assert resp["summary"] == {
        "points": 3,
        "current_rating": 1.24,
        "peak_rating": 1.31,
        "current_acs": 260.0,
        "peak_acs": 280.0,
    }
    assert "note" not in resp  # healthy trend -> no young-history note


# ---- empty / young history --------------------------------------------------
def test_empty_input_is_valid_empty_response():
    resp = build_player_response("9", 90, [])
    assert resp["player_id"] == "9"
    assert resp["player"] is None
    assert resp["rating_trend"] == []
    assert resp["rating_change"] is None
    assert resp["acs_change"] is None
    assert resp["summary"] == {
        "points": 0, "current_rating": None, "peak_rating": None,
        "current_acs": None, "peak_acs": None,
    }
    assert "note" in resp  # young/empty -> surfaced honestly, not an error


def test_all_garbage_ratings_produce_no_points_but_resolve_identity():
    rows = [psnap("N/A", days=0), psnap("", days=1)]
    resp = build_player_response("9", 90, rows)
    assert resp["rating_trend"] == []
    assert resp["summary"]["points"] == 0
    assert resp["player"] == "TenZ"  # identity still resolves from the rows
    assert "note" in resp


def test_single_point_is_a_valid_trend_with_null_change():
    resp = build_player_response("9", 90, [psnap("1.10", days=0)])
    assert resp["summary"]["points"] == 1
    assert resp["rating_change"] is None  # need >=2 points for a delta
    assert resp["summary"]["current_rating"] == resp["summary"]["peak_rating"] == 1.10


# ---- identity resolution + window cutoff ------------------------------------
def test_latest_player_field_picks_most_recent_nonempty():
    rows = [psnap("1.0", team="Cloud9", days=0), psnap("1.1", team="Sentinels", days=2), psnap("1.2", team="", days=1)]
    assert latest_player_field(rows, "team") == "Sentinels"  # day 2, not the empty day-1
    assert latest_player_field([], "team") is None


def test_cutoff_windows_the_trend_but_identity_resolves_from_all_rows():
    # only the day-10 snapshot is inside the window; the older one still names the player.
    rows = [psnap("0.90", alias="TenZ", days=0), psnap("1.20", alias="TenZ", days=10)]
    resp = build_player_response("9", 5, rows, cutoff=at(8))
    assert [p["rating"] for p in resp["rating_trend"]] == [1.20]  # windowed
    assert resp["summary"]["points"] == 1
    assert resp["player"] == "TenZ"  # resolved from ALL rows, not just the window


def test_cutoff_none_means_no_window():
    rows = [psnap("0.90", days=0), psnap("1.20", days=10)]
    resp = build_player_response("9", 90, rows, cutoff=None)
    assert resp["summary"]["points"] == 2
