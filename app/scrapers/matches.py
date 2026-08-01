"""Match-card list scraper — the a.match-item cards on /matches and /matches/results.

Both pages render the SAME card markup; only which fields are filled differs
(results carry scores, /matches carries an eta + an ml-status of live/upcoming).
So one parser serves both, and the caller decides what the rows mean.

Shape notes worth knowing before you touch this:
  - `scores` stay STRINGS. Upcoming cards render an en-dash placeholder, not a
    number; coercing here would either crash or invent a 0. The API layer and
    the frontend both do null-safe numeric coercion downstream.
  - `time`/`eta`/`date` are vlr's own display strings ("9:00 PM", "in 14h"), not
    timestamps. vlr renders them in the viewer's configured timezone and gives
    no machine-readable datetime on these cards; the frontend derives real dates
    from them (frontend/src/lib/schedule.ts).
  - Layering: this module is pure parsing plus a thin fetch. Nothing here caches
    or persists — that is services/refresh.py's job.
"""
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
    # Label-bleed guard: div.match-item-event NESTS the series div, so its text
    # reads "Group StageChampions Tour 2026". Subtracting the series string is
    # the only split available — the two share one text node otherwise.
    event = clean_spaces(event_full.replace(series, "")) if series else event_full
    return {
        "id": id_from_href(href),
        "url": ("https://www.vlr.gg" + href) if href.startswith("/") else href,
        "time": first_text(card, S.MATCH_TIME) or None,
        "eta": first_text(card, S.MATCH_ETA) or None,
        # lowercased ml-status text: "live" / "upcoming" / "completed".
        # None when the card has no status node at all — that is a valid state,
        # not a parse failure, so downstream must treat it as "unknown".
        "status": status,
        # [:2] is a belt-and-braces truncation. The selectors are deliberately
        # single (no comma-fallbacks) so they match exactly 2 nodes per card —
        # see the MATCH_TEAMS/MATCH_SCORES note in selectors.py for why a union
        # selector here silently returned 4 and only worked by document order.
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
    """Partition /matches cards into live vs everything-else.

    Only "live" is positively identified; the upcoming bucket is the complement,
    so a card with a missing or renamed status still surfaces (as upcoming)
    rather than vanishing from the API. An empty live list is a normal state —
    most hours of the day have no match in progress.
    """
    live = [m for m in matches if m.get("status") == "live"]
    upcoming = [m for m in matches if m.get("status") != "live"]
    return {"live": live, "upcoming": upcoming}


async def fetch_results() -> list[dict[str, Any]]:
    html = await get_client().get_html("/matches/results")
    return parse_match_list(html)


async def fetch_upcoming() -> dict[str, list[dict[str, Any]]]:
    html = await get_client().get_html("/matches")
    return split_live_upcoming(parse_match_list(html))
