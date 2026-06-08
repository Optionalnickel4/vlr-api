from typing import Any

from selectolax.parser import HTMLParser, Node

from app.core.http import get_client
from app.scrapers import selectors as S
from app.scrapers._util import clean_spaces, first_text, id_from_href, text_of


def _parse_row(row: Node) -> dict[str, Any]:
    link = row.css_first("a")
    href = link.attributes.get("href", "") if link else ""
    country = clean_spaces(first_text(row, S.RANK_COUNTRY))
    team = clean_spaces(first_text(row, S.RANK_TEAM_NAME))
    # live markup nests the country inside the team-name node; strip the suffix
    if country and team.endswith(country):
        team = team[: -len(country)].strip()
    return {
        "rank": first_text(row, S.RANK_NUM) or None,
        "team": team or None,
        "team_id": id_from_href(href) if href else None,
        "country": country or None,
        "rating": first_text(row, S.RANK_RATING) or None,
        "record": clean_spaces(first_text(row, S.RANK_RECORD)) or None,
        "earnings": clean_spaces(first_text(row, S.RANK_EARNINGS)) or None,
    }


def parse_rankings(html: str) -> list[dict[str, Any]]:
    tree = HTMLParser(html)
    return [_parse_row(r) for r in tree.css(S.RANK_ROW)]


async def fetch_rankings(region: str = "all") -> list[dict[str, Any]]:
    path = "/rankings" if region == "all" else f"/rankings/{region}"
    html = await get_client().get_html(path)
    return parse_rankings(html)
