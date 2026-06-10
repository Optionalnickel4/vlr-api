"""Match-detail scraper tests (Phase 7) — the full match shape.

Parse the two banked live fixtures and assert structure + invariants + the few
known-value checks that prove the scoreboard side-split spans are read correctly:
  - match_detail_live.html   = early/partial (R/ACS/ADR not yet computed -> empty)
  - match_detail_live_2.html = filled (all map-1 stats populated)
Both are valid live states. No network is touched.
"""
from pathlib import Path

from selectolax.parser import HTMLParser

from app.scrapers._util import parse_numeric, parse_percent
from app.scrapers.match_detail import parse_match

FIX = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIX / name).read_text()


FILLED = "match_detail_live_2.html"   # Global Esports vs FULL SENSE
PARTIAL = "match_detail_live.html"    # Dragon Ranger vs Xi Lai


# ---------- coercion helpers (null, never NaN) ----------
def test_parse_numeric_null_not_nan():
    assert parse_numeric("13") == 13.0
    assert parse_numeric("1.04") == 1.04
    for bad in ["", "  ", None, "nan", "inf", "-", "N/A"]:
        assert parse_numeric(bad) is None  # never NaN, never a crash


def test_parse_percent_strips_then_parses():
    assert parse_percent("64%") == 64.0
    assert parse_percent("") is None
    assert parse_percent(None) is None
    assert parse_percent("100") == 100.0


# ---------- header ----------
def test_header_event_teams_score_veto():
    d = parse_match(load(FILLED))
    assert d["event"] == "Valorant Masters London 2026"
    assert d["series"] and "Swiss Stage" in d["series"]
    assert d["format"] == "BO3"
    names = [t["name"] for t in d["teams"]]
    assert names == ["Global Esports", "FULL SENSE"]
    ids = [t["id"] for t in d["teams"]]
    assert all(i and i.isdigit() for i in ids)
    # both team series scores coerce to ints (live: 0 / 1), never NaN
    for t in d["teams"]:
        assert t["score"] is None or isinstance(t["score"], (int, float))
    # the veto/picks strip is present and mentions a ban/pick
    assert d["veto"] and ("ban" in d["veto"] and "pick" in d["veto"])


def test_header_winner_flag_only_when_final():
    # the FILLED fixture is a LIVE match -> nobody is marked won yet
    d = parse_match(load(FILLED))
    assert d["status"] == "live"
    assert all(t["won"] is False for t in d["teams"])


# ---------- maps ----------
def test_maps_names_pick_decider_and_scores():
    d = parse_match(load(FILLED))
    assert len(d["maps"]) == 3
    by_name = {m["name"]: m for m in d["maps"]}
    # two picked maps + exactly one decider
    assert sum(1 for m in d["maps"] if m["decider"]) == 1
    assert sum(1 for m in d["maps"] if m["picked"]) == 2
    split = by_name["Split"]
    assert split["picked"] is True and split["decider"] is False
    assert split["scores"] == [9.0, 13.0]  # [team1, team2]
    # every map has both teams with five players each
    for m in d["maps"]:
        assert [len(t["players"]) for t in m["teams"]] == [5, 5]


def test_all_maps_aggregate_present():
    d = parse_match(load(FILLED))
    assert d["all_maps"] is not None
    assert [len(t["players"]) for t in d["all_maps"]["teams"]] == [5, 5]


# ---------- rounds timeline ----------
def test_round_timeline_structure():
    d = parse_match(load(FILLED))
    split = next(m for m in d["maps"] if m["name"] == "Split")
    rounds = split["rounds"]
    assert len(rounds) == 24
    r1 = rounds[0]
    assert r1["round"] == 1
    assert r1["winner"] in (1, 2)
    assert r1["side"] in ("t", "ct")
    assert isinstance(r1["outcome"], str) and r1["outcome"]  # elim/boom/defuse/time
    assert r1["score"] == "1-0"  # cumulative team1-team2 after round 1
    # the un-played decider (live match) has rounds with no winner yet — valid
    pearl = next(m for m in d["maps"] if m["name"] == "Pearl")
    assert all(rr["winner"] is None for rr in pearl["rounds"])


# ---------- scoreboard: THE concatenation proof ----------
def test_value_reads_mod_both_not_concatenation():
    """K=13 in span.mod-both, but the raw cell text concatenates both/t/ct into
    "1385" — a number that coerces fine and is silently WRONG. Prove we read the
    combined span, not the raw cell."""
    html = load(FILLED)
    tree = HTMLParser(html)
    kcell = tree.css("table.wf-table-inset.mod-overview")[0].css("tbody tr")[0].css_first(
        "td.mod-vlr-kills"
    )
    assert kcell.text(strip=True) == "1385"  # the dangerous concatenation

    p = parse_match(html)["maps"][0]["teams"][0]["players"][0]
    assert p["player"] == "Kr1stal" and p["agent"] == "fade"
    k = p["stats"]["K"]
    assert k["both"] == "13" and k["value"] == 13.0 and k["value"] != 1385.0
    assert k["t"] == "8" and k["ct"] == "5"  # side-splits preserved, not discarded


def test_percent_columns_parsed():
    stats = parse_match(load(FILLED))["maps"][0]["teams"][0]["players"][0]["stats"]
    assert stats["KAST"]["both"] == "64%" and stats["KAST"]["value"] == 64.0
    assert stats["HS%"]["both"] == "21%" and stats["HS%"]["value"] == 21.0


def test_partial_empty_stats_are_null():
    stats = parse_match(load(PARTIAL))["maps"][0]["teams"][0]["players"][0]["stats"]
    for empty_key in ("R", "ACS", "ADR"):
        assert stats[empty_key]["both"] is None
        assert stats[empty_key]["value"] is None  # not NaN, not 0
    for live_key in ("K", "D", "A"):
        assert isinstance(stats[live_key]["value"], float)


def test_kd_and_fk_diff_keys_distinct():
    stats = parse_match(load(FILLED))["maps"][0]["teams"][0]["players"][0]["stats"]
    assert "KD_+/-" in stats and "FK_+/-" in stats


# ---------- cross-cutting invariants ----------
def test_all_player_values_finite_or_none():
    for name in (FILLED, PARTIAL):
        d = parse_match(load(name))
        groups = [t for m in d["maps"] for t in m["teams"]] + d["all_maps"]["teams"]
        for g in groups:
            for p in g["players"]:
                assert isinstance(p["player"], str) and p["player"].strip()
                for cell in p["stats"].values():
                    v = cell["value"]
                    assert v is None or (isinstance(v, float) and v == v)  # NaN guard
