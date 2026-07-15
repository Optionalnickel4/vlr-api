from pathlib import Path

import pytest

from app.scrapers.matches import parse_match_list, split_live_upcoming
from app.scrapers.rankings import parse_rankings
from app.scrapers.events import parse_events, parse_news
from app.scrapers.players import parse_player
from app.scrapers._util import id_from_href, clean_spaces

FIX = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIX / name).read_text()


# ---------- util ----------
def test_id_from_href_variants():
    assert id_from_href("/310/sentinels") == "310"
    assert id_from_href("/event/2498/masters-london-2026") == "2498"
    assert id_from_href("/player/4164/aspas") == "4164"
    assert id_from_href("/about") is None


def test_clean_spaces():
    assert clean_spaces("  a   b\n c ") == "a b c"


# ---------- matches / results ----------
def test_parse_results_count_and_fields():
    matches = parse_match_list(load("results.html"))
    assert len(matches) == 2
    m = matches[0]
    assert m["id"] == "378289"
    assert m["url"] == "https://www.vlr.gg/378289/team-a-vs-team-b"
    assert m["teams"] == ["Team Alpha", "Team Beta"]
    assert m["scores"] == ["13", "7"]
    assert "Masters London 2026" in m["event"]
    assert m["series"] == "Playoffs–Upper Final"


def test_parse_results_second_card():
    m = parse_match_list(load("results.html"))[1]
    assert m["teams"] == ["Gamma GG", "Delta Esports"]
    assert m["scores"] == ["2", "0"]


# ---------- live / upcoming ----------
def test_split_live_upcoming():
    matches = parse_match_list(load("upcoming.html"))
    split = split_live_upcoming(matches)
    assert len(split["live"]) == 1
    assert split["live"][0]["teams"] == ["Sentinels", "Paper Rex"]
    assert len(split["upcoming"]) == 1
    assert split["upcoming"][0]["teams"] == ["Fnatic", "G2 Esports"]
    assert split["upcoming"][0]["eta"] == "in 14h"


def test_live_card_has_live_status():
    matches = parse_match_list(load("upcoming.html"))
    live = [m for m in matches if m["status"] == "live"]
    assert len(live) == 1
    assert live[0]["id"] == "400001"


# ---------- rankings ----------
def test_parse_rankings():
    # rankings.html is the WORLD view (real trim) — the class-less team div
    # nests the country div, so the name must come out clean, country-free.
    rows = parse_rankings(load("rankings.html"))
    assert len(rows) == 2
    assert rows[0]["rank"] == "1"
    assert rows[0]["team"] == "Enterprise Esports"
    assert rows[0]["team_id"] == "876"
    assert rows[0]["rating"] == "2000"
    assert rows[0]["country"] == "Czech Republic"
    assert rows[1]["team"] == "Team Vitality"
    assert rows[1]["country"] == "Europe"


# ---------- rankings: W/L record (Item 1 — regional layout) ----------
# vlr split rankings into a WORLD view (no record) and REGIONAL pages (record
# present in div.rank-item-record as "wins–losses"). These assert the record is
# extracted from the regional layout and splits into clean, coercible wins/losses.
def _coerces_clean(s):
    # mirrors the frontend parseNumeric contract: a finite number or null, never NaN
    if s is None:
        return True
    try:
        int(s)
        return True
    except (TypeError, ValueError):
        return False


def test_parse_rankings_record_wl_regional():
    rows = parse_rankings(load("rankings_regional.html"))
    assert len(rows) == 2
    g2 = rows[0]
    # record is non-null and is the CURRENT (first) node "74–35", not all-time "140–64"
    assert g2["record"] == "74–35"
    assert g2["wins"] == "74" and g2["losses"] == "35"
    # the per-match mod-win/mod-loss dots ("1","0","1") did NOT bleed into the record
    assert "1" not in (g2["wins"], g2["losses"]) or g2["wins"] == "74"
    # every team's W/L is non-null and coerces cleanly (parseNumeric: value not NaN)
    for r in rows:
        assert r["record"] is not None
        assert r["wins"] is not None and r["losses"] is not None
        assert _coerces_clean(r["wins"]) and _coerces_clean(r["losses"])
        assert int(r["wins"]) >= 0 and int(r["losses"]) >= 0


def test_parse_rankings_world_view_has_no_record():
    # the world/all view dropped the W/L column entirely — record/wins/losses are
    # legitimately null there (a valid state, not a parse failure), and still coerce.
    # NB: must be wrapped in <table> — selectolax/lexbor drops a bare <tr>, exactly
    # as the live world page nests its rows in a real rankings table.
    html = (
        '<table><tbody><tr class="wf-card mod-hover"><td class="rank-item-rank">'
        '<a href="/team/2/sentinels">1</a></td>'
        '<td class="rank-item-team"><a href="/team/2/sentinels"><div>Sentinels'
        '<div class="rank-item-team-country">United States</div></div></a></td>'
        '<td class="rank-item-rating mod-world"><a>1024</a></td></tr></tbody></table>'
    )
    r = parse_rankings(html)[0]
    assert r["rating"] == "1024"
    assert r["record"] is None and r["wins"] is None and r["losses"] is None
    assert _coerces_clean(r["wins"]) and _coerces_clean(r["losses"])


# ---------- events ----------
def test_parse_events():
    events = parse_events(load("events.html"))
    assert len(events) == 2
    e = events[0]
    assert e["id"] == "2765"
    assert e["title"] == "Valorant Masters London 2026"
    assert e["status"] == "ongoing"
    # prize/dates must have the trailing "Prize Pool"/"Dates" labels stripped
    assert e["prize"] == "$1,000,000"
    assert e["dates"] == "Jun 5—21"
    assert e["region"] == "gb"


def test_parse_events_strips_desc_labels():
    # second card carries a "TBD" prize — the label-strip must not eat the value
    e = parse_events(load("events.html"))[1]
    assert e["id"] == "2780"
    assert e["prize"] == "TBD"
    assert e["dates"] == "May 18—Jul 12"


# ---------- news ----------
def test_parse_news():
    news = parse_news(load("news.html"))
    assert len(news) == 2
    assert news[0]["title"].startswith("nAts to miss")
    assert news[0]["url"] == "https://www.vlr.gg/715457/nats-to-miss-first-game-of-stage-2-against-eternal-fire"
    assert news[1]["title"].startswith("GIANTX finalizes")


def test_parse_news_skips_titleless():
    html = '<a class="wf-module-item" href="/x"><div class="news-item-desc">no title</div></a>'
    assert parse_news(html) == []


# ---------- player detail (TenZ, id 9) ----------
# These assert STRUCTURE + INVARIANTS only — never volatile values (team, stats,
# match list all change over time), so the suite stays green as TenZ's data moves.
def test_parse_player_identity():
    p = parse_player(load("player_tenz.html"))
    assert p["id"] and p["id"].isdigit()
    assert isinstance(p["alias"], str) and p["alias"].strip()
    assert isinstance(p["real_name"], str) and p["real_name"].strip()
    # country is a short code parsed off the flag class
    assert isinstance(p["country"], str) and p["country"].strip()


def test_parse_player_team_none_when_no_current_teams_section():
    # TenZ currently has no "Current Teams" card at all -- only "Past Teams",
    # whose first entry is his national team (Canada). Regression guard for the
    # bug where css_first() on the whole page grabbed that national entry as
    # if it were his club: team must resolve to null, never fall back to it.
    p = parse_player(load("player_tenz.html"))
    assert p["team"] is None
    assert p["team_id"] is None
    assert p["team_url"] is None


def test_parse_player_team_resolves_to_club_not_national():
    # johnqt (id 1265) has a "Current Teams" card (Sentinels) AND a "Past Teams"
    # card whose first/most-recent entry is his national team (Morocco, still
    # active with no end date). Team must resolve to the club, not the national
    # team, even though the national entry is more recent.
    p = parse_player(load("player_johnqt.html"))
    assert p["team"] == "Sentinels"
    assert p["team_id"] == "2"
    assert p["team_url"] == "https://www.vlr.gg/team/2/sentinels"


def test_parse_player_team_club_only_no_national():
    # A player whose "Past Teams" card has no national-team entry at all --
    # confirms club resolution doesn't depend on a national entry being present.
    p = parse_player(load("player_victor.html"))
    assert isinstance(p["team"], str) and p["team"].strip()
    assert p["team_id"] and p["team_id"].isdigit()


def test_parse_player_team_null_for_teamless_player():
    # No "Current Teams" or "Past Teams" section at all (free agent / minimal
    # page) -- must not crash, team fields all resolve to null.
    html = "<html><body><h1 id='wf-title'>Nobody</h1></body></html>"
    p = parse_player(html)
    assert p["team"] is None
    assert p["team_id"] is None
    assert p["team_url"] is None


def test_parse_player_agent_stats_structure():
    p = parse_player(load("player_tenz.html"))
    stats = p["agent_stats"]
    assert isinstance(stats, list) and len(stats) > 0
    for row in stats:
        assert set(row.keys()) == {"agent", "stats"}
        assert isinstance(row["agent"], str) and row["agent"].strip()
        assert isinstance(row["stats"], dict) and len(row["stats"]) > 0
        # every column value is a string (we don't pin the numbers)
        assert all(isinstance(v, str) for v in row["stats"].values())
    # the per-agent columns are consistent across rows
    assert len({frozenset(r["stats"].keys()) for r in stats}) == 1


def test_parse_player_match_history_structure():
    p = parse_player(load("player_tenz.html"))
    matches = p["matches"]
    assert isinstance(matches, list) and len(matches) > 0
    for m in matches:
        assert m["id"] and m["id"].isdigit()
        assert m["url"].startswith("https://www.vlr.gg/")
        assert isinstance(m["opponent"], str) and m["opponent"].strip()
        assert m["result"] in {"win", "loss", None}
        assert isinstance(m["event"], str) and m["event"].strip()
