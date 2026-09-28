"""Bounded direct-API follow-up; retains shapes and allowlisted facts only."""
import asyncio
import json
import time
from pathlib import Path
from urllib.parse import quote

import httpx
from scripts.probe_api import request

ROOT = Path(__file__).parent

async def main():
    selected = json.loads((ROOT / 'api.json').read_text())['selected']
    player = selected['player']['ids'][0]
    team = selected['team']['ids'][0]
    queue = ['/api/v1/status', f'/api/v1/player/{player}', f'/api/v1/team/{team}',
             f'/api/v1/trends/player/{player}',
             f'/api/v1/players/{player}/dimensions?region=na&timespan=all',
             f'/api/v1/trends/team/{team}', f'/api/v1/history/player/{player}?limit=3']
    report = {'selected': selected, 'limits': {'requests': 9, 'seconds': 480, 'deadline': 60, 'interval': 3, 'bytes': 2000000}, 'observations': []}
    end = time.monotonic() + 480
    async with httpx.AsyncClient(base_url='http://10.0.0.21:8000', trust_env=False, follow_redirects=False,
                                 headers={'User-Agent': 'VLR-API-read-only-probe/1.0'}) as client:
        while queue and len(report['observations']) < 9 and time.monotonic() < end:
            path = queue.pop(0)
            row, body = await request(client, path, min(60, end-time.monotonic()), 2000000)
            if body is not None:
                if path.endswith('/status'):
                    row['facts'] = {k: body.get(k) for k in ('commit', 'checks')}
                elif path == f'/api/v1/player/{player}':
                    row['facts'] = {'identity_present': {k: bool(body.get(k)) for k in ('alias','real_name','country','team','team_id')},
                                    'match_fields_present': [{k: bool(m.get(k)) for k in ('id','opponent','result','score','event')} for m in body.get('matches',[])[:5]],
                                    'stat_keys': list(body.get('agent_stats',[{}])[0].get('stats',{}))}
                    if body.get('alias'):
                        queue.append('/api/v1/players?q=' + quote(body['alias'], safe=''))
                elif path == f'/api/v1/team/{team}' and body.get('name'):
                    queue.append('/api/v1/teams?q=' + quote(body['name'], safe=''))
                elif '?q=' in path:
                    row['facts'] = {'ids': [r.get('id') for r in body.get('data',[])], 'sources': sorted({r.get('source','unknown') for r in body.get('data',[])})}
            report['observations'].append(row)
            print(json.dumps(row), flush=True)
            if row.get('failure') in ('timeout','transport') or row['status'] == 429 or 'retry-after' in row['headers']:
                break
            if queue:
                await asyncio.sleep(3)
    report['unvisited'] = queue
    (ROOT/'followup.json').write_text(json.dumps(report, indent=2)+'\n')

if __name__ == '__main__':
    asyncio.run(main())
