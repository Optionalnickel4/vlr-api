import json

from app.services import team_identity as I, team_identity_store as S


class Redis:
    def __init__(self):
        self.hashes = {S.IDENTITIES: {}, S.NAMES: {}}
        self.pending = []

    def pipeline(self, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def eval(self, script, count, identities, names, tid, name, payload, replace):
        self.pending.append((tid, name, payload, replace))

    async def execute(self):
        for tid, name, payload, replace in self.pending:
            if replace == '1' or tid not in self.hashes[S.IDENTITIES]:
                self.hashes[S.IDENTITIES][tid] = payload
            old = self.hashes[S.NAMES].get(name)
            self.hashes[S.NAMES][name] = tid if old in (None, tid) else '?'
        self.pending.clear()

    async def hmget(self, key, fields):
        return [self.hashes[key].get(f) for f in fields]


async def test_logo_survives_absent_match_and_ranking_caches(monkeypatch):
    redis = Redis()
    monkeypatch.setattr(S, 'get_redis', lambda: redis)
    await S.remember([{'id': '8050', 'name': 'MIBR GC', 'logo': 'https://owcdn.net/mibr.png'}])
    async def absent(key):
        return None
    async def missing(keys):
        return [None] * len(keys)
    monkeypatch.setattr(I, 'cache_get', absent)
    monkeypatch.setattr(I, 'cache_get_many', missing)
    got = await I.enrich_match_cards([{'id': '744488', 'teams': ['MIBR GC', 'TBD'], 'scores': [3, None]}])
    assert got[0]['team_ids'] == ['8050', None]
    assert got[0]['team_logos'] == ['https://owcdn.net/mibr.png', None]
    assert got[0]['scores'] == [3, None]


async def test_missing_or_invalid_artwork_cannot_erase_observed_logo(monkeypatch):
    redis = Redis()
    monkeypatch.setattr(S, 'get_redis', lambda: redis)
    row = {'id': '1', 'name': 'Alpha', 'logo': '//owcdn.net/old.png'}
    await S.remember([row])
    await S.remember([{**row, 'logo': None}, {**row, 'logo': 'javascript:bad'}])
    by_id, _ = await S.lookup(ids=['1'])
    assert by_id['1']['logo'] == 'https://owcdn.net/old.png'
    await S.remember([{**row, 'logo': 'https://owcdn.net/new.png'}])
    by_id, _ = await S.lookup(ids=['1'])
    assert by_id['1']['logo'].endswith('new.png')
    await S.remember([row], replace=False)
    by_id, _ = await S.lookup(ids=['1'])
    assert by_id['1']['logo'].endswith('new.png')


async def test_colliding_names_do_not_guess_a_team(monkeypatch):
    redis = Redis()
    monkeypatch.setattr(S, 'get_redis', lambda: redis)
    await S.remember([{'id': '1', 'name': 'Alpha', 'logo': 'https://cdn/1.png'},
                      {'id': '2', 'name': ' ALPHA ', 'logo': 'https://cdn/2.png'}])
    by_id, by_name = await S.lookup(names=['Alpha'], ids=['1', '2'])
    assert set(by_id) == {'1', '2'}
    assert by_name == {}


async def test_retained_cache_failure_is_optional(monkeypatch):
    def fail():
        raise RuntimeError('offline')
    monkeypatch.setattr(S, 'get_redis', fail)
    await S.remember([{'id': '1', 'name': 'Alpha', 'logo': 'https://cdn/1.png'}])
    assert await S.lookup(names=['Alpha']) == ({}, {})
