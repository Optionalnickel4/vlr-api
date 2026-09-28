"""Nine sequential GETs; no retries, redirects, raw payload retention or deployment."""
import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time
from urllib.parse import quote
import httpx
from app.services.trends import build_player_response
from scripts.probe_api import request

ROOT = Path(__file__).parent

async def main():
    selected = json.loads((ROOT/'api.json').read_text())['selected']
    pid = selected['player']['ids'][0]
    mid = selected['match']['ids'][0]
    # Search terms came from the selected live details, recorded by followup.py.
    searches = [r['path'] for r in json.loads((ROOT/'followup.json').read_text())['observations'] if '?q=' in r['path']]
    queue = ['/health', '/api/v1/status', f'/api/v1/match/{mid}', f'/api/v1/player/{pid}',
             f'/api/v1/trends/player/{pid}', f'/api/v1/history/player/{pid}?limit=3',
             f'/api/v1/players/{pid}/dimensions?region=na&timespan=all', *searches]
    report = {'limits': {'requests': 9, 'seconds': 300, 'deadline': 60, 'interval': 3, 'bytes': 2000000}, 'observations': []}
    end = time.monotonic()+300
    async with httpx.AsyncClient(base_url='http://10.0.0.21:8000', trust_env=False, follow_redirects=False,
                                 headers={'User-Agent':'VLR-API-read-only-probe/1.0'}) as c:
        while queue and len(report['observations']) < 9 and time.monotonic() < end:
            path = queue.pop(0)
            row, body = await request(c,path,min(60,end-time.monotonic()),2000000)
            if body is not None:
                if path.endswith('/status'):
                    row['facts'] = {k:body.get(k) for k in ('commit','checks')}
                elif path == f'/api/v1/match/{mid}':
                    row['facts'] = {'series_scores':[t.get('score') for t in body.get('teams',[])], 'winner_flags':[t.get('won') for t in body.get('teams',[])]}
                elif path == f'/api/v1/player/{pid}':
                    row['facts'] = {'recent_match_date_field_present':['date' in m for m in body.get('matches',[])]}
                elif path.startswith('/api/v1/history/player/'):
                    rows = [{**r,'captured_at':datetime.fromisoformat(r['captured_at'])} for r in body]
                    result = build_player_response(pid,90,rows,datetime.now(timezone.utc)-timedelta(days=90))
                    row['source_comparison'] = {'input':'same three API history rows in memory', 'points_from_current_source':len(result['rating_trend']), 'capture_range':[min(r['captured_at'] for r in rows).isoformat(),max(r['captured_at'] for r in rows).isoformat()]}
                elif '?q=' in path:
                    row['facts'] = {'ids':[r.get('id') for r in body.get('data',[])], 'sources':sorted({r.get('source','unknown') for r in body.get('data',[])})}
            report['observations'].append(row)
            print(json.dumps({k:row.get(k) for k in ('path','status','elapsed_ms','facts','source_comparison')}), flush=True)
            if row.get('failure') in ('timeout','transport') or row['status']==429 or 'retry-after' in row['headers']:
                break
            if queue:
                await asyncio.sleep(3)
    report['unvisited'] = queue
    (ROOT/'final.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__ == '__main__':
    asyncio.run(main())
