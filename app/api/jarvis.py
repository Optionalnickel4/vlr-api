"""Scoped server-to-server Jarvis contract, isolated from legacy callers."""
import asyncio
import hashlib
import hmac
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Body, Header, Query
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.cache import get_redis
from app.schemas.jarvis import JARVIS_REQUEST_ADAPTER
from app.services import jarvis as J

router = APIRouter()
REQUEST_TIMEOUT = 3.0
# Atomic fixed window shared across workers; only authenticated client keys exist.
LIMIT = """
local n = redis.call('INCR', KEYS[1])
if n == 1 then redis.call('EXPIRE', KEYS[1], 60) end
return {n, redis.call('TTL', KEYS[1])}
"""


def reply(body, status=200, **headers):
    return JSONResponse(body, status_code=status, headers={'Cache-Control': 'no-store', **headers})


def token_for(authorization: str | None):
    """Return the configured token only for a constant-time Bearer match."""
    try:
        token = Path(get_settings().jarvis_token_file).read_text().strip()
    except (OSError, ValueError):
        return None, 'auth_unconfigured'
    if not token:
        return None, 'auth_unconfigured'
    expected = 'Bearer ' + token
    if not authorization or not hmac.compare_digest(authorization.encode(), expected.encode()):
        return None, 'unauthorized'
    return token, None


async def take_quota(token: str):
    client = hashlib.sha256(token.encode()).hexdigest()[:24]
    return await get_redis().eval(LIMIT, 1, f'vlr:jarvis:limit:{client}')


@router.get('/jarvis/team-match')
async def team_match(
    team_id: str | None = Query(None, pattern=r'^[0-9]{1,16}$'),
    name: str | None = Query(None, min_length=2, max_length=64),
    kind: Literal['auto', 'live', 'upcoming', 'completed'] = 'auto',
    authorization: str | None = Header(None),
):
    token, auth_error = token_for(authorization)
    if auth_error == 'auth_unconfigured':
        return reply(J.response('unavailable', code='auth_unconfigured'), 503)
    if auth_error:
        return reply(J.response('unavailable', code='unauthorized'), 401, **{'WWW-Authenticate': 'Bearer'})
    if not team_id and (not name or len(J.S.normalize_term(name)) < 2):
        return reply(J.response('unavailable', code='invalid_query'), 422)
    try:
        async with asyncio.timeout(REQUEST_TIMEOUT):
            count, ttl = await take_quota(token)
            if count > 30:
                return reply(J.response('unavailable', code='rate_limited'), 429, **{'Retry-After': str(max(1, ttl))})
            body = await J.team_match(team_id, name, kind)
            return reply(body, 409 if body['state'] == 'ambiguous' else 503 if body['state'] == 'unavailable' else 200)
    except TimeoutError:
        return reply(J.response('unavailable', code='timeout'), 504)
    except Exception:
        return reply(J.response('unavailable', code='storage_unavailable'), 503)


@router.post('/jarvis/query')
async def query(
    payload: Any = Body(...),
    authorization: str | None = Header(None),
):
    """Bounded cache/DB-only operations for general Jarvis questions."""
    token, auth_error = token_for(authorization)
    operation = payload.get('operation') if isinstance(payload, dict) else None
    operation = operation if isinstance(operation, str) and len(operation) <= 64 else None
    if auth_error == 'auth_unconfigured':
        return reply(J.query_response(operation, 'unavailable', code='auth_unconfigured'), 503)
    if auth_error:
        return reply(
            J.query_response(operation, 'unavailable', code='unauthorized'),
            401, **{'WWW-Authenticate': 'Bearer'},
        )
    try:
        request = JARVIS_REQUEST_ADAPTER.validate_python(payload)
    except ValidationError:
        return reply(J.query_response(operation, 'error', code='invalid_request'), 422)

    try:
        async with asyncio.timeout(REQUEST_TIMEOUT):
            count, ttl = await take_quota(token)
            if count > 30:
                return reply(
                    J.query_response(request.operation, 'error', code='rate_limited'),
                    429, **{'Retry-After': str(max(1, ttl))},
                )
            body = await J.query(request)
            status = 409 if body['state'] == 'ambiguous' else 503 if body['state'] == 'unavailable' else 200
            return reply(body, status)
    except TimeoutError:
        return reply(J.query_response(request.operation, 'unavailable', code='timeout'), 504)
    except Exception:
        return reply(J.query_response(request.operation, 'unavailable', code='storage_unavailable'), 503)
