from typing import Any

from selectolax.parser import HTMLParser, Node

from app.core.http import get_client
from app.scrapers import selectors as S
from app.scrapers._util import clean_spaces, first_text, id_from_href, text_of


def _parse_card(card: Node) -> dict[str, Any]:
    href = card.attributes.get("href", "") or ""
    teams = [text_of(n) for n in card.css(S.MATCH_TEAMS)]
    scores = [text_of(n) for n in card.css(S.MATCH_SCORES)]
    status_node = card.css_first(S.MATCH_STATUS)
    status = text_of(status_node).lower() or None
    series = clean_spaces(first_text(card, S.MATCH_EVENT_SERIES))
    event_full = clean_spaces(first_text(card, S.MATCH_EVENT))
    # event text includes the series child; strip it so they don't concatenate
    event = clean_spaces(event_full.replace(series, "")) if series else event_full
    return {
        "id": id_from_href(href),
        "url": ("https://www.vlr.gg" + href) if href.startswith("/") else href,
        "time": first_text(card, S.MATCH_TIME) or None,
        "eta": first_text(card, S.MATCH_ETA) or None,
        "status": status,  # "live" / "upcoming" / None when completed
        "teams": [clean_spaces(t) for t in teams][:2],
        "scores": [clean_spaces(s) for s in scores][:2],
        "event": event or None,
        "series": series or None,
    }


def parse_match_list(html: str) -> list[dict[str, Any]]:
    """Pure: HTML -> list of match dicts. Used by both results and upcoming/live pages."""
    tree = HTMLParser(html)
    return [_parse_card(c) for c in tree.css(S.MATCH_CARD)]


def split_live_upcoming(matches: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    live = [m for m in matches if m.get("status") == "live"]
    upcoming = [m for m in matches if m.get("status") != "live"]
    return {"live": live, "upcoming": upcoming}


async def fetch_results() -> list[dict[str, Any]]:
    html = await get_client().get_html("/matches/results")
    return parse_match_list(html)


async def fetch_upcoming() -> dict[str, list[dict[str, Any]]]:
    html = await get_client().get_html("/matches")
    return split_live_upcoming(parse_match_list(html))
