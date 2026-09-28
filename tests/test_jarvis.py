import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api import jarvis as API
from app.services import jarvis as J, refresh as R

TEAM = {'id': '2', 'name': 'Sentinels'}
CARD = {'id': '500', 'opponent': 'NRG', 'event': 'VCT', 'date': 'Sep 28, 2026', 'score': '2 : 1'}


@pytest.fixture
def cache(monkeypatch):
    values = {R.CACHE_TEAM.format(id='2'): {**TEAM, 'upcoming': [], 'results': []},
              R.CACHE_LIVE: [], R.CACHE_UPCOMING: [], R.CACHE_RESULTS: []}
    async def read(key):
        return values.get(key)
    monkeypatch.setattr(J, 'cache_get', read)
    monkeypatch.setattr(J, 'db_team', AsyncMock(return_value=None))
    # Any accidental upstream call fails the tests.
    monkeypatch.setattr(R, 'refresh_team', AsyncMock(side_effect=AssertionError('scrape')))
    return values


async def test_live_orientation_rounds_and_nulls(cache):
    cache[R.CACHE_LIVE] = [{'id': '500', 'teams': ['NRG', 'Sentinels'], 'scores': ['0', '1']}]
    cache[R.CACHE_MATCH.format(id='500')] = {'teams': [
        {'id': '1034', 'name': 'NRG', 'score': 0}, {**TEAM, 'score': 1}],
        'maps': [{'name': 'Ascent', 'rounds': [{'winner': 2}, {'winner': None}]},
                 {'name': 'Bind', 'rounds': [{'winner': None}]}]}
    body = await J.team_match('2')
    assert body['state'] == 'ok'
    m = body['match']
    assert m['state'] == 'live' and m['opponent']['id'] == '1034'
    assert m['series_score'] == {'team': 1, 'opponent': 0}
    assert m['maps'][0]['round_score'] == {'team': 1, 'opponent': 0}
    assert m['maps'][1]['round_score'] == {'team': None, 'opponent': None}


@pytest.mark.parametrize('kind,key,score', [('upcoming', 'upcoming', None), ('completed', 'results', 2)])
async def test_schedule_and_results(cache, kind, key, score):
    cache[R.CACHE_TEAM.format(id='2')][key] = [CARD]
    body = await J.team_match('2', kind=kind)
    assert body['match']['state'] == kind
    assert body['match']['series_score']['team'] == score
    assert body['match']['source_date']['display_date'] == CARD['date']
    assert body['match']['url'] == 'https://www.vlr.gg/500'
    assert body['match']['opponent']['id'] is None


async def test_empty_and_unavailable(cache):
    assert (await J.team_match('2'))['state'] == 'empty'
    cache.pop(R.CACHE_LIVE)
    assert (await J.team_match('2'))['state'] == 'unavailable'
    assert (await J.team_match('999'))['error'] == 'team_not_cached'


async def test_ambiguity(cache, monkeypatch):
    monkeypatch.setattr(J.S, 'db_team_search', AsyncMock(return_value=[TEAM, {'id': '3', 'name': 'Sentinels Academy'}]))
    b = await J.team_match(name='Sentinels')
    assert b['state'] == 'ambiguous' and len(b['candidates']) == 2
    assert b['team'] is None


async def test_partial_unknown_freshness_and_missing_priority(cache):
    cache.pop(R.CACHE_LIVE)
    cache[R.CACHE_TEAM.format(id='2')]['results'] = [CARD]
    b = await J.team_match('2')
    assert b['state'] == 'partial' and b['error'] == 'partial_data'
    assert b['freshness']['status'] == 'unknown'
    assert b['freshness']['captured_at'] is None
    assert b['match']['freshness']['age_seconds'] is None


async def test_id_conflict_and_no_fuzzy_match(cache):
    cache[R.CACHE_LIVE] = [{'id': '500', 'teams': ['Sentinels Academy', 'NRG']}]
    assert (await J.team_match('2', kind='live'))['state'] == 'empty'
    cache[R.CACHE_LIVE][0]['teams'][0] = 'Sentinels'
    cache[R.CACHE_MATCH.format(id='500')] = {'teams': [{'id': '3'}, {'id': '4'}]}
    assert (await J.team_match('2'))['error'] == 'identity_conflict'


@pytest.fixture
def client(monkeypatch, tmp_path):
    token = tmp_path / 'token'
    token.write_text('test-only-credential')
    monkeypatch.setattr(API.get_settings(), 'jarvis_token_file', str(token))
    redis = AsyncMock()
    redis.eval.return_value = [1, 60]
    monkeypatch.setattr(API, 'get_redis', lambda: redis)
    return TestClient(app), redis


AUTH = {'Authorization': 'Bearer test-only-credential'}
URL = '/api/v1/jarvis/team-match?team_id=2'


def test_auth_limit_and_validation(client, cache):
    c, redis = client
    assert c.get(URL).status_code == 401
    assert c.get(URL, headers={'Authorization': 'Bearer wrong'}).status_code == 401
    redis.eval.assert_not_called()
    assert c.get(URL, headers=AUTH).status_code == 200
    assert c.get('/api/v1/jarvis/team-match', headers=AUTH).status_code == 422
    assert c.get(URL + '&kind=bogus', headers=AUTH).status_code == 422
    redis.eval.return_value = [31, 20]
    r = c.get(URL, headers=AUTH)
    assert r.status_code == 429 and r.headers['retry-after'] == '20'


def test_timeout_and_storage_failure(client, monkeypatch):
    c, redis = client
    async def slow(*args):
        await asyncio.sleep(1)
    monkeypatch.setattr(API, 'REQUEST_TIMEOUT', .01)
    redis.eval.side_effect = slow
    r = c.get(URL, headers=AUTH)
    assert r.status_code == 504 and r.json()['error'] == 'timeout'
    redis.eval.side_effect = RuntimeError('secret internal details')
    r = c.get(URL, headers=AUTH)
    assert r.status_code == 503 and 'secret' not in r.text


def test_auth_unconfigured(client, monkeypatch):
    monkeypatch.setattr(API.get_settings(), 'jarvis_token_file', '/does/not/exist')
    assert client[0].get(URL, headers=AUTH).status_code == 503


async def test_conflicting_observed_state(cache):
    cache[R.CACHE_LIVE] = [{'id': '500', 'teams': ['Sentinels', 'NRG']}]
    cache[R.CACHE_MATCH.format(id='500')] = {'status': 'final'}
    assert (await J.team_match('2'))['error'] == 'state_conflict'


def test_available_scores_survive_partial_header_and_unknown_identity():
    m = J.shape(TEAM, {'id': '500', 'opponent': 'TBD', 'score': '2:1'}, 'completed',
                {'teams': [{**TEAM, 'score': None}, {'id': None, 'name': None, 'score': None}]})
    assert m['series_score'] == {'team': 2, 'opponent': 1}
    assert m['opponent'] == {'id': None, 'name': None}


async def test_id_preferred_to_ambiguous_name(cache, monkeypatch):
    search = AsyncMock(side_effect=AssertionError('name lookup'))
    monkeypatch.setattr(J.S, 'db_team_search', search)
    assert (await J.team_match('2', name='ambiguous'))['team'] == TEAM
    search.assert_not_called()
