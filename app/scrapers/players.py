from typing import Any

from selectolax.parser import HTMLParser, Node

from app.core.http import get_client
from app.scrapers import selectors as S
from app.scrapers._util import clean_spaces, id_from_href, text_of


def _country_from_flag(flag: Node | None) -> str | None:
    """vlr flags carry the ISO code as a `mod-xx` class, e.g. `flag mod-ca`."""
    if flag is None:
        return None
    for cls in (flag.attributes.get("class", "") or "").split():
        if cls.startswith("mod-"):
            return cls[len("mod-") :] or None
    return None


def _parse_team(card: Node | None) -> dict[str, Any]:
    """First team module-item on the page = the player's current/most recent team."""
    if card is None:
        return {"team": None, "team_id": None, "team_url": None}
    href = card.attributes.get("href", "") or ""
    name = clean_spaces(text_of(card.css_first(S.PLAYER_TEAM_NAME)))
    return {
        "team": name or None,
        "team_id": id_from_href(href),
        "team_url": ("https://www.vlr.gg" + href) if href.startswith("/") else (href or None),
    }


def _parse_agent_stats(tree: HTMLParser) -> list[dict[str, Any]]:
    """Per-agent stats. Header titles drive the keys so new vlr columns just work."""
    table = tree.css_first(S.PLAYER_STATS_TABLE)
    if table is None:
        return []
    headers = [clean_spaces(text_of(th)) for th in table.css(S.PLAYER_STATS_HEADER)]
    rows: list[dict[str, Any]] = []
    for tr in table.css(S.PLAYER_STATS_ROW):
        cells = tr.css(S.PLAYER_STATS_CELL)
        if not cells:
            continue
        img = cells[0].css_first(S.PLAYER_AGENT_IMG)
        agent = (img.attributes.get("alt") if img else None) or None
        # zip the remaining header labels with the remaining cell values
        values = [clean_spaces(text_of(c)) for c in cells[1:]]
        stats = {k: v for k, v in zip(headers[1:], values) if k}
        rows.append({"agent": agent, "stats": stats})
    return rows


def _parse_match(card: Node) -> dict[str, Any]:
    href = card.attributes.get("href", "") or ""
    result_node = card.css_first(S.PLAYER_MATCH_RESULT)
    rcls = (result_node.attributes.get("class", "") if result_node else "") or ""
    result = "win" if "mod-win" in rcls else "loss" if "mod-loss" in rcls else None
    opp = card.css_first(S.PLAYER_MATCH_OPPONENT)
    return {
        "id": id_from_href(href),
        "url": ("https://www.vlr.gg" + href) if href.startswith("/") else href,
        "opponent": clean_spaces(text_of(opp)) or None,
        "result": result,
        "score": (clean_spaces(text_of(result_node)) or None) if result_node else None,
        "event": clean_spaces(text_of(card.css_first(S.PLAYER_MATCH_EVENT))) or None,
    }


def parse_player(html: str) -> dict[str, Any]:
    """Pure: HTML -> player detail dict. Network-free (like the other scrapers)."""
    tree = HTMLParser(html)
    self_link = tree.css_first(S.PLAYER_SELF_LINK)
    player_id = id_from_href(self_link.attributes.get("href", "")) if self_link else None
    return {
        "id": player_id,
        "alias": clean_spaces(text_of(tree.css_first(S.PLAYER_ALIAS))) or None,
        "real_name": clean_spaces(text_of(tree.css_first(S.PLAYER_REAL))) or None,
        "country": _country_from_flag(tree.css_first(S.PLAYER_COUNTRY_FLAG)),
        **_parse_team(tree.css_first(S.PLAYER_TEAM)),
        "agent_stats": _parse_agent_stats(tree),
        "matches": [_parse_match(c) for c in tree.css(S.PLAYER_MATCH_CARD)],
    }


async def fetch_player(player_id: str) -> dict[str, Any]:
    # timespan=all so agent stats reflect the player's full history (good for snapshots)
    html = await get_client().get_html(f"/player/{player_id}/?timespan=all")
    data = parse_player(html)
    # trust the requested id over the scraped one
    data["id"] = str(player_id)
    return data
