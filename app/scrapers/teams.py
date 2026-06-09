from typing import Any

from selectolax.parser import HTMLParser, Node

from app.core.http import get_client
from app.scrapers import selectors as S
from app.scrapers._util import clean_spaces, country_from_flag, id_from_href, text_of

VLR = "https://www.vlr.gg"


def _abs(href: str) -> str | None:
    return (VLR + href) if href.startswith("/") else (href or None)


def _closest_card(node: Node | None) -> Node | None:
    """Walk up to the enclosing wf-card so roster traversal stays scoped to the
    roster module (other cards reuse the wf-module-label class for rank/record)."""
    n = node
    while n is not None:
        if "wf-card" in (n.attributes.get("class", "") or "").split():
            return n
        n = n.parent
    return None


def _parse_member(item: Node, section: str | None) -> dict[str, Any]:
    link = item.css_first(S.TEAM_ROSTER_LINK)
    href = (link.attributes.get("href", "") if link else "") or ""
    # the alias node nests a flag <i> and an optional captain-star <i>; both are
    # text-free, so text(strip=True) yields just the alias with no label-bleed.
    alias = clean_spaces(text_of(item.css_first(S.TEAM_ROSTER_ALIAS)))
    return {
        "alias": alias or None,
        "real_name": clean_spaces(text_of(item.css_first(S.TEAM_ROSTER_REAL))) or None,
        "role": clean_spaces(text_of(item.css_first(S.TEAM_ROSTER_ROLE))) or None,
        "country": country_from_flag(item.css_first(S.TEAM_ROSTER_FLAG)),
        "player_id": id_from_href(href),
        "url": _abs(href),
        "is_captain": item.css_first(S.TEAM_ROSTER_CAPTAIN) is not None,
        "is_staff": section == "staff",
    }


def _parse_roster(tree: HTMLParser) -> list[dict[str, Any]]:
    first = tree.css_first(S.TEAM_ROSTER_ITEM)
    if first is None:
        return []
    card = _closest_card(first)
    if card is None:  # defensive: no enclosing card -> flat parse, section unknown
        return [_parse_member(it, None) for it in tree.css(S.TEAM_ROSTER_ITEM)]
    members: list[dict[str, Any]] = []
    section: str | None = None
    # document-order walk: a wf-module-label switches the active section, every
    # roster item after it belongs to that section until the next label.
    for node in card.traverse(include_text=False):
        cls = set((node.attributes.get("class", "") or "").split())
        if "wf-module-label" in cls:
            section = clean_spaces(node.text(strip=True)).lower() or section
        elif "team-roster-item" in cls:
            members.append(_parse_member(node, section))
    return members


def _is_game_row(card: Node) -> bool:
    return S.TEAM_MATCH_GAME_ROW_CLASS in (card.attributes.get("class", "") or "")


def _parse_match(card: Node) -> dict[str, Any]:
    href = card.attributes.get("href", "") or ""
    result_node = card.css_first(S.TEAM_MATCH_RESULT)
    rcls = (result_node.attributes.get("class", "") if result_node else "") or ""
    result = "win" if "mod-win" in rcls else "loss" if "mod-loss" in rcls else None
    opp = card.css_first(S.TEAM_MATCH_OPPONENT)
    opp_link = card.css_first(S.TEAM_MATCH_OPPONENT_LINK)
    opp_href = (opp_link.attributes.get("href", "") if opp_link else "") or ""
    return {
        "id": id_from_href(href),
        "url": _abs(href),
        "opponent": clean_spaces(text_of(opp)) or None,
        "opponent_id": id_from_href(opp_href),
        "result": result,
        "score": (clean_spaces(text_of(result_node)) or None) if result_node else None,
        "event": clean_spaces(text_of(card.css_first(S.TEAM_MATCH_EVENT))) or None,
        "date": clean_spaces(text_of(card.css_first(S.TEAM_MATCH_DATE))) or None,
    }


def _parse_matches(tree: HTMLParser) -> tuple[list[dict], list[dict]]:
    """Split the team's match cards: a played card carries a win/loss result class;
    anything without one is a scheduled (upcoming) match. Upcoming may be empty out
    of season — that is a valid state, not a parse failure."""
    results: list[dict[str, Any]] = []
    upcoming: list[dict[str, Any]] = []
    for card in tree.css(S.TEAM_MATCH_CARD):
        if _is_game_row(card):
            continue
        m = _parse_match(card)
        (results if m["result"] in {"win", "loss"} else upcoming).append(m)
    return results, upcoming


def parse_team(html: str) -> dict[str, Any]:
    """Pure: HTML -> team detail dict. Network-free (like the other scrapers)."""
    tree = HTMLParser(html)
    self_link = tree.css_first(S.TEAM_SELF_LINK)
    team_id = id_from_href(self_link.attributes.get("href", "")) if self_link else None
    logo = tree.css_first(S.TEAM_LOGO)
    logo_src = (logo.attributes.get("src") if logo else None) or None
    if logo_src and logo_src.startswith("//"):
        logo_src = "https:" + logo_src
    results, upcoming = _parse_matches(tree)
    return {
        "id": team_id,
        "name": clean_spaces(text_of(tree.css_first(S.TEAM_NAME))) or None,
        "tag": clean_spaces(text_of(tree.css_first(S.TEAM_TAG))) or None,
        "country": clean_spaces(text_of(tree.css_first(S.TEAM_COUNTRY))) or None,
        "country_code": country_from_flag(tree.css_first(S.TEAM_COUNTRY_FLAG)),
        "logo": logo_src,
        "roster": _parse_roster(tree),
        "results": results,
        "upcoming": upcoming,
    }


async def fetch_team(team_id: str) -> dict[str, Any]:
    html = await get_client().get_html(f"/team/{team_id}")
    data = parse_team(html)
    # trust the requested id over the scraped one
    data["id"] = str(team_id)
    return data
