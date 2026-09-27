"""Preview-only adapter. GET/SELECT only; no refresh, cache writes, or scheduler."""
import json
import re
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from app.core.cache import get_redis
from app.core.db import SessionLocal
from app.services.search import db_search_stmt

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

@app.get('/health')
async def health():
    return {'status': 'ok', 'mode': 'read-only preview'}

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
