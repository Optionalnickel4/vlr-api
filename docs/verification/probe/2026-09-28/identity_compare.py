"""One prior-evidence ID as a control; no cache writes outside normal API GET."""
import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import httpx
from selectolax.parser import HTMLParser
from scripts.probe_api import request
from app.core.http import get_client, aclose_client
from app.scrapers.players import parse_player

KEYS = ('alias','real_name','country','team','team_id')

async def main():
    report = {'player_id': '3799', 'selection': 'September 27 comparator, not current first listing ID'}
    async with httpx.AsyncClient(base_url='http://10.0.0.21:8000',trust_env=False,follow_redirects=False) as c:
        row, body = await request(c, '/api/v1/player/3799', 60, 2000000)
        if body:
            row['identity_present'] = {k: bool(body.get(k)) for k in KEYS}
        report['api'] = row
    if row.get('failure') or row['status'] == 429 or 'retry-after' in row['headers']:
        return
    await asyncio.sleep(3)
    c = get_client()
    start = time.monotonic()
    upstream = {'url': 'https://www.vlr.gg/player/3799/?timespan=all', 'started': datetime.now(timezone.utc).isoformat()}
    try:
        async with asyncio.timeout(45):
            await c._throttle()
            async with c._client.stream('GET', '/player/3799/?timespan=all', follow_redirects=False) as r:
                upstream['status'] = r.status_code
                raw = bytearray()
                async for chunk in r.aiter_bytes():
                    if len(raw) + len(chunk) > 2000000:
                        raise RuntimeError('body_limit')
                    raw.extend(chunk)
                upstream['bytes'] = len(raw)
                if r.is_success:
                    html = raw.decode()
                    parsed = parse_player(html)
                    upstream['identity_present'] = {k: bool(parsed.get(k)) for k in KEYS}
                    tree = HTMLParser(html)
                    upstream['real_name_element_present'] = bool(tree.css('h2.player-real-name'))
                    upstream['current_teams_heading_present'] = any(n.text().strip() == 'Current Teams' for n in tree.css('h2.wf-label'))
    finally:
        await aclose_client()
    upstream['elapsed_ms'] = round((time.monotonic()-start)*1000,1)
    report['upstream'] = upstream
    (Path(__file__).parent/'identity-compare.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))

if __name__ == '__main__':
    asyncio.run(main())
