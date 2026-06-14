"""Player search: hybrid DB-first, VLR-autocomplete fallback.

Architecture rule holds. The PRIMARY source is our own banked PlayerSnapshot data
— a clean DB read, no scrape. VLR's typeahead is touched ONLY on a DB miss, and
the result is cached per normalized term exactly like the detail endpoints cache
their scrape-on-miss — so it is never a per-keystroke inline scrape.

Self-healing flywheel: a fallback hit returns immediately (source="vlr"); when the
user clicks through to that player's /player/{id} page, the existing route banks a
PlayerSnapshot, so the player becomes DB-searchable (source="db") thereafter. The
fallback never eagerly fetches full player pages — that would be abusive.

The pure helpers (statement builder, autocomplete parser) test without a DB or
network; the orchestrator is exercised with both sources mocked.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import quote

from sqlalchemy import or_, select

from app.core.cache import cache_get, cache_set
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.http import get_client
from app.models import PlayerSnapshot

log = logging.getLogger("vlr.search")

MIN_QUERY_LEN = 2  # a single letter would scan everything for no signal
RESULT_CAP = 12
CACHE_SEARCH = "vlr:search:{term}"

# numeric player id out of a VLR autocomplete id ("/search/r/player/9/ac")
_PLAYER_ID_RE = re.compile(r"/player/(\d+)/")


def normalize_term(q: str) -> str:
    """Trim + collapse a raw query for matching and the cache key."""
    return " ".join((q or "").split())


# ---- primary: DB (pure statement builder + the read) ------------------------
def db_search_stmt(q: str, cap: int = RESULT_CAP):
    """The DISTINCT-ON-player_id, latest-snapshot-per-player search statement.
    Pure (no session) so its shape — ILIKE on alias OR real_name, distinct-latest,
    capped — is assertable by compiling it, without a live DB."""
    like = f"%{q}%"
    return (
        select(
            PlayerSnapshot.player_id,
            PlayerSnapshot.alias,
            PlayerSnapshot.team,
            PlayerSnapshot.country,
        )
        .where(
            or_(
                PlayerSnapshot.alias.ilike(like),
                PlayerSnapshot.real_name.ilike(like),
            )
        )
        .distinct(PlayerSnapshot.player_id)
        .order_by(PlayerSnapshot.player_id, PlayerSnapshot.captured_at.desc())
        .limit(cap)
    )


async def db_search(q: str, cap: int = RESULT_CAP) -> list[dict[str, Any]]:
    """Run the DB search and shape the hits. Read-only; raises on a real DB error
    (the orchestrator maps that to graceful-empty)."""
    async with SessionLocal() as session:
        rows = (await session.execute(db_search_stmt(q, cap))).all()
    return [
        {
            "id": r.player_id,
            "alias": r.alias,
            "team": r.team,
            "country": r.country,
            "source": "db",
        }
        for r in rows
    ]


# ---- fallback: VLR autocomplete (pure parser + the cached fetch) ------------
def parse_vlr_autocomplete(raw: str | bytes, cap: int = RESULT_CAP) -> list[dict[str, Any]]:
    """Pure: VLR /search/auto JSON -> player hits. Skips the category headers
    (id "#") and non-player entries (events/teams) — only items whose id carries a
    /player/<digits>/ survive. De-duped by id, capped. Bad JSON -> []."""
    try:
        items = json.loads(raw)
    except (ValueError, TypeError):
        return []
    if not isinstance(items, list):
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for it in items:
        if not isinstance(it, dict):
            continue
        m = _PLAYER_ID_RE.search(str(it.get("id", "")))
        if not m:
            continue  # category header / event / team
        pid = m.group(1)
        if pid in seen:
            continue
        seen.add(pid)
        out.append(
            {
                "id": pid,
                "alias": it.get("value") or None,
                "team": None,
                "country": None,
                "source": "vlr",
            }
        )
        if len(out) >= cap:
            break
    return out


async def vlr_fallback(term: str, cap: int = RESULT_CAP) -> list[dict[str, Any]]:
    """VLR autocomplete on a DB miss, cached per normalized term so a repeated miss
    for the same term doesn't re-hit vlr (scrape-on-miss, like the detail routes)."""
    key = CACHE_SEARCH.format(term=term.casefold())
    cached = await cache_get(key)
    if cached is not None:
        return cached
    raw = await get_client().get_html(f"/search/auto/?term={quote(term)}")
    hits = parse_vlr_autocomplete(raw, cap)
    await cache_set(key, hits, get_settings().ttl_search)
    return hits


# ---- orchestrator -----------------------------------------------------------
async def search_players(q: str) -> dict[str, Any]:
    """{data, stale, error} of {id, alias, team?, country?, source}. DB first; VLR
    autocomplete only on a DB miss. Never raises: a DB error or a failed fallback
    degrades to a graceful empty result with the error noted."""
    term = normalize_term(q)
    if len(term) < MIN_QUERY_LEN:
        return {"data": [], "stale": False, "error": None}

    try:
        hits = await db_search(term, RESULT_CAP)
    except Exception as exc:  # DB down / bad query -> graceful, never 500
        log.warning("player search: DB query failed for %r", term, exc_info=True)
        return {"data": [], "stale": True, "error": str(exc)}

    if hits:
        return {"data": hits, "stale": False, "error": None}

    # DB miss -> VLR autocomplete fallback (cached). A failure here still returns
    # the (empty) DB result gracefully rather than 500ing.
    try:
        hits = await vlr_fallback(term, RESULT_CAP)
        return {"data": hits, "stale": False, "error": None}
    except Exception as exc:
        log.warning("player search: VLR fallback failed for %r", term, exc_info=True)
        return {"data": [], "stale": True, "error": str(exc)}
