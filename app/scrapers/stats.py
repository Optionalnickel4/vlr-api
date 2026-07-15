"""VLR /stats leaderboard scraper (Phase 12) — HLTV-style player rankings.

Pure: HTML -> list of leaderboard-row dicts. Network-free like the other scrapers
(fetch_stats is the only async boundary). VLR exposes its OWN R2.0 rating at 100%
fill on this page — we surface it as the headline and DO NOT compute a composite.

COERCION DISCIPLINE (the label-bleed / silently-wrong-numbers bug class):
  - every stat value prefers span.mod-both over raw cell text — the 2026 table
    is plain-text (no side-split spans), but the guard stays so a re-added
    side-split can never concatenate into a wrong number (K=13 -> "1385");
  - % columns (KAST/HS%/CL%) go through parse_percent ('78%' -> 78.0);
  - the CL column is a FRACTION ('3/15' = won/played) -> two ints via parse_fraction,
    never a single number;
  - K:D is a ratio string ('1.62') -> float, fine via parse_numeric;
  - all numeric coercion is null-on-empty/malformed, never NaN, never a crash.
Each value <td> carries a data-col attribute (vlr's 2026 scheme, same as the
match scoreboard); STATS_COL_KEYS drives the column->key mapping, so column
reordering, header-label renames, and brand-new vlr columns all fall through
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

    out: list[dict[str, Any]] = []
    for tr in table.css(S.STATS_ROW):
        cells = tr.css(S.STATS_CELL)
        if not cells:
            continue
        row = _empty_row()
        for cell in cells:
            classes = cell.attributes.get("class", "") or ""
            if S.STATS_PLAYER_CELL_CLASS in classes:
                row["player"], row["player_id"], row["team"] = _parse_player_cell(cell)
                continue

            col = cell.attributes.get(S.STATS_COL_ATTR) or ""
            if col == S.STATS_COL_AGENTS:
                # junk like '(+1)' / '' — captured trivially, ignored for rating.
                row["agents"] = _cell_value(cell) or None
                continue
            if col == S.STATS_COL_CL:
                row["cl_won"], row["cl_played"] = parse_fraction(_cell_value(cell))
                continue

            key = S.STATS_COL_KEYS.get(col)
            if key is None:
                continue  # unmapped/new data-col — fall through harmlessly
            raw = _cell_value(cell)
            row[key] = parse_percent(raw) if key in S.STATS_PCT_KEYS else parse_numeric(raw)

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
