"""Two small list scrapers that share a file: /events and /news.

They live together because both are flat card lists with no cross-referencing
and neither is big enough to warrant its own module. Their only real hazards:

  - EVENTS: the prize/date values NEST their own label div, so raw text reads
    "$1,000,000Prize Pool" (see _desc_value). Region comes from a flag class,
    not text.
  - NEWS: vlr's news rows are class-less and inline-styled, so the selectors
    match on style attributes — unusually brittle by necessity, and the reason
    parse_news drops title-less items rather than emitting half-empty rows.
    See the NEWS_* block in selectors.py.

Values stay raw strings (prize as "$1,000,000", dates as "Jul 15—Aug 3");
nothing here parses money or dates, and downstream treats them as display text.
"""
from typing import Any

from selectolax.parser import HTMLParser, Node

from app.core.http import get_client
from app.scrapers import selectors as S
from app.scrapers._util import clean_spaces, first_text, id_from_href, text_of


def _desc_value(card: Node, selector: str) -> str:
    """Text of a desc-item (prize/dates) with its trailing label stripped.

    Live markup nests a <div class="event-item-desc-item-label"> ("Prize Pool",
    "Dates") inside the value node, so the raw text reads "$1,000,000Prize Pool".
    """
    node = card.css_first(selector)
    if node is None:
        return ""
    full = clean_spaces(text_of(node))
    label = clean_spaces(text_of(node.css_first(S.EVENT_DESC_LABEL)))
    if label and full.endswith(label):
        full = full[: -len(label)].strip()
    return full


def _parse_event(card: Node) -> dict[str, Any]:
    href = card.attributes.get("href", "") or ""
    # Region is encoded ONLY in the flag icon's class ("flag mod-eu"); the card
    # carries no region text. mod-un ("unknown") is a real vlr value for
    # international events and passes through as-is.
    region_node = card.css_first(S.EVENT_REGION)
    region = region_node.attributes.get("class", "") if region_node else ""
    return {
        "id": id_from_href(href),
        "url": ("https://www.vlr.gg" + href) if href.startswith("/") else href,
        "title": clean_spaces(first_text(card, S.EVENT_TITLE)) or None,
        "status": clean_spaces(first_text(card, S.EVENT_STATUS)) or None,
        "prize": _desc_value(card, S.EVENT_PRIZE) or None,
        "dates": _desc_value(card, S.EVENT_DATES) or None,
        "region": region.replace("flag mod-", "").strip() or None,
    }


def parse_events(html: str) -> list[dict[str, Any]]:
    tree = HTMLParser(html)
    return [_parse_event(c) for c in tree.css(S.EVENT_CARD)]


async def fetch_events() -> list[dict[str, Any]]:
    html = await get_client().get_html("/events")
    return parse_events(html)


def _parse_news(item: Node) -> dict[str, Any]:
    href = item.attributes.get("href", "") or ""
    return {
        "url": ("https://www.vlr.gg" + href) if href.startswith("/") else href,
        "title": clean_spaces(first_text(item, S.NEWS_TITLE)) or None,
        "description": clean_spaces(first_text(item, S.NEWS_DESC)) or None,
        "meta": clean_spaces(first_text(item, S.NEWS_DATE)) or None,
    }


def parse_news(html: str) -> list[dict[str, Any]]:
    """Parse /news rows, dropping any without a title.

    a.wf-module-item is a GENERIC vlr row class — the news page reuses it for
    non-article rows (nav/promo items) that carry no styled title div. The title
    filter is what keeps those out; without it the API emits url-only rows the
    frontend renders as blank cards.
    """
    tree = HTMLParser(html)
    items = [_parse_news(i) for i in tree.css(S.NEWS_ITEM)]
    return [i for i in items if i["title"]]


async def fetch_news() -> list[dict[str, Any]]:
    html = await get_client().get_html("/news")
    return parse_news(html)
