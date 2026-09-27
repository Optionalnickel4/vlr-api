"""One selected player's layer trace, using the documented GET-only probe.

Run from repo root with PYTHONPATH=. .venv/bin/python <this file>.
Eight sequential requests, two seconds apart, no retries; no raw payload output.
"""
import argparse
import asyncio
import json
from pathlib import Path

import httpx

from scripts.probe_api import request


def features(body):
    if not isinstance(body, dict):
        return {}
    data = body.get('data', body)
    if isinstance(data, list):
        data = data[0] if data else {}
    if not isinstance(data, dict):
        return {}
    agents = data.get('agent_stats', data.get('agentStats', []))
    matches = data.get('matches', [])
    trend = data.get('rating_trend', data.get('ratingTrend', []))
    return {'agent_rows': len(agents), 'match_rows': len(matches),
            'rated_points': len(trend),
            'dimension_fields': [k for k in ('firepower','entry','consistency','clutch')
                                 if isinstance(data.get(k), (int,float))],
            'agent_stat_keys': list(agents[0].get('stats', {})) if agents else []}


async def main(args):
    rows = []
    paths = [f'/player/{args.player_id}', f'/trends/player/{args.player_id}?days=90',
             f'/players/{args.player_id}/dimensions?region=na&timespan=all']
    # This frontend uses a server-only dimensions loader, with no dimensions proxy.
    targets = [] if args.skip_backend else [(args.api, '/api/v1'+p, 'backend') for p in paths]
    targets += [(args.adapter, '/api/v1'+p, 'adapter') for p in paths]
    targets += [(args.frontend, '/api'+p, 'proxy') for p in paths[:2]]
    async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as client:
        for base,path,layer in targets:
            row, body = await request(client, base+path, 90, 2_000_000)
            row.update(layer=layer, path=path, features=features(body))
            rows.append(row)
            print(json.dumps({k:row.get(k) for k in ('layer','path','status','state','elapsed_ms','features')}),flush=True)
            if row.get('failure') in ('timeout','transport') or row['status']==429 or 'retry-after' in row['headers']:
                break
            await asyncio.sleep(2)
    args.output.write_text(json.dumps({'player_id':args.player_id,'observations':rows},indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--player-id',default='3799',choices=['3799'])
    p.add_argument('--skip-backend',action='store_true')
    p.add_argument('--api',default='http://10.0.0.21:8000')
    p.add_argument('--adapter',default='http://127.0.0.1:8101')
    p.add_argument('--frontend',default='http://10.0.0.21:3100')
    p.add_argument('--output',type=Path,default=Path('docs/verification/player-analytics/2026-09-27/before.json'))
    asyncio.run(main(p.parse_args()))
