from pathlib import Path

import pytest

from app.scrapers.matches import parse_match_list, split_live_upcoming
from app.scrapers.rankings import parse_rankings
from app.scrapers.events import parse_events, parse_news
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
    rows = parse_rankings(load("rankings.html"))
    assert len(rows) == 2
    assert rows[0]["rank"] == "1"
    assert rows[0]["team"] == "Sentinels"
    assert rows[0]["team_id"] == "310"
    assert rows[0]["rating"] == "1024"
    assert rows[1]["team"] == "Paper Rex"
    assert rows[1]["country"] == "Singapore"


# ---------- events ----------
def test_parse_events():
    events = parse_events(load("events.html"))
    assert len(events) == 2
    e = events[0]
    assert e["id"] == "2498"
    assert e["title"] == "Masters London 2026"
    assert e["status"] == "ongoing"
    assert e["prize"] == "$1,000,000"
    assert e["region"] == "gb"


# ---------- news ----------
def test_parse_news():
    news = parse_news(load("news.html"))
    assert len(news) == 2
    assert news[0]["title"].startswith("Star duelist")
    assert news[0]["url"] == "https://www.vlr.gg/news/410000/some-roster-move"
    assert news[1]["title"].startswith("Patch 9.0")


def test_parse_news_skips_titleless():
    html = '<a class="wf-module-item" href="/x"><div class="news-item-desc">no title</div></a>'
    assert parse_news(html) == []
