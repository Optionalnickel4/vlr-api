"""Preview-only adapter. GET/SELECT only; no refresh, cache writes, or scheduler."""
import asyncio
from datetime import datetime, timedelta, timezone
import json
import re
from fastapi import FastAPI, HTTPException, Path, Query, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.exceptions import RequestValidationError
from sqlalchemy import select, text
from app.core.cache import get_redis
from app.core.db import SessionLocal
from app.services.search import db_search_stmt
from app.models import PlayerSnapshot
from app.ratings.dimensions import compute_dimensions
from app.services.trends import build_player_response

# No app.main import/lifespan: never initialize schema, scheduler or scrapers.
# A route handler deadline cancels storage work itself (BaseHTTPMiddleware's
# call_next would leave a child task running until its task group finished).
READ_TIMEOUT_SECONDS = 8


class BoundedReadRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def bounded(request: Request):
            try:
                async with asyncio.timeout(READ_TIMEOUT_SECONDS):
                    return await handler(request)
            except (HTTPException, RequestValidationError):
                raise
            except TimeoutError:
                return JSONResponse({"detail": "Preview read timed out"}, status_code=503)
            except Exception:
                return JSONResponse({"detail": "Read-only preview source unavailable"}, status_code=503)
        return bounded


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
app.router.route_class = BoundedReadRoute


@app.get('/health')
async def health():
    return {'status': 'ok', 'mode': 'read-only preview'}


@app.get('/api/v1/players/{player_id}/dimensions')
async def player_dimensions(
    player_id: str = Path(pattern=r"^[0-9]{1,12}$"),
    region: str = Query("na"), timespan: str = Query("all"),
):
    region = region.lower()
    if region not in ("na", "eu"):
        raise HTTPException(400, "region must be one of ['na', 'eu']")
    if timespan not in ("30d", "60d", "90d", "all"):
        raise HTTPException(400, "timespan must be one of ['30d', '60d', '90d', 'all']")
    # Do NOT delegate to the public route: it refreshes missing cohorts/players.
    raw = await get_redis().get(f"vlr:stats:{region}:{timespan}")
    cohort = json.loads(raw) if raw is not None else None
    if not cohort:
        raise HTTPException(503, "cohort unavailable in cache-only preview")
    player = next((r for r in cohort if str(r.get("player_id")) == player_id), None)
    if player is None:
        raise HTTPException(404, f"player {player_id} not found in {region}/{timespan} leaderboard")
    return {"player_id": player_id, "region": region, "timespan": timespan,
            **compute_dimensions(player, cohort)}


@app.get('/api/v1/trends/player/{player_id}')
async def player_trend(
    player_id: str = Path(pattern=r"^[0-9]{1,12}$"),
    days: int = Query(90, ge=1, le=365),
):
    # Match the API's history/identity semantics and share its pure aggregation.
    # The database enforces read-only for this transaction, including future edits.
    async with SessionLocal() as session:
        await session.execute(text("SET TRANSACTION READ ONLY"))
        snapshots = (await session.execute(
            select(PlayerSnapshot).where(PlayerSnapshot.player_id == player_id)
            .order_by(PlayerSnapshot.captured_at.asc())
        )).scalars().all()
    if not snapshots:
        raise HTTPException(404, f"no snapshot history for player {player_id}")
    rows = [{"captured_at": s.captured_at, "alias": s.alias, "team": s.team,
             "agent_stats": s.agent_stats} for s in snapshots]
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return build_player_response(player_id, days, rows, cutoff)


@app.get('/api/v1/{path:path}')
async def read(path: str, request: Request):
    try:
        trend = re.fullmatch(r'trends/team/(\d+)', path)
        if trend:
            from app.services.trends import team_trend
            days = max(1, min(365, int(request.query_params.get('days', '90'))))
            return await team_trend(trend[1], days)
        if path == 'players':
            q = ' '.join(request.query_params.get('q', '').split())
            if len(q) < 2:
                return {'data': [], 'stale': False}
            async with SessionLocal() as session:
                await session.execute(text('SET TRANSACTION READ ONLY'))
                rows = (await session.execute(db_search_stmt(q[:100]))).all()
            data = [dict(id=r.player_id, alias=r.alias, team=r.team, country=r.country, source='db') for r in rows]
            return {'data': data, 'stale': False}
        keys = {'matches/results':'vlr:results', 'matches/upcoming':'vlr:upcoming', 'matches/live':'vlr:live', 'news':'vlr:news', 'events':'vlr:events'}
        key = keys.get(path)
        if path == 'rankings':
            region = request.query_params.get('region', 'all')
            if not re.fullmatch(r'[a-z-]+', region):
                return JSONResponse({'error':'Invalid region'}, status_code=400)
            key = f'vlr:rankings:{region}'
        if path == 'stats':
            region = request.query_params.get('region', 'na')
            timespan = request.query_params.get('timespan', 'all')
            if region not in ('na','eu') or timespan not in ('all','30d','60d','90d'):
                return JSONResponse({'error':'Invalid filter'}, status_code=400)
            key = f'vlr:stats:{region}:{timespan}'
        detail = re.fullmatch(r'(match|player|team)/(\d+)', path)
        if detail:
            key = f'vlr:{detail[1]}:{detail[2]}'
        if not key:
            return JSONResponse({'error':'Not available in cache-only preview'}, status_code=503)
        raw = await get_redis().get(key)
        stale = False
        if raw is None and (path in ('rankings','events')):
            raw = await get_redis().get(key + ':retained')
            stale = raw is not None
        if raw is None:
            return JSONResponse({'error':'Preview cache miss; refresh disabled'}, status_code=503)
        data = json.loads(raw)
        if path == 'stats':
            minimum = int(request.query_params.get('min_rnd', '0'))
            return {'data': [r for r in data if (r.get('rnd') or 0) >= minimum], 'stale': stale}
        return JSONResponse(data, headers={'Cache-Control':'no-store','X-VLR-Cache':'stale' if stale else 'fresh'})
    except Exception:
        return JSONResponse({'error':'Read-only preview source unavailable'}, status_code=503)
