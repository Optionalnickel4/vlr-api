"""Preview adapter regression tests: isolated HTTPX/Redis/DB fixtures only."""
import asyncio
import json
import time
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from scripts import preview_api as preview
from app.ratings.dimensions import compute_dimensions


@pytest.fixture
async def api(monkeypatch):
    # Catch any accidental introduction of refresh paths in the adapter.
    from app.services import refresh
    refresh_calls=[]
    for name in dir(refresh):
        if name.startswith('refresh_'):
            spy=AsyncMock(side_effect=AssertionError('preview must not refresh'))
            refresh_calls.append(spy)
            monkeypatch.setattr(refresh, name, spy)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=preview.app), base_url='http://fixture') as client:
        yield client
    for spy in refresh_calls:
        spy.assert_not_awaited()


@pytest.mark.parametrize('region', ['na','eu'])
async def test_dimensions_match_pure_api_computation(api, monkeypatch, region):
    cohort = [{'player_id':'42','acs':100,'rnd':100}, {'player_id':'43','acs':200,'rnd':200}]
    redis = SimpleNamespace(get=AsyncMock(return_value=json.dumps(cohort)))
    monkeypatch.setattr(preview, 'get_redis', lambda:redis)
    r=await api.get(f'/api/v1/players/42/dimensions?region={region}')
    assert r.status_code == 200
    assert r.json() == {'player_id':'42','region':region,'timespan':'all', **compute_dimensions(cohort[0],cohort)}
    redis.get.assert_awaited_once_with(f'vlr:stats:{region}:all')


@pytest.mark.parametrize('raw,status', [(None,503),('[]',503),('[{"player_id":"43"}]',404),('invalid',503)])
async def test_missing_cohort_is_unavailable_missing_member_is_not_found(api,monkeypatch,raw,status):
    monkeypatch.setattr(preview,'get_redis',lambda:SimpleNamespace(get=AsyncMock(return_value=raw)))
    r=await api.get('/api/v1/players/42/dimensions')
    assert r.status_code == status


@pytest.mark.parametrize('path,status', [
    ('/players/42/dimensions?region=ap',400),
    ('/players/42/dimensions?timespan=invalid',400),
    ('/players/not-an-id/dimensions',422),
    ('/trends/player/42?days=0',422),
    ('/trends/player/42?days=366',422),
])
async def test_bad_parameters_do_not_touch_storage(api,monkeypatch,path,status):
    def no_storage(): raise AssertionError('invalid request touched storage')
    monkeypatch.setattr(preview,'get_redis',no_storage)
    monkeypatch.setattr(preview,'SessionLocal',no_storage)
    assert (await api.get('/api/v1'+path)).status_code == status


def fake_session(monkeypatch, snapshots):
    session=MagicMock()
    session.execute=AsyncMock(return_value=MagicMock(scalars=lambda:SimpleNamespace(all=lambda:snapshots)))
    session.__aenter__=AsyncMock(return_value=session)
    session.__aexit__=AsyncMock(return_value=False)
    monkeypatch.setattr(preview,'SessionLocal',lambda:session)
    return session


@pytest.mark.parametrize('kind', ['rated','unrated','missing'])
async def test_history_preserves_empty_thin_and_absent_semantics(api,monkeypatch,kind):
    snapshots=[] if kind=='missing' else [SimpleNamespace(
        captured_at=datetime.now(timezone.utc),alias='Fixture',team=None,
        agent_stats=[{'agent':'sova','stats':{'R':'1.5' if kind=='rated' else '–','Rnd':'100','ACS':'200'}}])]
    session=fake_session(monkeypatch,snapshots)
    r=await api.get('/api/v1/trends/player/42?days=90')
    assert str(session.execute.call_args_list[0].args[0])=='SET TRANSACTION READ ONLY'
    assert str(session.execute.call_args_list[1].args[0]).startswith('SELECT ')
    assert session.execute.await_count == 2
    session.commit.assert_not_called()
    if kind=='missing':
        assert r.status_code==404
    else:
        assert r.status_code==200
        assert len(r.json()['rating_trend'])==(1 if kind=='rated' else 0)
        assert r.json()['rating_change'] is None


async def test_storage_failure_is_bounded_and_does_not_leak(api,monkeypatch):
    async def slow(*args): await asyncio.sleep(10)
    monkeypatch.setattr(preview,'READ_TIMEOUT_SECONDS',.01)
    monkeypatch.setattr(preview,'get_redis',lambda:SimpleNamespace(get=slow))
    start=time.monotonic()
    r=await api.get('/api/v1/players/42/dimensions')
    assert time.monotonic()-start < .5
    assert r.status_code==503
    assert 'timed out' in r.json()['detail']
    monkeypatch.setattr(preview,'get_redis',lambda:SimpleNamespace(get=AsyncMock(side_effect=RuntimeError('SECRET'))))
    r=await api.get('/api/v1/players/42/dimensions')
    assert r.status_code==503 and 'SECRET' not in r.text


async def test_player_detail_keeps_agent_stats_and_matches_verbatim(api,monkeypatch):
    body={'id':'42','agent_stats':[{'agent':'sova','stats':{'Rnd':'100','R':'1.5'}}],
          'matches':[{'id':'123','result':'win'}]}
    redis=SimpleNamespace(get=AsyncMock(return_value=json.dumps(body)))
    monkeypatch.setattr(preview,'get_redis',lambda:redis)
    r=await api.get('/api/v1/player/42')
    assert r.status_code==200 and r.json()==body
    assert (await api.post('/api/v1/player/42')).status_code==405
