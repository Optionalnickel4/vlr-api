"""Isolated HTTP/Redis check. No production keys, scheduler, schema or upstream."""
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time

import httpx
import redis


def port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def main():
    with tempfile.TemporaryDirectory(prefix='vlr-jarvis-check-') as tmp:
        root = Path(tmp)
        token = secrets.token_urlsafe(32)
        secret = root / 'token'
        secret.write_text(token)
        secret.chmod(0o600)
        redis_port, api_port = port(), port()
        processes = []
        with (root / 'process.log').open('w') as log:
            try:
                processes.append(subprocess.Popen(['redis-server', '--bind', '127.0.0.1', '--port', str(redis_port), '--save', '', '--appendonly', 'no'], stdout=log, stderr=log))
                r = redis.Redis(host='127.0.0.1', port=redis_port)
                for _ in range(100):
                    try:
                        if r.ping():
                            break
                    except redis.ConnectionError:
                        time.sleep(.05)
                r.set('vlr:team:2', json.dumps({'id': '2', 'name': 'Sentinels', 'results': [], 'upcoming': []}))
                r.set('vlr:live', json.dumps([{'id': '500', 'teams': ['Sentinels', 'NRG'], 'scores': ['1', '0']}]))
                env = {**os.environ, 'VLR_REDIS_URL': f'redis://127.0.0.1:{redis_port}/0',
                       'VLR_JARVIS_TOKEN_FILE': str(secret), 'VLR_ENABLE_SCHEDULER': 'false'}
                processes.append(subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(api_port), '--lifespan', 'off'], env=env, stdout=log, stderr=log))
                with httpx.Client(base_url=f'http://127.0.0.1:{api_port}', timeout=4) as c:
                    for _ in range(100):
                        try:
                            if c.get('/health').status_code == 200:
                                break
                        except httpx.ConnectError:
                            time.sleep(.05)
                    route = '/api/v1/jarvis/team-match?team_id=2&kind=live'
                    assert c.get(route).status_code == 401
                    headers = {'Authorization': f'Bearer {token}'}
                    start = time.monotonic()
                    result = c.get(route, headers=headers)
                    assert result.status_code == 200, result.text
                    assert result.json()['match']['series_score'] == {'team': 1, 'opponent': 0}
                    assert result.json()['freshness']['status'] == 'unknown'
                    for _ in range(29):
                        assert c.get(route, headers=headers).status_code == 200
                    limited = c.get(route, headers=headers)
                    assert limited.status_code == 429 and int(limited.headers['retry-after']) > 0
                    print(json.dumps({'check': 'isolated HTTP + real Redis', 'passed': True,
                                      'requests': 32, 'elapsed_seconds': round(time.monotonic()-start, 3),
                                      'schema_version': result.json()['schema_version'], 'state': result.json()['state']}))
            finally:
                for p in reversed(processes):
                    p.terminate()
                    p.wait(timeout=10)


if __name__ == '__main__':
    main()
