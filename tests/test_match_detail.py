"""Match-detail scoreboard scraper tests (Phase 7, Item 2).

Parse the two banked live fixtures and assert structure + invariants + the few
known-value checks that prove the side-split spans are read correctly:
  - match_detail_live.html   = early/partial (R/ACS/ADR not yet computed -> empty)
  - match_detail_live_2.html = filled (all stats populated)
Both are valid live states. No network is touched.
"""
from pathlib import Path

from selectolax.parser import HTMLParser

from app.scrapers import selectors as S
from app.scrapers._util import parse_numeric, parse_percent
from app.scrapers.match_detail import parse_match_detail

FIX = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIX / name).read_text()


FILLED = "match_detail_live_2.html"
PARTIAL = "match_detail_live.html"


# ---------- coercion helpers (null, never NaN) ----------
def test_parse_numeric_null_not_nan():
    assert parse_numeric("13") == 13.0
    assert parse_numeric("1.04") == 1.04
    for bad in ["", "  ", None, "nan", "inf", "-", "N/A"]:
        out = parse_numeric(bad)
        assert out is None  # never NaN, never a crash


def test_parse_percent_strips_then_parses():
    assert parse_percent("64%") == 64.0
    assert parse_percent("21%") == 21.0
    assert parse_percent("") is None
    assert parse_percent(None) is None
    # safe on non-% text too
    assert parse_percent("100") == 100.0


# ---------- structure: 8 scoreboards, 5 players each ----------
def test_scoreboard_tables_and_rows():
    for name in (FILLED, PARTIAL):
        d = parse_match_detail(load(name))
        assert len(d["scoreboards"]) == 8  # per-map × per-team + all-maps aggregate
        for sb in d["scoreboards"]:
            assert len(sb["players"]) == 5  # five per team


# ---------- identity + agent ----------
def test_player_identity_and_agent():
    p = parse_match_detail(load(FILLED))["scoreboards"][0]["players"][0]
    assert p["player"] == "Kr1stal"          # td.mod-player div.text-of, not "Kr1stalGE"
    assert p["team"] == "GE"                  # div.ge-text-light (team tag)
    assert p["player_id"] == "5796"           # from /player/5796/kr1stal
    assert p["country"] == "ru"               # i.flag mod-ru
    assert p["agent"] == "fade"               # td.mod-agents img[alt]


# ---------- THE concatenation proof ----------
def test_value_reads_mod_both_not_concatenation():
    """K=13 in span.mod-both, but the raw cell text concatenates both/t/ct into
    "1385" — a number that coerces fine and is silently WRONG. Prove we read the
    combined span, not the raw cell."""
    html = load(FILLED)
    # what the raw cell text WOULD be (the trap): "1385" from 13 / 8 / 5
    tree = HTMLParser(html)
    kcell = tree.css("table.wf-table-inset.mod-overview")[0].css("tbody tr")[0].css_first(
        "td.mod-vlr-kills"
    )
    assert kcell.text(strip=True) == "1385"  # the dangerous concatenation

    k = parse_match_detail(html)["scoreboards"][0]["players"][0]["stats"]["K"]
    assert k["both"] == "13"
    assert k["value"] == 13.0                # combined stat, NOT 1385.0
    assert k["value"] != 1385.0
    # mod-t / mod-ct are real attack/defense data and are preserved, not discarded
    assert k["t"] == "8" and k["ct"] == "5"


# ---------- KAST / HS% via parse_percent ----------
def test_percent_columns_parsed():
    stats = parse_match_detail(load(FILLED))["scoreboards"][0]["players"][0]["stats"]
    assert stats["KAST"]["both"] == "64%" and stats["KAST"]["value"] == 64.0
    assert stats["HS%"]["both"] == "21%" and stats["HS%"]["value"] == 21.0
    # side-splits keep their % text too
    assert stats["KAST"]["t"] == "75%" and stats["KAST"]["ct"] == "50%"


# ---------- live-partial: empty R/ACS/ADR -> null (never NaN, never crash) ----------
def test_partial_empty_stats_are_null():
    stats = parse_match_detail(load(PARTIAL))["scoreboards"][0]["players"][0]["stats"]
    for empty_key in ("R", "ACS", "ADR"):
        assert stats[empty_key]["both"] is None
        assert stats[empty_key]["value"] is None  # not NaN, not 0
    # but K/D/A ARE computed on the partial page and coerce cleanly
    for live_key in ("K", "D", "A"):
        v = stats[live_key]["value"]
        assert v is not None and isinstance(v, float)


# ---------- both '+/–' columns disambiguated ----------
def test_kd_and_fk_diff_keys_distinct():
    stats = parse_match_detail(load(FILLED))["scoreboards"][0]["players"][0]["stats"]
    # the two identical '+/–' headers must not collide
    assert "KD_+/-" in stats and "FK_+/-" in stats
    assert stats["KD_+/-"]["both"] == "-1"
    assert stats["FK_+/-"]["both"] == "+1"


# ---------- invariants across every row of every scoreboard ----------
def test_all_rows_structurally_sound():
    for name in (FILLED, PARTIAL):
        for sb in parse_match_detail(load(name))["scoreboards"]:
            for p in sb["players"]:
                assert isinstance(p["player"], str) and p["player"].strip()
                # agent is pinned per-map (see test above); on the all-maps
                # aggregate a player has no single agent -> None is valid here
                assert p["agent"] is None or isinstance(p["agent"], str)
                assert isinstance(p["stats"], dict) and p["stats"]
                for cell in p["stats"].values():
                    # value is a finite float or None — never NaN
                    assert cell["value"] is None or isinstance(cell["value"], float)
                    if cell["value"] is not None:
                        assert cell["value"] == cell["value"]  # NaN != NaN guard
