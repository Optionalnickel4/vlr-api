"""Jarvis v1: read-only orchestration; never calls refresh or upstream HTTP."""
from datetime import datetime, timezone
import re
from typing import Any

from sqlalchemy import select

from app.core.cache import cache_get
from app.core.db import SessionLocal
from app.models import MatchResult, TeamSnapshot
from app.schemas import jarvis as Q
from app.services import assistant as A, refresh as R, search as S


def identity(value):
    return {"id": str(value['id']) if value.get('id') is not None else None,
            "name": (value.get('name') or None) if A._norm(value.get('name')) not in
            {'tbd', 'tba', 'unknown', '?', '-'} else None}


def freshness():
    # These bare cache payloads have no acquisition timestamp. TTL is not one.
    return {"status": "unknown", "captured_at": None, "age_seconds": None}


def _coverage(status="partial", source="cache", cache_status="present", **values):
    return {
        "status": status,
        "source": source,
        "cache_status": cache_status,
        "observed_items": values.pop("observed_items", 0),
        "matched_items": values.pop("matched_items", 0),
        "returned_items": values.pop("returned_items", 0),
        "truncated": values.pop("truncated", False),
        "limitations": values.pop("limitations", []),
        **values,
    }


def query_response(operation, state, items=None, code=None, candidates=None, coverage=None):
    """Stable envelope shared by every operation and endpoint-generated error."""
    return {
        "schema_version": "1",
        "operation": operation,
        "state": state,
        "items": items or [],
        "candidates": candidates or [],
        "error": code,
        "coverage": coverage or _coverage(
            "unavailable", cache_status="unknown",
            limitations=["No coverage could be established for this response."],
        ),
        "freshness": {
            "served_at": datetime.now(timezone.utc).isoformat(),
            **freshness(),
        },
    }


def response(state, team=None, match=None, code=None, candidates=None):
    return {"schema_version": "1", "state": state, "team": team, "match": match,
            "candidates": candidates or [], "error": code,
            "freshness": {"served_at": datetime.now(timezone.utc).isoformat(), **freshness()}}


async def db_team(team_id):
    async with SessionLocal() as session:
        row = (await session.execute(select(TeamSnapshot).where(
            TeamSnapshot.team_id == team_id).order_by(TeamSnapshot.captured_at.desc()).limit(1))).scalar_one_or_none()
        return {"id": row.team_id, "name": row.name} if row else None


def number(value):
    return int(value) if value is not None and re.fullmatch(r"\d+", str(value)) else None


def shape(team, card, state, detail):
    header = detail.get('teams') or []
    side = next((i for i, t in enumerate(header[:2]) if str(t.get('id')) == team['id']), None)
    # Never guess side zero or override a conflicting stable ID using a name.
    if side is None:
        side = next((i for i, t in enumerate(header[:2]) if t.get('id') is None
                     and A._norm(t.get('name')) == A._norm(team['name']) and team['name']), None)
    opponent = {"id": card.get('opponent_id'), "name": card.get('opponent')}
    scores = [None, None]
    if state == 'completed' and card.get('score'):
        pair = re.fullmatch(r"\s*(\d+)\s*[:–-]\s*(\d+)\s*", str(card['score']))
        if pair:
            scores = list(map(int, pair.groups()))
    names = card.get('teams') or []
    if team['name'] and A._norm(team['name']) in [A._norm(n) for n in names]:
        ci = [A._norm(n) for n in names].index(A._norm(team['name']))
        if len(names) == 2:
            opponent['name'] = names[1-ci]
            raw = card.get('scores') or []
            if len(raw) == 2 and state != 'upcoming':
                scores = [number(raw[ci]), number(raw[1-ci])]
    maps = []
    if side is not None and len(header) == 2:
        opponent = identity({"id": header[1-side].get('id') or opponent.get('id'),
                             "name": header[1-side].get('name') or opponent.get('name')})
        if state != 'upcoming':
            observed = [number(header[side].get('score')), number(header[1-side].get('score'))]
            scores = [n if n is not None else scores[i] for i, n in enumerate(observed)]
        for m in detail.get('maps') or []:
            raw = m.get('scores') or [None, None]
            pair = [number(raw[side]), number(raw[1-side])] if len(raw) == 2 else [None, None]
            if any(r.get('winner') in (1, 2) for r in m.get('rounds') or []):
                counts = A.count_map_rounds(m)
                if pair == [None, None]:
                    pair = [counts[side], counts[1-side]]
            maps.append({"name": m.get('name'), "round_score": dict(zip(('team', 'opponent'), pair))})
    mid = str(card['id']) if card.get('id') is not None else None
    return {"id": mid, "state": state, "opponent": identity(opponent),
            "event": detail.get('event') or card.get('event'),
            "url": f"https://www.vlr.gg/{mid}" if mid and mid.isdigit() else None,
            "series_score": dict(zip(('team', 'opponent'), scores)), "maps": maps,
            "source_date": {"display_date": card.get('date'), "display_time": card.get('time'), "starts_at": None},
            "freshness": freshness()}


async def team_match(team_id=None, name=None, kind='auto'):
    detail = None
    if team_id:
        detail = await cache_get(R.CACHE_TEAM.format(id=team_id))
        team = identity(detail) if detail else await db_team(team_id)
    else:
        term = S.normalize_term(name)
        # Escape LIKE wildcards; use the existing DB search and cached autocomplete only.
        hits = await S.db_team_search(term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_'))
        cached = await cache_get(S.CACHE_TEAM_SEARCH.format(term=term.casefold()))
        hits = {str(h['id']): identity(h) for h in [*hits, *(cached or [])] if h.get('id')}
        if len(hits) > 1:
            return response('ambiguous', code='ambiguous_team', candidates=list(hits.values()))
        team = next(iter(hits.values()), None)
    if not team:
        return response('unavailable', code='team_not_cached')
    team = identity(team)
    if detail is None:
        detail = await cache_get(R.CACHE_TEAM.format(id=team['id']))
    states = ['live', 'upcoming', 'completed'] if kind == 'auto' else [kind]
    missing = False
    for state in states:
        key = {'live': R.CACHE_LIVE, 'upcoming': R.CACHE_UPCOMING, 'completed': R.CACHE_RESULTS}[state]
        listing = await cache_get(key)
        cards = [c for c in listing or [] if team['name'] and
                 A._norm(team['name']) in [A._norm(n) for n in c.get('teams') or []]]
        if state != 'live' and detail is not None:
            cards = detail.get('upcoming' if state == 'upcoming' else 'results') or cards
        if listing is None and (state == 'live' or detail is None):
            missing = True
        if not cards:
            continue
        card = cards[0]  # Source order: next schedule / newest result, as legacy assistant.
        match_detail = await cache_get(R.CACHE_MATCH.format(id=card['id'])) if card.get('id') else None
        if match_detail:
            observed_state = {'final': 'completed', 'live': 'live'}.get(match_detail.get('status'))
            if observed_state and observed_state != state:
                return response('unavailable', team, code='state_conflict')
            ids = [str(t['id']) for t in match_detail.get('teams') or [] if t.get('id') is not None]
            if ids and team['id'] not in ids:
                return response('unavailable', team, code='identity_conflict')
        match = shape(team, card, state, match_detail or {})
        partial = missing or match_detail is None or match['opponent']['name'] is None
        return response('partial' if partial else 'ok', team, match,
                        'partial_data' if partial else None)
    return response('unavailable' if missing else 'empty', team,
                    code='cache_miss' if missing else 'no_match')


# ---------------------------------------------------------------------------
# General query contract. These operations deliberately read only the cache and
# banked snapshots. Do not replace any of these calls with search_teams(),
# refresh_*(), or a public API route: those paths can scrape on a miss.

_MATCH_KEYS = {
    "live": R.CACHE_LIVE,
    "upcoming": R.CACHE_UPCOMING,
    "completed": R.CACHE_RESULTS,
}

_LIST_LIMITATIONS = {
    "live": [
        "Only the current cached VLR /matches live partition is covered.",
        "The cache payload has no acquisition timestamp or region field.",
        "Match cards do not provide a timezone-qualified start timestamp.",
    ],
    "upcoming": [
        "Only the current cached VLR /matches upcoming partition is covered.",
        "The cache payload has no acquisition timestamp or region field.",
        "Source display times are not converted because their timezone is unknown.",
    ],
    "completed": [
        "The cached results feed is a rolling recent sample, not complete history.",
        "The cache payload has no acquisition timestamp or region field.",
        "Source display times are not converted because their timezone is unknown.",
    ],
}


def _canonical(kind: str, value: object) -> str | None:
    entity_id = str(value) if value is not None else ""
    return f"https://www.vlr.gg/{kind}/{entity_id}" if entity_id.isdigit() else None


def _match_url(value: object) -> str | None:
    match_id = str(value) if value is not None else ""
    return f"https://www.vlr.gg/{match_id}" if match_id.isdigit() else None


def _score(value: object) -> int | None:
    return int(value) if value is not None and re.fullmatch(r"\d+", str(value).strip()) else None


def _match_item(card: dict[str, Any], state: str | None, *, match_id=None) -> dict[str, Any]:
    mid = str(match_id if match_id is not None else card.get("id"))
    raw_teams = card.get("teams") if isinstance(card.get("teams"), list) else []
    raw_ids = card.get("team_ids") if isinstance(card.get("team_ids"), list) else []
    raw_scores = card.get("scores") if isinstance(card.get("scores"), list) else []
    teams = []
    for index in range(min(2, max(len(raw_teams), len(raw_ids), len(raw_scores)))):
        raw_team = raw_teams[index] if index < len(raw_teams) else None
        if isinstance(raw_team, dict):
            team_id = raw_team.get("id")
            name = raw_team.get("name")
            score = raw_team.get("score")
        else:
            team_id = raw_ids[index] if index < len(raw_ids) else None
            name = raw_team
            score = raw_scores[index] if index < len(raw_scores) else None
        teams.append({
            "id": str(team_id) if team_id is not None else None,
            "name": name or None,
            "score": None if state == "upcoming" else _score(score),
        })
    return {
        "id": mid if mid.isdigit() else None,
        "state": state,
        "teams": teams,
        "event": card.get("event") or None,
        "series": card.get("series") or None,
        "region": None,
        "starts_at": None,
        "source_time": {
            "display_time": card.get("time") or card.get("date") or None,
            "relative_eta": card.get("eta") or None,
        },
        "url": _match_url(mid),
        "freshness": freshness(),
    }


def _norm(value: object) -> str:
    return A._norm(str(value)) if value is not None else ""


async def matches_list(params: Q.MatchesListParams):
    rows = await cache_get(_MATCH_KEYS[params.state])
    if rows is None:
        return query_response(
            "matches.list", "unavailable", code="cache_miss",
            coverage=_coverage(
                "unavailable", cache_status="missing",
                limitations=_LIST_LIMITATIONS[params.state],
            ),
        )
    if not isinstance(rows, list):
        return query_response(
            "matches.list", "unavailable", code="invalid_cache_payload",
            coverage=_coverage(
                "unavailable", cache_status="invalid",
                limitations=_LIST_LIMITATIONS[params.state],
            ),
        )

    filtered = [row for row in rows if isinstance(row, dict)]
    if params.team:
        wanted = _norm(params.team)
        filtered = [
            row for row in filtered
            if wanted in {_norm(team) for team in row.get("teams") or []}
        ]
    if params.event:
        wanted = _norm(params.event)
        filtered = [row for row in filtered if wanted in _norm(row.get("event"))]
    selected = filtered[:params.limit]
    items = [_match_item(row, params.state) for row in selected]
    coverage = _coverage(
        "partial", observed_items=len(rows), matched_items=len(filtered),
        returned_items=len(items), truncated=len(filtered) > params.limit,
        limitations=_LIST_LIMITATIONS[params.state],
        ordering="source_order",
        supported_filters=["team", "event"],
        unsupported_filters=["region", "time_window"],
    )
    return query_response(
        "matches.list", "ok" if items else "empty", items=items,
        code=None if items else "no_cached_matches", coverage=coverage,
    )


async def _db_match(match_id: str):
    async with SessionLocal() as session:
        return (await session.execute(
            select(MatchResult).where(MatchResult.vlr_id == match_id).limit(1)
        )).scalar_one_or_none()


async def matches_get(params: Q.MatchesGetParams):
    detail = await cache_get(R.CACHE_MATCH.format(id=params.match_id))
    if isinstance(detail, dict):
        observed = {"final": "completed", "live": "live"}.get(detail.get("status"))
        state = observed
        item = _match_item(detail, state, match_id=params.match_id)
        return query_response(
            "matches.get", "ok", items=[item],
            coverage=_coverage(
                "partial", observed_items=1, matched_items=1, returned_items=1,
                limitations=[
                    "This is one cached match detail with no acquisition timestamp.",
                    "Match state remains null when cached detail does not establish it.",
                    "A timezone-qualified start timestamp is not stored.",
                ],
            ),
        )

    saw_listing = False
    for state, key in _MATCH_KEYS.items():
        rows = await cache_get(key)
        if rows is None:
            continue
        saw_listing = True
        card = next((row for row in rows if isinstance(row, dict) and str(row.get("id")) == params.match_id), None)
        if card:
            return query_response(
                "matches.get", "ok", items=[_match_item(card, state)],
                coverage=_coverage(
                    "partial", observed_items=1, matched_items=1, returned_items=1,
                    limitations=_LIST_LIMITATIONS[state] + ["Cached match detail is unavailable."],
                ),
            )

    row = await _db_match(params.match_id)
    if row:
        item = _match_item({
            "id": row.vlr_id,
            "teams": [row.team_a, row.team_b],
            "team_ids": [row.team_a_id, row.team_b_id],
            "scores": [row.score_a, row.score_b],
            "event": row.event,
            "series": row.series,
        }, "completed")
        return query_response(
            "matches.get", "ok", items=[item],
            coverage=_coverage(
                "partial", source="database", cache_status="missing",
                observed_items=1, matched_items=1, returned_items=1,
                limitations=[
                    "The database contains sampled completed results, not complete history.",
                    "Older feed rows often have no stable team IDs or match start timestamp.",
                ],
            ),
        )
    return query_response(
        "matches.get", "unavailable", code="match_not_cached",
        coverage=_coverage(
            "unavailable", cache_status="present" if saw_listing else "missing",
            limitations=[
                "The requested match is absent from bounded caches and sampled result history.",
                "Absence is not proof that the VLR match does not exist.",
            ],
        ),
    )


def _team_item(raw: dict[str, Any], team_id=None) -> dict[str, Any]:
    tid = str(team_id if team_id is not None else raw.get("id") or raw.get("team_id") or "")
    return {
        "id": tid if tid.isdigit() else None,
        "name": raw.get("name") or raw.get("team") or None,
        "tag": raw.get("tag") or None,
        "region": raw.get("country") or raw.get("region") or None,
        "url": _canonical("team", tid),
    }


async def teams_search(params: Q.TeamsSearchParams):
    term = S.normalize_term(params.query)
    escaped = term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    db_error = False
    try:
        db_hits = await S.db_team_search(escaped, params.limit)
    except Exception:
        db_error = True
        db_hits = []
    cached = await cache_get(S.CACHE_TEAM_SEARCH.format(term=term.casefold()))
    cache_hits = cached if isinstance(cached, list) else []
    unique = {}
    for raw in [*db_hits, *cache_hits]:
        if isinstance(raw, dict) and raw.get("id") is not None:
            unique.setdefault(str(raw["id"]), _team_item(raw))
    items = list(unique.values())[:params.limit]
    state = "ok" if items else "unavailable" if db_error else "empty"
    return query_response(
        "teams.search", state, items=items,
        code=None if items else "search_storage_unavailable" if db_error else "no_cached_teams",
        coverage=_coverage(
            "partial" if not db_error else "unavailable" if not items else "partial",
            source="database_and_cache", cache_status="present" if cached is not None else "missing",
            observed_items=len(unique), matched_items=len(unique), returned_items=len(items),
            truncated=len(unique) > params.limit,
            limitations=[
                "Search covers banked team snapshots and an exact-term autocomplete cache only.",
                "A miss never triggers upstream autocomplete or a team-page scrape.",
                "The banked team set is not a complete VLR team directory.",
            ] + (["The team snapshot database search was unavailable."] if db_error else []),
        ),
    )


async def _db_team_detail(team_id: str):
    async with SessionLocal() as session:
        return (await session.execute(
            select(TeamSnapshot).where(TeamSnapshot.team_id == team_id)
            .order_by(TeamSnapshot.captured_at.desc()).limit(1)
        )).scalar_one_or_none()


async def teams_get(params: Q.TeamsGetParams):
    cached = await cache_get(R.CACHE_TEAM.format(id=params.team_id))
    if isinstance(cached, dict):
        return query_response(
            "teams.get", "ok", items=[_team_item(cached, params.team_id)],
            coverage=_coverage(
                "partial", observed_items=1, matched_items=1, returned_items=1,
                limitations=[
                    "This is one cached team detail with no acquisition timestamp.",
                    "The response is an identity summary, not a current roster guarantee.",
                ],
            ),
        )
    row = await _db_team_detail(params.team_id)
    if row:
        return query_response(
            "teams.get", "ok", items=[_team_item({
                "id": row.team_id, "name": row.name, "region": row.region,
            })],
            coverage=_coverage(
                "partial", source="database", cache_status="missing",
                observed_items=1, matched_items=1, returned_items=1,
                limitations=[
                    "This is the latest on-demand team snapshot, not a complete current directory.",
                    "The API does not infer current roster freshness from snapshot age.",
                ],
            ),
        )
    return query_response(
        "teams.get", "unavailable", code="team_not_cached",
        coverage=_coverage(
            "unavailable", cache_status="missing",
            limitations=[
                "No cached or banked team snapshot exists for this ID.",
                "Absence is not proof that the VLR team does not exist.",
            ],
        ),
    )


def capabilities():
    supported = [
        {
            "operation": "capabilities", "available": True,
            "parameters": {}, "max_items": 9,
        },
        {
            "operation": "matches.list", "available": True,
            "parameters": {
                "state": ["live", "upcoming", "completed"],
                "limit": {"default": 10, "min": 1, "max": 25},
                "filters": ["team", "event"],
                "unsupported_filters": ["region", "time_window"],
            },
            "max_items": 25,
        },
        {
            "operation": "matches.get", "available": True,
            "parameters": {"match_id": "numeric VLR match ID"}, "max_items": 1,
        },
        {
            "operation": "teams.search", "available": True,
            "parameters": {"query": "2-64 characters", "limit": {"default": 8, "min": 1, "max": 12}},
            "max_items": 12,
        },
        {
            "operation": "teams.get", "available": True,
            "parameters": {"team_id": "numeric VLR team ID"}, "max_items": 1,
        },
    ]
    planned = [
        {
            "operation": "rankings.list", "available": False,
            "gap": "Only world rankings are scheduler-warmed; regional caches are traffic-dependent and cache acquisition time is not stored.",
        },
        {
            "operation": "players.summary", "available": False,
            "gap": "Player snapshots are on-demand or limited prefetch samples, so they are neither a complete directory nor uniformly current.",
        },
        {
            "operation": "news.list", "available": False,
            "gap": "The news cache has no per-item capture time and the normalized Jarvis contract has not been implemented and verified.",
        },
        {
            "operation": "matches.head_to_head", "available": False,
            "gap": "Completed history is sampled, and many older rows lack stable IDs, so historical head-to-head would be incomplete and name-ambiguous.",
        },
    ]
    items = supported + planned
    return query_response(
        "capabilities", "ok", items=items,
        coverage=_coverage(
            "complete", source="static_contract", cache_status="not_applicable",
            observed_items=len(items), matched_items=len(items), returned_items=len(items),
            limitations=["Availability describes this schema version, not upstream VLR availability."],
        ),
    )


async def query(request):
    if isinstance(request, Q.CapabilitiesRequest):
        return capabilities()
    if isinstance(request, Q.MatchesListRequest):
        return await matches_list(request.params)
    if isinstance(request, Q.MatchesGetRequest):
        return await matches_get(request.params)
    if isinstance(request, Q.TeamsSearchRequest):
        return await teams_search(request.params)
    if isinstance(request, Q.TeamsGetRequest):
        return await teams_get(request.params)
    return query_response(None, "error", code="invalid_request")
