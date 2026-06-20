"""Tests for app.cs2.matches.parse_upcoming + split_live_upcoming.

Uses tests/cs2/fixtures/matches.html (642 KB, 136 match-wrappers, captured
live 2026-06-20). All assertions against the saved fixture — no network.
"""
from pathlib import Path

import pytest

from app.cs2.matches import parse_upcoming, split_live_upcoming


FIX = Path(__file__).parent / "fixtures" / "matches.html"


@pytest.fixture(scope="module")
def html() -> str:
    assert FIX.exists(), (
        f"fixture missing: {FIX}. Run `uv run python -m app.cs2.capture`."
    )
    return FIX.read_text(encoding="utf-8")


def test_parse_upcoming_returns_non_empty_list(html):
    matches = parse_upcoming(html)
    assert isinstance(matches, list)
    assert len(matches) >= 50, f"got {len(matches)} matches, expected >=50"


def test_parse_upcoming_shape_is_stable(html):
    """Every parsed match must have the documented keys with the right types."""
    matches = parse_upcoming(html)
    required_str = {
        "url", "team_a", "team_b", "format", "stage",
        "region", "event_type", "match_slug",
    }
    for i, m in enumerate(matches[:10]):
        missing = required_str - set(m.keys())
        assert not missing, f"row {i} missing keys: {missing}"
        assert isinstance(m["id"], int), f"row {i} id not int"
        assert isinstance(m["stars"], int), f"row {i} stars not int"
        assert isinstance(m["event_id"], int | type(None)), (
            f"row {i} event_id not int or None"
        )
        assert isinstance(m["team_a_id"], str), f"row {i} team_a_id not str"
        assert isinstance(m["team_b_id"], str), f"row {i} team_b_id not str"
        assert isinstance(m["unix_ms"], int | type(None)), (
            f"row {i} unix_ms not int or None"
        )
        assert isinstance(m["live"], bool), f"row {i} live not bool"
        assert 0 <= m["stars"] <= 5, f"row {i} stars out of range"


def test_parse_upcoming_extracts_real_match_ids(html):
    """IDs come from data-match-id on the wrapper. They're 7-digit integers."""
    matches = parse_upcoming(html)
    for m in matches[:5]:
        assert m["id"] > 1_000_000, f"unrealistic ID: {m['id']}"
        assert f"/matches/{m['id']}/" in m["url"], f"url missing ID: {m['url']}"


def test_parse_upcoming_live_is_false_in_fixture(html):
    """The captured fixture has 0 live matches (HLTV renders live matches in a
    different DOM via the scorebot websocket). All parsed matches must report
    live=False. When HLTV DOES render a live match on this page, the same
    attribute-based detection should flip to True (covered by live network)."""
    matches = parse_upcoming(html)
    live_matches = [m for m in matches if m["live"]]
    assert live_matches == [], (
        f"expected 0 live matches in the static fixture, got {len(live_matches)}"
    )


def test_parse_upcoming_teams_are_nonempty(html):
    matches = parse_upcoming(html)
    for m in matches[:20]:
        assert m["team_a"].strip(), f"empty team_a in {m}"
        assert m["team_b"].strip(), f"empty team_b in {m}"
        # Team ids are non-empty strings
        assert m["team_a_id"], f"empty team_a_id in {m}"
        assert m["team_b_id"], f"empty team_b_id in {m}"


def test_parse_upcoming_format_is_bo1_bo3_or_bo5(html):
    matches = parse_upcoming(html)
    formats = {m["format"] for m in matches if m["format"]}
    assert formats, "no matches had a format"
    assert formats <= {"bo1", "bo3", "bo5"}, f"unexpected formats: {formats}"


def test_parse_upcoming_unix_ms_is_present(html):
    """At least 80% of matches should have a unix_ms (from div.match-time
    data-unix). The remaining ones may have been matches whose time element
    was inside an outer zone-wrapper."""
    matches = parse_upcoming(html)
    with_unix = sum(1 for m in matches if m["unix_ms"] is not None)
    assert with_unix >= len(matches) * 0.8, (
        f"only {with_unix}/{len(matches)} had unix_ms — selector may have drifted"
    )


def test_split_live_upcoming_separates_by_flag(html):
    """split_live_upcoming routes each match into live[] or upcoming[] based
    on the live bool. In our static fixture, all are upcoming."""
    matches = parse_upcoming(html)
    split = split_live_upcoming(matches)
    assert "live" in split and "upcoming" in split
    assert split["live"] == [], "static fixture has no live matches"
    assert len(split["upcoming"]) == len(matches)


def test_split_live_upcoming_with_fake_live():
    """Unit test for the splitter — feed it a synthetic list with one live match."""
    synthetic = [
        {"id": 1, "live": False},
        {"id": 2, "live": True},
        {"id": 3, "live": False},
    ]
    split = split_live_upcoming(synthetic)
    assert [m["id"] for m in split["live"]] == [2]
    assert [m["id"] for m in split["upcoming"]] == [1, 3]


def test_parse_upcoming_handles_empty_html():
    assert parse_upcoming("") == []


def test_parse_upcoming_is_deterministic(html):
    a = parse_upcoming(html)
    b = parse_upcoming(html)
    assert a == b