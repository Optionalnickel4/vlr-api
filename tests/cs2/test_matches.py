"""Tests for app.cs2.matches.parse_results.

Uses a saved HLTV HTML fixture (tests/cs2/fixtures/results.html) captured by
`python -m app.cs2.capture --results-only`. No network in tests.

The parser must extract, per result row:
  - id (int)         from /matches/{id}/... in the inner <a> href
  - url (str)        full /matches/{id}/{slug}
  - team_a (str)     first .team-cell .team
  - team_b (str)     second .team-cell .team
  - score_a (int)    first <span> in .result-score (lost side)
  - score_b (int)    second <span> in .result-score (won side)
  - winner (str)     whichever team has .team-won class ("team_a" | "team_b")
  - event (str)      td.event .event-name text
  - format (str)     "bo1" | "bo3" | "bo5" from div.map.map-text
  - stars (int)      count of <i class="star"> inside div.stars (0 if absent)
  - unix_ms (int)    data-zonedgrouping-entry-unix, or None
  - match_slug (str) the slug segment of the href after the ID
"""
from pathlib import Path

import pytest

from app.cs2.matches import parse_results


FIX = Path(__file__).parent / "fixtures" / "results.html"


@pytest.fixture(scope="module")
def html() -> str:
    assert FIX.exists(), (
        f"fixture missing: {FIX}. Run `uv run python -m app.cs2.capture --results-only` "
        f"to capture live HTML from HLTV."
    )
    return FIX.read_text(encoding="utf-8")


def test_parse_results_returns_a_non_empty_list(html):
    results = parse_results(html)
    assert isinstance(results, list)
    assert len(results) >= 50, (
        f"expected >=50 results on a fresh /results page, got {len(results)} "
        f"— selectors may have drifted"
    )


def test_parse_results_shape_is_stable(html):
    """Every result must have all the documented keys, with the right types."""
    results = parse_results(html)
    required_str = {"url", "team_a", "team_b", "winner", "event", "format", "match_slug"}
    for i, r in enumerate(results[:10]):
        missing = required_str - set(r.keys())
        assert not missing, f"row {i} missing keys: {missing}"
        assert isinstance(r["id"], int), f"row {i} id not int: {r['id']!r}"
        assert isinstance(r["score_a"], int), f"row {i} score_a not int"
        assert isinstance(r["score_b"], int), f"row {i} score_b not int"
        assert isinstance(r["stars"], int), f"row {i} stars not int"
        assert 0 <= r["score_a"] <= 16, f"row {i} score_a out of range: {r['score_a']}"
        assert 0 <= r["score_b"] <= 16, f"row {i} score_b out of range: {r['score_b']}"
        assert 0 <= r["stars"] <= 5, f"row {i} stars out of range: {r['stars']}"
        # unix_ms may be None (a handful of blocks were missing the attr in the live capture)
        assert r["unix_ms"] is None or isinstance(r["unix_ms"], int)


def test_parse_results_extracts_real_match_ids(html):
    """The ID is the integer segment of /matches/{id}/ in the href."""
    results = parse_results(html)
    for r in results[:5]:
        assert r["id"] > 1_000_000, f"unrealistic ID: {r['id']}"
        assert f"/matches/{r['id']}/" in r["url"], f"url missing ID: {r['url']}"


def test_parse_results_winner_is_team_a_or_team_b(html):
    """The .team-won class MUST be on exactly one of the two team cells."""
    results = parse_results(html)
    for r in results[:20]:
        assert r["winner"] in ("team_a", "team_b"), f"bad winner: {r['winner']!r} for {r}"
        # The winner's score must be >= the loser's (no draws in CS2).
        if r["winner"] == "team_a":
            assert r["score_a"] >= r["score_b"], (
                f"team_a won but score_a={r['score_a']} < score_b={r['score_b']}: {r}"
            )
        else:
            assert r["score_b"] >= r["score_a"], (
                f"team_b won but score_b={r['score_b']} < score_a={r['score_a']}: {r}"
            )


def test_parse_results_event_is_nonempty(html):
    results = parse_results(html)
    non_empty = [r for r in results if r["event"].strip()]
    assert len(non_empty) >= len(results) * 0.9, (
        f"only {len(non_empty)}/{len(results)} had a non-empty event name"
    )


def test_parse_results_format_is_bo1_bo3_or_bo5(html):
    results = parse_results(html)
    formats = {r["format"] for r in results if r["format"]}
    assert formats, "no rows had a format string"
    assert formats <= {"bo1", "bo3", "bo5"}, f"unexpected formats: {formats}"


def test_parse_results_handles_empty_html():
    """Empty input must return an empty list, not raise."""
    assert parse_results("") == []
    assert parse_results("<html><body>no results here</body></html>") == []


def test_parse_results_is_deterministic(html):
    """Running the parser twice on the same HTML yields the same list."""
    a = parse_results(html)
    b = parse_results(html)
    assert a == b


def test_parse_results_id_matches_url_segment(html):
    """url must be /matches/{id}/{match_slug} — the parser doesn't strip the slug."""
    results = parse_results(html)
    for r in results[:10]:
        # match_slug should be the trailing segment after the ID
        assert r["match_slug"], f"empty slug for {r}"
        assert r["url"].endswith(r["match_slug"]), f"slug not at end of url: {r}"