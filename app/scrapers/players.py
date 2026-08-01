"""Player-detail scraper (/player/{id}) — header, current club, agent stats, matches.

The one genuinely tricky thing on this page is CURRENT TEAM, and getting it
wrong is silent: vlr renders several team cards ("Current Teams", "Past Teams")
with identical markup, and national / event-representative sides live under
Past Teams even while they are active. A page-wide css_first for a team link
therefore returns whichever card happens to come first — which for TenZ is his
national "Canada" entry, not a club. So the parser anchors on the "Current
Teams" HEADING and only looks inside the card that follows it
(_current_team_card). See PLAYER_TEAM_HEADING in selectors.py.

A player with no "Current Teams" heading at all is a free agent: the correct
answer is a null team, NOT a fallback to Past Teams. verify.py pins both sides
of this — TenZ as the null control, johnqt as the non-null control — because a
null result alone is indistinguishable from a dead selector.

Pure parse (parse_player) + a thin fetch. No cache, no DB — see services/refresh.py.
"""
from typing import Any

from selectolax.parser import HTMLParser, Node

from app.core.http import get_client
from app.scrapers import selectors as S
from app.scrapers._util import clean_spaces, id_from_href, text_of


def _country_from_flag(flag: Node | None) -> str | None:
    """vlr flags carry the ISO code as a `mod-xx` class, e.g. `flag mod-ca`.

    Byte-identical to _util.country_from_flag — if you change flag handling,
    change both or the two will drift.
    """
    if flag is None:
        return None
    for cls in (flag.attributes.get("class", "") or "").split():
        if cls.startswith("mod-"):
            return cls[len("mod-") :] or None
    return None


def _current_team_card(tree: HTMLParser) -> Node | None:
    """The wf-card immediately after the "Current Teams" <h2>, if any.

    That heading/card boundary is vlr's own split between the player's real
    club roster spot and everything else -- see PLAYER_TEAM_HEADING for why.
    """
    for heading in tree.css(S.PLAYER_TEAM_HEADING):
        if clean_spaces(text_of(heading)) != "Current Teams":
            continue
        # Skip the whitespace text nodes between the heading and its card; the
        # first element sibling IS the card (vlr emits heading-then-card, with
        # no wrapper to select on — hence the sibling walk instead of a selector).
        sibling = heading.next
        while sibling is not None and sibling.tag != "div":
            sibling = sibling.next
        return sibling
    return None


def _parse_team(card: Node | None) -> dict[str, Any]:
    """First team module-item in the "Current Teams" card = the player's club.

    `card` is the module-item itself (already scoped by the caller), not the
    wf-card. None means free agent -> all three keys null; never a fallback.
    """
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
    """Per-agent stats, keyed by header title.

    This is the ONE table in the codebase still keyed by header text rather than
    by a data-col attribute (as /stats and the match scoreboard are) — the player
    page simply doesn't emit data-col. Consequence: a vlr header rename silently
    renames our stat key, and a column reorder is harmless (headers and cells are
    zipped positionally from the same row). Values stay raw strings; nothing here
    coerces, because the keys aren't known ahead of time.
    """
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
    team_card = _current_team_card(tree)
    team_node = team_card.css_first(S.PLAYER_TEAM) if team_card is not None else None
    return {
        "id": player_id,
        "alias": clean_spaces(text_of(tree.css_first(S.PLAYER_ALIAS))) or None,
        "real_name": clean_spaces(text_of(tree.css_first(S.PLAYER_REAL))) or None,
        "country": _country_from_flag(tree.css_first(S.PLAYER_COUNTRY_FLAG)),
        **_parse_team(team_node),
        "agent_stats": _parse_agent_stats(tree),
        "matches": [_parse_match(c) for c in tree.css(S.PLAYER_MATCH_CARD)],
    }


async def fetch_player(player_id: str) -> dict[str, Any]:
    # timespan=all so agent stats reflect the player's full history (good for snapshots)
    html = await get_client().get_html(f"/player/{player_id}/?timespan=all")
    data = parse_player(html)
    # Trust the requested id over the scraped one — same reasoning as fetch_team:
    # a dead PLAYER_SELF_LINK would otherwise persist a null id under a valid key.
    data["id"] = str(player_id)
    return data
