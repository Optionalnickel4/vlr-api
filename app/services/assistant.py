"""Assistant orchestration — one deterministic, name-driven "what about team X?"
answer for the Command Central / Jarvis dashboard.

The assistant talks in team NAMES ("the NRG game"); every other endpoint keys by
numeric id. This layer closes that gap and does the branching the LLM should NOT
have to orchestrate: resolve the name, then pick the team's single MOST RELEVANT
match in a fixed priority — LIVE now, else the NEXT scheduled one, else the LAST
completed result — and shape it so an LLM can render a sentence with no follow-up
calls.

LAYERING. This is a pure orchestration layer over data the API already has. It
NEVER adds new scraping: it reads the same caches the routes read and reuses the
exact bounded on-demand detail refreshes the /team/{id}, /match/{id} and
/matches/live routes already use on a cache miss. The name resolver is
services/search.search_teams (DB-first, VLR-autocomplete fallback).

THE ROUND-SCORE RULE (the whole point of the LIVE branch). A live map's rounds[]
carries a TRAILING NULL-STUB round — a not-yet-played slot with winner/side/
outcome/score all None (see scrapers/match_detail._parse_rounds). Counting rounds
naively would report one too many. `count_map_rounds` counts only rounds with a
real winner, so a map with 6 played rounds + 1 null stub reports 6, not 7. This is
the "one team has 4 round wins, the other 2" answer.

The pure helpers (round counting, current-map pick, live-card matching, shaping)
test with plain dicts — no DB, no network; the orchestrator is exercised with the
cache/detail reads mocked.
"""
from __future__ import annotations

import logging
from typing import Any

from app.core.cache import cache_get
from app.services import refresh as R
from app.services.search import search_teams

log = logging.getLogger("vlr.assistant")


def _envelope(data: Any, stale: bool = False, error: str | None = None) -> dict[str, Any]:
    return {"data": data, "stale": stale, "error": error}


def _none_answer(team: dict[str, Any] | None) -> dict[str, Any]:
    """The state="none" body. Always carries a `state` so the assistant can branch
    on it unconditionally, even for team-not-found."""
    return {"state": "none", "team": team, "match": None}


def _norm(s: str | None) -> str:
    return " ".join((s or "").split()).casefold()


# ---- pure: round-score off a live map (skips the trailing null-stub round) ----
def count_map_rounds(map_obj: dict[str, Any]) -> tuple[int, int]:
    """(team1_rounds, team2_rounds) from a map's rounds[]. A round with winner==1
    is a top-team round, winner==2 a bottom-team round; a null-stub round (winner
    None — the not-yet-played slot) is SKIPPED. So a live map with 6 played rounds
    plus 1 null stub returns totals summing to 6, never 7."""
    t1 = t2 = 0
    for rnd in map_obj.get("rounds") or []:
        w = rnd.get("winner")
        if w == 1:
            t1 += 1
        elif w == 2:
            t2 += 1
        # w is None -> trailing null-stub / unplayed slot -> skip
    return t1, t2


def pick_current_map(match_detail: dict[str, Any]) -> dict[str, Any] | None:
    """The map in progress: the LAST map (play order) that has at least one played
    round. Completed earlier maps also have rounds, so 'last with rounds' is the
    live one; a not-yet-started map has only null-stub rounds (or none) and is
    skipped. None when no map has a played round yet (match just went live)."""
    current = None
    for m in match_detail.get("maps") or []:
        t1, t2 = count_map_rounds(m)
        if t1 + t2 > 0:
            current = m
    return current


def _team_side_index(match_detail: dict[str, Any], team_id: str | None, team_name: str | None) -> int:
    """Which header side (0=team1/top, 1=team2/bottom) is OUR team. Header and
    per-map team order are the same top/bottom order on the vlr page, so this index
    aligns the header map-score AND the map round-score to the right team. Prefer id
    (exact), fall back to name, default to 0 so a shape is always returned."""
    header = match_detail.get("teams") or []
    for i, t in enumerate(header[:2]):
        if team_id is not None and str(t.get("id")) == str(team_id):
            return i
    for i, t in enumerate(header[:2]):
        if team_name and _norm(t.get("name")) == _norm(team_name):
            return i
    return 0


def find_live_card_for_team(
    live_list: list[dict[str, Any]], team_name: str | None
) -> dict[str, Any] | None:
    """The live /matches card whose two team NAMES include our team (live cards
    expose names, not ids). Exact case-insensitive match first, then a contains
    match either direction ('NRG' <-> 'NRG Esports'). None when the team has no
    live match right now — the common case, and the trigger to fall through to
    upcoming/last."""
    if not team_name:
        return None
    want = _norm(team_name)
    for card in live_list or []:
        names = [_norm(t) for t in (card.get("teams") or [])]
        if any(n == want for n in names):
            return card
    for card in live_list or []:
        names = [_norm(t) for t in (card.get("teams") or [])]
        if any(n and (want in n or n in want) for n in names):
            return card
    return None


# ---- pure: shape one state's match body from already-fetched data ------------
def shape_live(
    team: dict[str, Any], match_detail: dict[str, Any], live_card: dict[str, Any]
) -> dict[str, Any]:
    """LIVE body: map-level score AND the current-map round score, both oriented
    to OUR team. Round score comes from the current map's rounds[] via
    count_map_rounds (null-stub-safe)."""
    ti = _team_side_index(match_detail, team.get("id"), team.get("name"))
    oi = 1 - ti
    header = match_detail.get("teams") or []

    def _score(idx: int) -> int | None:
        if idx < len(header):
            s = header[idx].get("score")
            return int(s) if isinstance(s, int) else s
        return None

    def _hname(idx: int) -> str | None:
        return header[idx].get("name") if idx < len(header) else None

    current = pick_current_map(match_detail)
    current_map = None
    if current is not None:
        t1, t2 = count_map_rounds(current)
        per_side = (t1, t2)
        current_map = {
            "name": current.get("name"),
            "round_score": {"team": per_side[ti], "opponent": per_side[oi]},
        }

    return {
        "state": "live",
        "team": team,
        "match": {
            "id": match_detail.get("id"),
            "url": match_detail.get("url"),
            "event": match_detail.get("event"),
            "series": match_detail.get("series"),
            "status": "live",
            "format": match_detail.get("format"),
            "opponent": _hname(oi) or _other_name(live_card, team.get("name")),
            "map_score": {"team": _score(ti), "opponent": _score(oi)},
            "current_map": current_map,
        },
    }


def _other_name(live_card: dict[str, Any] | None, team_name: str | None) -> str | None:
    """The opponent name off a live card, best-effort, when the match header can't
    supply it."""
    if not live_card:
        return None
    names = [t for t in (live_card.get("teams") or []) if t]
    want = _norm(team_name)
    for n in names:
        if _norm(n) != want:
            return n
    return names[0] if names else None


def shape_upcoming(team: dict[str, Any], match: dict[str, Any]) -> dict[str, Any]:
    """NEXT body from a team-detail upcoming card (opponent, event, date). These
    cards have no decided result; time is vlr's own display string."""
    return {
        "state": "upcoming",
        "team": team,
        "match": {
            "id": match.get("id"),
            "url": match.get("url"),
            "status": "upcoming",
            "opponent": match.get("opponent"),
            "opponent_id": match.get("opponent_id"),
            "event": match.get("event"),
            "date": match.get("date"),
        },
    }


def shape_completed(team: dict[str, Any], match: dict[str, Any]) -> dict[str, Any]:
    """LAST body from a team-detail result card (opponent, score, win/loss, event)."""
    return {
        "state": "completed",
        "team": team,
        "match": {
            "id": match.get("id"),
            "url": match.get("url"),
            "status": "completed",
            "opponent": match.get("opponent"),
            "opponent_id": match.get("opponent_id"),
            "result": match.get("result"),
            "score": match.get("score"),
            "event": match.get("event"),
            "date": match.get("date"),
        },
    }


# ---- cache-first reads (reuse the exact route paths; bounded on-demand) -------
async def _get_live_list() -> list[dict[str, Any]]:
    """The live match list, cache-first with the same cold-start refresh the
    /matches/live route uses (one /matches scrape warms it)."""
    data = await cache_get(R.CACHE_LIVE)
    if data is None:
        await R.refresh_upcoming()
        data = await cache_get(R.CACHE_LIVE)
    return data or []


async def _get_match_detail(match_id: str) -> dict[str, Any]:
    """Match detail, cache-first then the bounded on-demand scrape (/match/{id}'s
    own path). The live-refresh job keeps live matches warm, so this is usually a
    cache hit."""
    data = await cache_get(R.CACHE_MATCH.format(id=match_id))
    if data is None:
        data = await R.refresh_match(str(match_id))
    return data


async def _get_team_detail(team_id: str) -> dict[str, Any]:
    """Team detail (results + upcoming), cache-first then the bounded on-demand
    scrape (/team/{id}'s own path)."""
    data = await cache_get(R.CACHE_TEAM.format(id=team_id))
    if data is None:
        data = await R.refresh_team(str(team_id))
    return data


# ---- orchestrator -----------------------------------------------------------
async def team_match(name: str) -> dict[str, Any]:
    """Resolve a team NAME, then return its single most relevant match in the
    fixed priority LIVE > NEXT > LAST as {data, stale, error}. `data.state` is
    always one of live|upcoming|completed|none so the assistant branches on it
    unconditionally. Never 500s: a missing name, a down DB, or a failed detail
    fetch degrades to a clean envelope error, never an exception."""
    resolved = await search_teams(name)
    teams = resolved.get("data") or []
    if not teams:
        # clean "not found" in the envelope — never a 500
        return _envelope(
            _none_answer(None),
            stale=bool(resolved.get("stale")),
            error=resolved.get("error") or f"team not found: {name}",
        )

    top = teams[0]
    team = {"id": top.get("id"), "name": top.get("name"), "tag": top.get("tag")}
    tid = str(top["id"]) if top.get("id") is not None else None

    stale = False
    error: str | None = None

    # (a) LIVE — a match in progress right now, with map + current-map round score.
    try:
        live_list = await _get_live_list()
        card = find_live_card_for_team(live_list, team.get("name"))
        if card and card.get("id"):
            detail = await _get_match_detail(str(card["id"]))
            return _envelope(shape_live(team, detail, card), stale=stale, error=error)
    except Exception as exc:
        log.warning("assistant: live lookup failed for %r", name, exc_info=True)
        stale, error = True, str(exc)

    # (b) NEXT / (c) LAST — both come from one team-detail read.
    if tid is None:
        return _envelope(_none_answer(team), stale=stale, error=error)
    try:
        detail = await _get_team_detail(tid)
    except Exception as exc:
        log.warning("assistant: team detail failed for %s", tid, exc_info=True)
        return _envelope(_none_answer(team), stale=True, error=str(exc))

    upcoming = detail.get("upcoming") or []
    if upcoming:
        return _envelope(shape_upcoming(team, upcoming[0]), stale=stale, error=error)

    results = detail.get("results") or []
    if results:
        return _envelope(shape_completed(team, results[0]), stale=stale, error=error)

    return _envelope(_none_answer(team), stale=stale, error=error)
