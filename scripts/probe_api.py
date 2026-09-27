#!/usr/bin/env python3
"""Sequential GET-only VLR API observations; never retain response bodies."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

import httpx

HEADERS = ('date', 'age', 'cache-control', 'expires', 'last-modified', 'etag',
           'x-vlr-cache', 'retry-after', 'content-type')
LISTINGS = ('/matches/results', '/matches/upcoming', '/matches/live', '/rankings',
            '/stats?region=na&timespan=all', '/news', '/events', '/teams', '/players')


def shape(value, depth=0):
    """Types/counts only, capped breadth/depth. Never include scalar values."""
    if isinstance(value, list):
        return {'type': 'array', 'count': len(value),
                'item': shape(value[0], depth + 1) if value and depth < 2 else None}
    if isinstance(value, dict):
        return {'type': 'object', 'fields': {
            k: shape(v, depth + 1) if depth < 2 else type(v).__name__
            for k, v in list(value.items())[:40]}}
    return {'type': type(value).__name__}


def summarize(value):
    envelope = isinstance(value, dict) and 'data' in value
    data = value['data'] if envelope else value
    error = bool(value.get('error')) if isinstance(value, dict) else False
    return {'shape': shape(value),
            'state': 'unavailable' if error and not data else 'populated' if data else 'empty',
            'stale': value.get('stale') is True if envelope else None,
            'error_present': error}


def select_ids(value, field, limit):
    rows = value.get('data', []) if isinstance(value, dict) else value
    if not isinstance(rows, list):
        return []
    if limit <= 0:
        return []
    ids = []
    for row in rows:
        raw = row.get(field) if isinstance(row, dict) else None
        identifier = str(raw)
        if re.fullmatch(r'[0-9]{1,12}', identifier) and identifier not in ids:
            ids.append(identifier)
        if len(ids) >= limit:
            break
    return ids[:limit]


async def request(client, path, deadline, max_bytes):
    started = time.monotonic()
    row = {'path': path, 'started': datetime.now(timezone.utc).isoformat(),
           'status': None, 'state': 'unavailable', 'headers': {}}
    value = None
    try:
        async with asyncio.timeout(deadline):
            async with client.stream('GET', path) as response:
                row.update(status=response.status_code, headers={
                    k: response.headers[k][:256] for k in HEADERS if k in response.headers})
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(body) + len(chunk) > max_bytes:
                        row['failure'] = 'body_limit'
                        break
                    body.extend(chunk)
                else:
                    row['bytes'] = len(body)
                    try:
                        value = json.loads(body)
                        row.update(summarize(value))
                    except (ValueError, UnicodeError):
                        row['failure'] = 'non_json'
                if not response.is_success:
                    row.update(state='unavailable', failure='http_status')
                    value = None
    except (TimeoutError, httpx.TimeoutException):
        row['failure'] = 'timeout'
    except httpx.HTTPError:
        # Exception text can include credentials, URLs or payload fragments.
        row['failure'] = 'transport'
    row['elapsed_ms'] = round((time.monotonic() - started) * 1000, 1)
    return row, value


async def probe(args):
    report = {'base_url': args.base_url, 'started': datetime.now(timezone.utc).isoformat(),
              'limits': {k: getattr(args, k) for k in
                         ('deadline', 'interval', 'max_requests', 'max_seconds', 'max_bytes', 'details')},
              'selected': {}, 'observations': [], 'stop_reason': 'complete'}
    queue = ['/health', '/api/v1/status'] + ['/api/v1' + p for p in LISTINGS]
    end = time.monotonic() + args.max_seconds
    async with httpx.AsyncClient(base_url=args.base_url, follow_redirects=False,
                                 trust_env=False, timeout=args.deadline,
                                 headers={'Accept': 'application/json',
                                          'User-Agent': 'VLR-API-read-only-probe/1.0'}) as client:
        while queue:
            if len(report['observations']) >= args.max_requests:
                report['stop_reason'] = 'request_limit'
                break
            if report['observations']:
                await asyncio.sleep(min(args.interval, max(0, end - time.monotonic())))
            remaining = end - time.monotonic()
            if remaining <= 0:
                report['stop_reason'] = 'time_limit'
                break
            path = queue.pop(0)
            row, value = await request(client, path, min(args.deadline, remaining), args.max_bytes)
            report['observations'].append(row)
            print(json.dumps({k: row.get(k) for k in
                              ('path', 'status', 'state', 'elapsed_ms', 'failure')}), flush=True)
            for source, kind, field in [('/matches/results', 'match', 'id'),
                                        ('/rankings', 'team', 'team_id'),
                                        ('/stats?region=na&timespan=all', 'player', 'player_id')]:
                if path == '/api/v1' + source:
                    ids = select_ids(value, field, args.details)
                    report['selected'][kind] = {'source': path, 'ids': ids}
                    queue.extend(f'/api/v1/{kind}/{identifier}' for identifier in ids)
            # Cancellation does not guarantee the server stopped a scrape. End the
            # pass instead of adding pressure. Retry-After always ends the pass.
            if row.get('failure') in ('timeout', 'transport') or row['status'] == 429 or 'retry-after' in row['headers']:
                report['stop_reason'] = 'server_backoff_or_transport'
                break
    report['unvisited'] = queue
    report['finished'] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    return report


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://10.0.0.21:8000')
    parser.add_argument('--output', type=Path, default=Path('probe-report.json'))
    parser.add_argument('--deadline', type=float, default=90)
    parser.add_argument('--interval', type=float, default=2)
    parser.add_argument('--max-requests', type=int, default=14)
    parser.add_argument('--max-seconds', type=float, default=600)
    parser.add_argument('--max-bytes', type=int, default=2_000_000)
    parser.add_argument('--details', type=int, default=1)
    args = parser.parse_args()
    url = urlsplit(args.base_url)
    if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ('', '/'):
        parser.error('--base-url must be an HTTP(S) origin without credentials/query/path')
    for key, low, high in [('deadline', .01, 120), ('interval', 1.5, 60),
                           ('max_requests', 1, 30), ('max_seconds', 1, 1800),
                           ('max_bytes', 1, 5_000_000), ('details', 0, 3)]:
        value = getattr(args, key)
        if not math.isfinite(value) or not low <= value <= high:
            parser.error(f'{key} must be between {low} and {high}')
    return args


if __name__ == '__main__':
    result = asyncio.run(probe(arguments()))
    raise SystemExit(1 if result['stop_reason'] != 'complete' or any(
        r['state'] == 'unavailable' for r in result['observations']) else 0)
