"""Jarvis v1: read-only orchestration; never calls refresh or upstream HTTP."""
from datetime import datetime, timezone
import re

from sqlalchemy import select

from app.core.cache import cache_get
from app.core.db import SessionLocal
from app.models import TeamSnapshot
from app.services import assistant as A, refresh as R, search as S


def identity(value):
    return {"id": str(value['id']) if value.get('id') is not None else None,
            "name": (value.get('name') or None) if A._norm(value.get('name')) not in
            {'tbd', 'tba', 'unknown', '?', '-'} else None}


def freshness():
    # These bare cache payloads have no acquisition timestamp. TTL is not one.
    return {"status": "unknown", "captured_at": None, "age_seconds": None}


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
