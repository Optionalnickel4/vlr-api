"""Detail deadlines/history failures. All serving and persistence I/O isolated."""
import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.api.v1 import routes
from app.main import app
from app.services import refresh as R


@pytest.fixture
async def api():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url='http://test') as client:
        yield client


@pytest.mark.parametrize('kind', ['match', 'team', 'player'])
async def test_warm_and_cold_preserve_bare_detail_body(api, monkeypatch, kind):
    body = {'id': '1', 'name': 'A', 'raw_score': '13'}
    cache = AsyncMock(return_value=body)
    refresh = AsyncMock(return_value=body)
    monkeypatch.setattr(routes, 'cache_get', cache)
    monkeypatch.setattr(R, f'refresh_{kind}', refresh)
    assert (await api.get(f'/api/v1/{kind}/1')).json() == body
    refresh.assert_not_awaited()
    cache.return_value = None
    assert (await api.get(f'/api/v1/{kind}/1')).json() == body
    refresh.assert_awaited_once_with('1')


@pytest.mark.parametrize('kind', ['match', 'team', 'player'])
@pytest.mark.parametrize('phase', ['cache', 'refresh'])
async def test_detail_total_deadline_cancels_stalled_work(api, monkeypatch, kind, phase):
    cancelled = asyncio.Event()
    async def stalled(*args):
        try:
            await asyncio.sleep(10)
        finally:
            cancelled.set()
    monkeypatch.setattr(routes, 'DETAIL_REQUEST_TIMEOUT_SECONDS', .01)
    monkeypatch.setattr(routes, 'cache_get', stalled if phase == 'cache' else AsyncMock(return_value=None))
    monkeypatch.setattr(R, f'refresh_{kind}', stalled)
    response = await api.get(f'/api/v1/{kind}/1')
    assert response.status_code == 504
    assert response.json() == {'detail': 'detail refresh timed out'}
    assert cancelled.is_set()


@pytest.mark.parametrize('kind', ['team', 'player'])
@pytest.mark.parametrize('persistence', ['success', 'failed', 'slow'])
async def test_history_cannot_discard_published_detail(api, monkeypatch, caplog, kind, persistence):
    body = {'id': '1', 'name': 'Team', 'alias': 'Player', 'results': [], 'agent_stats': []}
    cache = {}
    async def publish(key, value, ttl):
        cache[key] = value
    async def read(key):
        return cache.get(key)
    session = MagicMock()
    session.execute = AsyncMock(return_value=MagicMock(first=lambda: None))
    async def commit():
        assert cache, 'serving payload must be published before history'
        if persistence == 'failed':
            raise RuntimeError('database offline')
        if persistence == 'slow':
            await asyncio.sleep(10)
    session.commit = AsyncMock(side_effect=commit)
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=session)
    context.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(R, 'SessionLocal', lambda: context)
    monkeypatch.setattr(R, 'DETAIL_HISTORY_TIMEOUT_SECONDS', .01)
    monkeypatch.setattr(R, 'cache_set', publish)
    monkeypatch.setattr(routes, 'cache_get', read)
    scraper = R.te if kind == 'team' else R.pl
    fetch = AsyncMock(return_value=body)
    monkeypatch.setattr(scraper, f'fetch_{kind}', fetch)
    response = await api.get(f'/api/v1/{kind}/1')
    assert response.status_code == 200
    assert response.json() == body
    assert (await api.get(f'/api/v1/{kind}/1')).json() == body
    fetch.assert_awaited_once()
    session.commit.assert_awaited_once()
    if persistence != 'success':
        assert 'detail cached; history persistence failed' in caplog.text


@pytest.mark.parametrize('kind', ['match', 'team', 'player'])
async def test_scrape_failure_does_not_become_success(api, monkeypatch, kind):
    monkeypatch.setattr(routes, 'cache_get', AsyncMock(return_value=None))
    monkeypatch.setattr(R, f'refresh_{kind}', AsyncMock(side_effect=RuntimeError('upstream offline')))
    assert (await api.get(f'/api/v1/{kind}/1')).status_code == 500


async def test_external_cancellation_is_not_swallowed():
    entered = asyncio.Event()
    async def work():
        async with R._detail_history('player', '1'):
            entered.set()
            await asyncio.sleep(10)
    task = asyncio.create_task(work())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.parametrize('kind', ['match', 'team', 'player'])
async def test_upstream_not_found_has_consistent_detail_404(api, monkeypatch, kind):
    from app.core.http import VlrNotFound
    monkeypatch.setattr(routes, 'cache_get', AsyncMock(return_value=None))
    refresh = AsyncMock(side_effect=VlrNotFound(f'/{kind}/123'))
    monkeypatch.setattr(R, f'refresh_{kind}', refresh)
    response = await api.get(f'/api/v1/{kind}/123')
    assert response.status_code == 404
    assert response.json() == {'detail': f'{kind} 123 not found'}
    refresh.assert_awaited_once_with('123')
