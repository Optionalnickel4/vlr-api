"""Shared node-reading and coercion helpers for the scrapers.

The single rule that shapes every function here: SCRAPED DATA IS ALWAYS PARTIAL,
so a missing or malformed value must become None — never a crash, never NaN, and
never a plausible-looking wrong number. vlr pages legitimately serve empty stat
cells (a live match has no rating yet), absent nodes (world rankings have no W/L
column), and placeholder dashes, all of which reach these functions.

NaN is called out explicitly because it is the dangerous case: it survives float()
and arithmetic, serializes as invalid JSON, and only surfaces as a broken chart
far downstream. The frontend's parseNumeric mirrors this contract exactly, so a
value coerces identically on both sides of the wire.

Every helper takes `object` rather than `str` on purpose — callers pass whatever
came out of the DOM without pre-checking its type.
"""
import math
import re
from typing import Optional

from selectolax.parser import Node


def text_of(node: Optional[Node], default: str = "") -> str:
    """Stripped text of a node that may not exist — the css_first() companion."""
    return node.text(strip=True) if node is not None else default


def parse_numeric(raw: object) -> Optional[float]:
    """Coerce a raw stat string to a float, or None. NEVER NaN.

    '' / None / non-numeric -> None; 'nan'/'inf' are rejected (non-finite -> None).
    Mirrors the frontend parseNumeric contract so coercion is identical on both
    sides of the wire. Used by the match-detail scoreboard (R/ACS/ADR are empty
    on a live-partial page and must become null, not crash, not NaN)."""
    if raw is None:
        return None
    s = str(raw).strip()
    if s == "":
        return None
    try:
        n = float(s)
    except ValueError:
        return None
    return n if math.isfinite(n) else None


def parse_percent(raw: object) -> Optional[float]:
    """Strip a trailing '%' then parse_numeric. '64%' -> 64.0, '' -> None, never NaN.

    The match-detail KAST and HS% columns carry a percent sign; this is where that
    is consumed. Safe on non-% text too (nothing to strip)."""
    if raw is None:
        return None
    s = str(raw).strip()
    if s.endswith("%"):
        s = s[:-1].strip()
    return parse_numeric(s)


def coerce_int(raw: object) -> Optional[int]:
    """parse_numeric then truncate to int, or None. Never NaN, never crash.
    '15' -> 15, '15.0' -> 15, '' / '-' / None -> None."""
    n = parse_numeric(raw)
    return int(n) if n is not None else None


def parse_fraction(raw: object) -> tuple[Optional[int], Optional[int]]:
    """Split a 'won/played' fraction string into two ints. The vlr /stats CL
    column is a FRACTION ('3/15' = clutches won / played, '19/104' valid) — NOT a
    single number, so it must never go through parse_numeric (which would yield
    None on the slash). Empty / no-slash / malformed -> (None, None), no crash."""
    if raw is None:
        return None, None
    s = str(raw).strip()
    if "/" not in s:
        return None, None
    won, _, played = s.partition("/")
    return coerce_int(won), coerce_int(played)


def first_text(parent: Node, selector: str, default: str = "") -> str:
    """Text of the first match, or `default` when nothing matches.

    Beware on side-split cells: this reads the whole subtree, so on the match
    scoreboard it would concatenate mod-both/mod-t/mod-ct. Those cells go
    through match_detail._read_stat instead.
    """
    return text_of(parent.css_first(selector), default)


def id_from_href(href: str) -> Optional[str]:
    """vlr hrefs look like /310/sentinels, /event/2498/..., /player/4164/aspas.
    Return the first all-numeric path segment.

    Scanning for the first numeric segment (rather than indexing a fixed
    position) is what lets one helper serve every entity: the id sits at index 0
    for matches but index 1 for players/teams/events. It does mean a slug that
    is purely digits would win if it came first — no live vlr slug is.
    """
    for seg in href.strip("/").split("/"):
        if seg.isdigit():
            return seg
    return None


def clean_spaces(s: str) -> str:
    """Collapse runs of whitespace to single spaces and trim.

    vlr's HTML is pretty-printed, so text that renders as one line arrives with
    embedded newlines and tabs. Applied to every scraped string so cached and
    persisted values are stable — without it the same value hashes/compares
    differently depending on vlr's indentation.
    """
    return re.sub(r"\s+", " ", s).strip()


def country_from_flag(flag: Optional[Node]) -> Optional[str]:
    """vlr flags carry the ISO code as a `mod-xx` class, e.g. `flag mod-ca`."""
    if flag is None:
        return None
    for cls in (flag.attributes.get("class", "") or "").split():
        if cls.startswith("mod-"):
            return cls[len("mod-") :] or None
    return None
