"""Parse HLTV /results into the canonical match-row dict.

The parser is pure: HTML string in, list of dicts out. The async fetchers
(fetch_results, fetch_upcoming) live in this module too so the pattern
mirrors app/scrapers/matches.py, but the pure functions are what the
unit tests exercise.

Output shape (locked by tests/cs2/test_matches.py):

    {
        "id":          int,        # integer segment of /matches/{id}/...
        "url":         str,        # full /matches/{id}/{slug}
        "match_slug":  str,        # trailing segment after the ID
        "team_a":      str,        # first .team-cell .team
        "team_b":      str,        # second .team-cell .team
        "score_a":     int,        # first <span> in .result-score (lost side)
        "score_b":     int,        # second <span> in .result-score (won side)
        "winner":      "team_a" | "team_b",
        "event":       str,        # td.event .event-name text
        "format":      "bo1" | "bo3" | "bo5",   # from div.map.map-text
        "stars":       int,        # count of <i class="star"> inside div.stars
        "unix_ms":     int | None, # data-zonedgrouping-entry-unix on the row
    }

The .team-won class on one of the two .team cells drives the `winner` field.
CS2 has no draws, so the loser's score is always <= the winner's; we don't
re-check this in the parser (the test suite does, and a divergence would
indicate a markup change).
"""
from typing import Any, Optional

from selectolax.parser import HTMLParser, Node

from app.cs2 import selectors as S


# Local helpers — mirrors app/scrapers/_util.py without sharing it. CS2 has
# different markup quirks (no flag-class country codes, no percent signs in
# stats) so a shared helper module would be premature.

def _text(node: Optional[Node], default: str = "") -> str:
    return node.text(strip=True) if node is not None else default


def _clean_spaces(s: str) -> str:
    import re
    return re.sub(r"\s+", " ", s).strip()


def _coerce_int(s: str) -> Optional[int]:
    s = s.strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _id_and_slug_from_href(href: str) -> tuple[Optional[int], str, str]:
    """HLTV hrefs look like /matches/2395001/spirit-vs-falcons-iem-cologne-major-2026.

    Returns (id, url, slug). id is None if the href doesn't match the shape.
    The URL is the path-only form (caller can prefix the base URL if needed).
    """
    href = href or ""
    if not href.startswith("/matches/"):
        return None, href, ""
    parts = href.strip("/").split("/")
    # ['matches', '<id>', '<slug...>']
    if len(parts) < 2 or not parts[1].isdigit():
        return None, href, ""
    match_id = int(parts[1])
    slug = "/".join(parts[2:]) if len(parts) > 2 else ""
    return match_id, href, slug


def _parse_row(row: Node) -> Optional[dict[str, Any]]:
    """Parse a single <div class="result-con"> row. Returns None on a malformed row."""
    anchor = row.css_first(S.RESULTS_MATCH_LINK)
    if anchor is None:
        return None
    href = anchor.attributes.get("href", "") or ""
    match_id, url, slug = _id_and_slug_from_href(href)
    if match_id is None:
        return None

    # Team cells: two td.team-cell elements in document order. We grab both
    # .team nodes; each .team sits inside a .line-align.team1/.team2 wrapper.
    team_nodes = row.css(f"{S.RESULTS_TEAM_CELL} {S.RESULTS_TEAM_NAME}")
    if len(team_nodes) < 2:
        # A row missing one or both team cells is malformed; skip rather than
        # emit a partial dict that downstream code can't render.
        return None
    team_a = _text(team_nodes[0])
    team_b = _text(team_nodes[1])
    if not team_a or not team_b:
        return None

    # Winner: which .team carries the .team-won class? We check the class
    # attribute string rather than relying on text content.
    def _is_winner(node: Node) -> bool:
        cls = (node.attributes.get("class", "") or "").split()
        return S.RESULTS_WINNER_CLASS in cls

    if _is_winner(team_nodes[0]):
        winner = "team_a"
    elif _is_winner(team_nodes[1]):
        winner = "team_b"
    else:
        # Neither team carries the .team-won class — should not happen for a
        # completed match. Default to team_a so the row still renders.
        winner = "team_a"

    # Scores: two <span>s inside .result-score, in document order.
    score_cell = row.css_first(S.RESULTS_SCORE_CELL)
    if score_cell is None:
        return None
    spans = score_cell.css(S.RESULTS_SCORE_SPAN)
    if len(spans) < 2:
        return None
    score_a = _coerce_int(_text(spans[0]))
    score_b = _coerce_int(_text(spans[1]))
    if score_a is None or score_b is None:
        # A row with non-numeric scores is unparseable — skip.
        return None

    event = _clean_spaces(_text(row.css_first(S.RESULTS_EVENT_NAME)))
    fmt = _clean_spaces(_text(row.css_first(S.RESULTS_FORMAT)))
    if fmt and fmt not in ("bo1", "bo3", "bo5"):
        # Some rows have unusual formats ("bo7" in showmatches?); surface
        # whatever HLTV gave us but flag in tests.
        fmt = fmt

    # Stars: count <i class="star"> inside .stars. If .stars is absent, 0.
    stars_container = row.css_first(S.RESULTS_STARS_CONTAINER)
    stars = 0
    if stars_container is not None:
        stars = len(stars_container.css(S.RESULTS_STAR))

    # Timestamp: data-zonedgrouping-entry-unix on the row itself. Some pages
    # had rows missing this attribute; we surface None rather than guess.
    unix_ms_raw = (row.attributes.get("data-zonedgrouping-entry-unix", "") or "").strip()
    unix_ms = _coerce_int(unix_ms_raw)

    return {
        "id": match_id,
        "url": url,
        "match_slug": slug,
        "team_a": team_a,
        "team_b": team_b,
        "score_a": score_a,
        "score_b": score_b,
        "winner": winner,
        "event": event,
        "format": fmt,
        "stars": stars,
        "unix_ms": unix_ms,
    }


def parse_results(html: str) -> list[dict[str, Any]]:
    """Pure: HLTV /results HTML -> list of result-row dicts.

    Robust against empty / non-HLTV input (returns []). Malformed individual
    rows are skipped (the parser returns a partial list rather than raising).
    """
    if not html:
        return []
    tree = HTMLParser(html)
    out: list[dict[str, Any]] = []
    for row in tree.css(S.RESULTS_ROW):
        parsed = _parse_row(row)
        if parsed is not None:
            out.append(parsed)
    return out


async def fetch_results() -> list[dict[str, Any]]:
    """Fetch /results from HLTV and return the parsed rows."""
    from app.cs2.http import get_client
    client = get_client()
    resp = await client.get("/results")
    return parse_results(resp.text)