"""Probe safety checks use HTTPX fixtures only; no running API is touched."""
import asyncio
import json
from types import SimpleNamespace

import httpx

from scripts.probe_api import probe, request, select_ids, summarize


async def test_report_redacts_values_and_headers():
    async def handler(req):
        assert req.method == 'GET'
        return httpx.Response(200, json={'data': [{'player_id': '42', 'alias': 'SECRET'}],
                                       'stale': True, 'error': 'SECRET'},
                              headers={'set-cookie': 'SECRET', 'x-vlr-cache': 'stale'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url='http://fixture') as client:
        row, body = await request(client, '/stats', 1, 1000)
    assert 'SECRET' not in json.dumps(row)
    assert row['state'] == 'populated' and row['stale'] and row['error_present']
    assert select_ids(body, 'player_id', 1) == ['42']
    assert summarize({'data': [], 'error': 'failure'})['state'] == 'unavailable'
    assert summarize([])['state'] == 'empty'


async def test_deadline_covers_slow_body():
    class Slow(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'['
            await asyncio.sleep(1)
            yield b']'
    async with httpx.AsyncClient(transport=httpx.MockTransport(
        lambda req: httpx.Response(200, stream=Slow())), base_url='http://fixture') as client:
        row, body = await request(client, '/', .01, 100)
    assert row['failure'] == 'timeout'
    assert row['state'] == 'unavailable'
    assert body is None


async def test_body_limit_and_redirect_are_not_followed():
    calls = []
    def handler(req):
        calls.append(str(req.url))
        return httpx.Response(302, headers={'location': 'http://other'}, content=b'x' * 100)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url='http://fixture') as client:
        row, body = await request(client, '/', 1, 10)
    assert len(calls) == 1 and body is None
    assert row['state'] == 'unavailable' and row['status'] == 302


async def test_probe_stops_on_backoff_without_retry(tmp_path, monkeypatch):
    from scripts import probe_api
    calls = []
    async def fake_request(client, path, deadline, max_bytes):
        calls.append(path)
        return {'path': path, 'status': 429, 'state': 'unavailable',
                'headers': {'retry-after': '30'}}, None
    monkeypatch.setattr(probe_api, 'request', fake_request)
    args = SimpleNamespace(base_url='http://fixture', deadline=1, interval=1.5,
                           max_requests=14, max_seconds=30, max_bytes=1000,
                           details=1, output=tmp_path / 'report.json')
    result = await probe(args)
    assert calls == ['/health']
    assert result['stop_reason'] == 'server_backoff_or_transport'
    assert result['unvisited']


def test_discovery_rejects_paths_and_limits_ids():
    assert select_ids([{'id': '../secret'}, {'id': '1'}, {'id': '1'}, {'id': '2'}], 'id', 1) == ['1']
    assert select_ids([{'id': '1'}], 'id', 0) == []


async def test_request_cap_preserves_unvisited_coverage(tmp_path, monkeypatch):
    from scripts import probe_api
    calls = []
    async def fake_request(client, path, deadline, max_bytes):
        calls.append(path)
        return {'path': path, 'status': 200, 'state': 'populated', 'headers': {}}, {'status': 'ok'}
    monkeypatch.setattr(probe_api, 'request', fake_request)
    args = SimpleNamespace(base_url='http://fixture', deadline=1, interval=1.5,
                           max_requests=1, max_seconds=30, max_bytes=1000,
                           details=1, output=tmp_path / 'report.json')
    report = await probe(args)
    assert calls == ['/health']
    assert report['stop_reason'] == 'request_limit'
    assert report['unvisited'][0] == '/api/v1/status'
