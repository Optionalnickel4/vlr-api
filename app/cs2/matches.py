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


# --- /matches (upcoming + live) parser ---------------------------------------
#
# Output shape for parse_upcoming (locked by tests/cs2/test_upcoming.py):
#
#     {
#         "id":          int,        # data-match-id on the wrapper
#         "url":         str,        # href of a.match-info
#         "match_slug":  str,        # trailing slug after the ID
#         "team_a":      str,        # first div.match-teamname
#         "team_b":      str,        # second div.match-teamname
#         "team_a_id":   str,        # team1 attribute on the wrapper
#         "team_b_id":   str,        # team2 attribute on the wrapper
#         "format":      "bo1" | "bo3" | "bo5",   # div.match-meta text
#         "stars":       int,        # data-stars on the wrapper (0-5)
#         "stage":       str,        # div.match-stage text ("Semifinal", etc.)
#         "region":      str,        # data-region on the wrapper ("Europe", etc.)
#         "event_type":  str,        # data-eventtype ("ranked" | "lan" | "online")
#         "event_id":    int | None, # data-event-id (cross-ref to events.py)
#         "unix_ms":     int | None, # data-unix on div.match-time
#         "live":        bool,       # `live` attribute == "true" on the wrapper
#     }


def _id_and_slug_from_match_href(href: str) -> tuple[Optional[int], str]:
    """HLTV match hrefs: /matches/2395347/chicken-coop-vs-overtake-sector-...

    Returns (id, slug). id is None if the href doesn't match the shape.
    Used by both parse_upcoming (href on a.match-info) and parse_match_detail.
    """
    href = href or ""
    if not href.startswith("/matches/"):
        return None, ""
    parts = href.strip("/").split("/")
    if len(parts) < 2 or not parts[1].isdigit():
        return None, ""
    return int(parts[1]), "/".join(parts[2:])


def _parse_upcoming_match(wrapper: Node) -> Optional[dict[str, Any]]:
    """Parse a single <div class="match-wrapper"> block."""
    match_id_raw = (wrapper.attributes.get("data-match-id", "") or "").strip()
    if not match_id_raw.isdigit():
        return None
    match_id = int(match_id_raw)

    # Time/format anchor: a.match-info. The href here is the canonical /matches/{id}/{slug}.
    info_anchor = wrapper.css_first(S.UPCOMING_TIME_ANCHOR)
    if info_anchor is None:
        return None
    href = info_anchor.attributes.get("href", "") or ""
    parsed_id, slug = _id_and_slug_from_match_href(href)
    if parsed_id is None:
        return None
    # The data-match-id is the authoritative source; trust it if the href disagrees.
    if parsed_id != match_id:
        slug = slug  # keep the slug from href even if id parsing fell back

    # Time: data-unix on div.match-time. Some matches (esp. live ones) lack it.
    time_node = info_anchor.css_first(S.UPCOMING_TIME)
    unix_ms_raw = ""
    if time_node is not None:
        unix_ms_raw = (time_node.attributes.get("data-unix", "") or "").strip()
    unix_ms = _coerce_int(unix_ms_raw)

    # Format: text content of div.match-meta.
    fmt = _clean_spaces(_text(info_anchor.css_first(S.UPCOMING_FORMAT)))

    # Teams: a.match-teams with two div.match-teamname children in document order.
    teams_anchor = wrapper.css_first(S.UPCOMING_TEAMS_ANCHOR)
    if teams_anchor is None:
        return None
    team_names = teams_anchor.css(S.UPCOMING_TEAM_NAME)
    if len(team_names) < 2:
        return None
    team_a = _text(team_names[0])
    team_b = _text(team_names[1])
    if not team_a or not team_b:
        return None

    # Stars: data-stars attribute (already an int on the wrapper).
    stars_raw = (wrapper.attributes.get("data-stars", "") or "").strip()
    stars = _coerce_int(stars_raw) or 0

    # Region + event_type + event_id from wrapper attributes.
    region = (wrapper.attributes.get("data-region", "") or "").strip()
    event_type = (wrapper.attributes.get("data-eventtype", "") or "").strip()
    event_id_raw = (wrapper.attributes.get("data-event-id", "") or "").strip()
    event_id = _coerce_int(event_id_raw)

    # Stage: optional div.match-stage (semifinal, group stage, etc.).
    stage = _clean_spaces(_text(wrapper.css_first(S.UPCOMING_STAGE)))

    # Team IDs from the wrapper attributes (used by the frontend to link to
    # the team profile route).
    team_a_id = (wrapper.attributes.get("team1", "") or "").strip()
    team_b_id = (wrapper.attributes.get("team2", "") or "").strip()

    # Live marker: the `live` attribute on the wrapper. The only reliable
    # signal in the markup. Captures to False when no matches are live (the
    # captured fixture has 0 live="true" wrappers; live matches get rendered
    # by the scorebot JS, not the /matches page directly).
    live = (wrapper.attributes.get("live", "") or "").lower() == "true"

    return {
        "id": match_id,
        "url": href,
        "match_slug": slug,
        "team_a": team_a,
        "team_b": team_b,
        "team_a_id": team_a_id,
        "team_b_id": team_b_id,
        "format": fmt,
        "stars": stars,
        "stage": stage,
        "region": region,
        "event_type": event_type,
        "event_id": event_id,
        "unix_ms": unix_ms,
        "live": live,
    }


def parse_upcoming(html: str) -> list[dict[str, Any]]:
    """Pure: HLTV /matches HTML -> list of upcoming-match dicts.

    Robust against empty / non-HLTV input (returns []). Malformed individual
    wrappers are skipped rather than raising — the parser returns a partial
    list so a single markup glitch can't break the whole endpoint.

    NB: HLTV's /matches page contains BOTH live and upcoming matches (the
    live ones carry live="true" on the wrapper). Callers that want them
    separated should use split_live_upcoming(). The /cs2/matches/live route
    returns [] in v1 because HLTV renders live matches via the scorebot
    websocket (data-scoreboturls on /live), not via static HTML on /matches.
    See tests/cs2/test_upcoming.py::test_parse_upcoming_live_is_false_in_fixture.
    """
    if not html:
        return []
    tree = HTMLParser(html)
    out: list[dict[str, Any]] = []
    for wrapper in tree.css(S.UPCOMING_MATCH):
        parsed = _parse_upcoming_match(wrapper)
        if parsed is not None:
            out.append(parsed)
    return out


def split_live_upcoming(matches: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Route matches into live[] vs upcoming[] based on the `live` bool field.

    Parallel to app.scrapers.matches.split_live_upcoming but for the CS2
    schema. Kept as a separate function (not merged into parse_upcoming)
    so a caller that wants the full list unfiltered can have it.
    """
    live = [m for m in matches if m.get("live") is True]
    upcoming = [m for m in matches if not m.get("live")]
    return {"live": live, "upcoming": upcoming}


async def fetch_upcoming() -> dict[str, list[dict[str, Any]]]:
    """Fetch /matches from HLTV and return {live, upcoming} split.

    The /cs2/matches/live route reads `result["live"]`; if HLTV is rendering
    live matches via scorebot (no static markup), this list is empty by design
    and the frontend should surface "no live matches right now" rather than
    a 200-with-data surprise.
    """
    from app.cs2.http import get_client
    client = get_client()
    resp = await client.get("/matches")
    return split_live_upcoming(parse_upcoming(resp.text))