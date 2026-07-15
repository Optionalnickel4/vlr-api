"""VLR /stats leaderboard scraper (Phase 12) — HLTV-style player rankings.

Pure: HTML -> list of leaderboard-row dicts. Network-free like the other scrapers
(fetch_stats is the only async boundary). VLR exposes its OWN R2.0 rating at 100%
fill on this page — we surface it as the headline and DO NOT compute a composite.

COERCION DISCIPLINE (the label-bleed / silently-wrong-numbers bug class):
  - every stat value reads span.mod-both, NEVER raw td.text() (which concatenates
    the side-split spans into a wrong number);
  - % columns (KAST/HS%/CL%) go through parse_percent ('78%' -> 78.0);
  - the CL column is a FRACTION ('3/15' = won/played) -> two ints via parse_fraction,
    never a single number;
  - K:D is a ratio string ('1.62') -> float, fine via parse_numeric;
  - all numeric coercion is null-on-empty/malformed, never NaN, never a crash.
The header titles drive the column->key mapping, so a new vlr column falls through
harmlessly rather than shifting every value one cell over.
"""
from typing import Any, Optional
from urllib.parse import urlencode

from selectolax.parser import HTMLParser, Node

from app.core.http import get_client
from app.scrapers import selectors as S
from app.scrapers._util import (
    clean_spaces,
    coerce_int,
    id_from_href,
    parse_fraction,
    parse_numeric,
    parse_percent,
    text_of,
)

# vlr only serves regional leaderboards for explicit regions; a value-less region
# (World) 500s, so callers pass na/eu explicitly (guarded at the route/service).
_NUM = "num"
_PCT = "pct"

# header label (verbatim as vlr prints it) -> (output key, coercion kind).
# Player / Agents / CL are handled specially below, not through this map.
_COLUMN_MAP: dict[str, tuple[str, str]] = {
    "Rnd": ("rnd", _NUM),
    "R": ("r2", _NUM),
    "ACS": ("acs", _NUM),
    "K:D": ("kd", _NUM),
    "KAST": ("kast", _PCT),
    "ADR": ("adr", _NUM),
    "KPR": ("kpr", _NUM),
    "APR": ("apr", _NUM),
    "FKPR": ("fkpr", _NUM),
    "FDPR": ("fdpr", _NUM),
    "HS%": ("hs", _PCT),
    "CL%": ("clutch_pct", _PCT),
    "KMAX": ("kmax", _NUM),
    "K": ("k", _NUM),
    "D": ("d", _NUM),
    "A": ("a", _NUM),
    "FK": ("fk", _NUM),
    "FD": ("fd", _NUM),
}

# every emitted row carries the full key set (null when absent) so the API/UI
# shape is stable regardless of which columns a given window happens to fill.
_ROW_KEYS = (
    "player", "player_id", "team", "agents", "r2", "acs", "kd", "kast", "adr",
    "kpr", "apr", "fkpr", "fdpr", "hs", "clutch_pct", "cl_won", "cl_played",
    "kmax", "rnd", "k", "d", "a", "fk", "fd",
)


def _empty_row() -> dict[str, Any]:
    return {k: None for k in _ROW_KEYS}


def _cell_value(cell: Node) -> str:
    """The combined stat value: prefer span.mod-both, fall back to the cell text
    for cells that aren't side-split. NEVER read raw td.text() on a split cell —
    it concatenates mod-both/mod-t/mod-ct into a silently-wrong number."""
    both = cell.css_first(S.STATS_VAL_BOTH)
    return clean_spaces(text_of(both)) if both is not None else clean_spaces(text_of(cell))


def _parse_player_cell(cell: Node) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """(alias, player_id, team) from the identity cell.

    Each field is read from its OWN selector — never from raw cell text (which would
    concatenate alias+team into "TenZSEN"). The three nodes are siblings under the
    link, so there is no way one bleeds into another.

    alias  — div.text-of                  e.g. "TenZ"
    id     — /player/{id} href segment    e.g. "9"
    team   — div.st-pl-country            e.g. "SEN" (null when absent)
    """
    link = cell.css_first(S.STATS_PLAYER_LINK)
    href = (link.attributes.get("href", "") if link else "") or ""
    alias = clean_spaces(text_of(cell.css_first(S.STATS_PLAYER_ALIAS)))
    if not alias and link is not None:
        alias = clean_spaces(text_of(link))
    team_node = cell.css_first(S.STATS_PLAYER_TEAM)
    team = clean_spaces(text_of(team_node)) or None
    return (alias or None), id_from_href(href), team


def parse_stats(html: str) -> list[dict[str, Any]]:
    """Pure: a /stats page -> list of leaderboard rows (coerced, null-not-NaN)."""
    tree = HTMLParser(html)
    table = tree.css_first(S.STATS_TABLE)
    if table is None:
        return []
    headers = [clean_spaces(text_of(th)) for th in table.css(S.STATS_HEADER)]

    out: list[dict[str, Any]] = []
    for tr in table.css(S.STATS_ROW):
        cells = tr.css(S.STATS_CELL)
        if not cells:
            continue
        row = _empty_row()
        for i, cell in enumerate(cells):
            label = headers[i] if i < len(headers) else ""
            classes = cell.attributes.get("class", "") or ""

            if label == "Player" or S.STATS_PLAYER_CELL_CLASS in classes:
                row["player"], row["player_id"], row["team"] = _parse_player_cell(cell)
                continue
            if label == "Agents":
                # junk like '(+1)' / '' — captured trivially, ignored for rating.
                row["agents"] = _cell_value(cell) or None
                continue
            if label == "CL":
                row["cl_won"], row["cl_played"] = parse_fraction(_cell_value(cell))
                continue

            mapped = _COLUMN_MAP.get(label)
            if mapped is None:
                continue  # unknown/new column — fall through harmlessly
            key, kind = mapped
            raw = _cell_value(cell)
            row[key] = parse_percent(raw) if kind == _PCT else parse_numeric(raw)

        # Rnd is a count — keep it an int for a clean min_rnd filter / display.
        if row["rnd"] is not None:
            row["rnd"] = coerce_int(row["rnd"])
        out.append(row)
    return out


def _build_path(region: str, timespan: str) -> str:
    return f"/stats/?{urlencode({'region': region, 'timespan': timespan})}"


async def fetch_stats(region: str = "na", timespan: str = "all") -> list[dict[str, Any]]:
    """Fetch + parse one region×timespan leaderboard. region must be a real vlr
    region (na/eu) — a value-less region 500s upstream (guarded by the caller)."""
    html = await get_client().get_html(_build_path(region, timespan))
    return parse_stats(html)
