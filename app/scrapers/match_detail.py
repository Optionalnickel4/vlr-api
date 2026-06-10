"""Match-detail scoreboard scraper (Phase 7).

Parses the per-map scoreboards on a vlr match page. The hard-won rule (from the two
banked live fixtures): every value cell is side-split into three spans — mod-both
(combined), mod-t (attack), mod-ct (defense). We read mod-both as the value and keep
mod-t/mod-ct alongside. Reading raw td.text() instead would CONCATENATE the three
(K=13 -> "1385"), which still coerces to a number and is therefore silently wrong.

Live-state empties are valid: on an in-progress match R/ACS/ADR aren't computed yet,
so those cells are empty -> the value coerces to None (never NaN, never a crash).
"""
from typing import Any

from selectolax.parser import HTMLParser, Node

from app.core.http import get_client
from app.scrapers import selectors as S
from app.scrapers._util import (
    clean_spaces,
    country_from_flag,
    id_from_href,
    parse_numeric,
    parse_percent,
    text_of,
)


def _stat_key(header: str, cls: str) -> str | None:
    """Column key from the header, disambiguating the two identical '+/–' headers
    via the cell's diff class (kd-diff vs fk-diff)."""
    if S.MATCH_SB_CLS_KD_DIFF in cls:
        return "KD_+/-"
    if S.MATCH_SB_CLS_FK_DIFF in cls:
        return "FK_+/-"
    return header or None


def _coerce(key: str, both: str | None) -> float | None:
    """KAST and HS% carry a percent sign -> parse_percent; the rest -> parse_numeric.
    Both return None (never NaN) for empty live-partial cells."""
    if key in S.MATCH_SB_PCT_KEYS or (both is not None and both.endswith("%")):
        return parse_percent(both)
    return parse_numeric(both)


def _read_stat(td: Node) -> tuple[str | None, str | None, str | None]:
    """(both, t, ct) clean strings from the side-split spans. Defaults to mod-both."""
    both = td.css_first(S.MATCH_SB_VAL_BOTH)
    t = td.css_first(S.MATCH_SB_VAL_T)
    ct = td.css_first(S.MATCH_SB_VAL_CT)
    return (
        clean_spaces(text_of(both)) or None,
        clean_spaces(text_of(t)) or None,
        clean_spaces(text_of(ct)) or None,
    )


def _parse_identity(tr: Node) -> dict[str, Any]:
    cell = tr.css_first(S.MATCH_SB_PLAYER)
    if cell is None:
        return {"player": None, "team": None, "player_id": None, "country": None}
    link = cell.css_first(S.MATCH_SB_PLAYER_LINK)
    href = (link.attributes.get("href", "") if link else "") or ""
    return {
        "player": clean_spaces(text_of(cell.css_first(S.MATCH_SB_PLAYER_ALIAS))) or None,
        "team": clean_spaces(text_of(cell.css_first(S.MATCH_SB_PLAYER_TEAM))) or None,
        "player_id": id_from_href(href),
        "country": country_from_flag(cell.css_first(S.MATCH_SB_PLAYER_FLAG)),
    }


def _parse_row(tr: Node, headers: list[str]) -> dict[str, Any]:
    agent_img = tr.css_first(S.MATCH_SB_AGENT)
    agent = (agent_img.attributes.get("alt") if agent_img else None) or None
    stats: dict[str, Any] = {}
    for i, td in enumerate(tr.css(S.MATCH_SB_CELL)):
        cls = td.attributes.get("class", "") or ""
        if "mod-stat" not in cls:  # skip the player + agent cells
            continue
        key = _stat_key(headers[i] if i < len(headers) else "", cls)
        if not key:
            continue
        both, t, ct = _read_stat(td)
        # value reads mod-both, NEVER the concatenated raw cell text
        stats[key] = {"value": _coerce(key, both), "both": both, "t": t, "ct": ct}
    return {**_parse_identity(tr), "agent": agent, "stats": stats}


def _parse_scoreboard(table: Node) -> dict[str, Any]:
    headers = [clean_spaces(text_of(th)) for th in table.css(S.MATCH_SB_HEADER)]
    players = [
        _parse_row(tr, headers)
        for tr in table.css(S.MATCH_SB_ROW)
        if tr.css(S.MATCH_SB_CELL)
    ]
    return {"players": players}


def parse_match_detail(html: str) -> dict[str, Any]:
    """Pure: HTML -> match detail dict. Network-free (like the other scrapers).

    `scoreboards` is the list of per-map/per-team scoreboards in document order
    (8 on a finished bo3: per-map × per-team + the all-maps aggregate)."""
    tree = HTMLParser(html)
    tables = tree.css(S.MATCH_SB_TABLE)
    return {"scoreboards": [_parse_scoreboard(t) for t in tables]}


async def fetch_match_detail(match_id: str) -> dict[str, Any]:
    html = await get_client().get_html(f"/{match_id}")
    return parse_match_detail(html)
