"""Retain source-observed team artwork independently of match freshness."""
import json
from urllib.parse import urlsplit

from app.core.cache import get_redis

IDENTITIES = 'vlr:identity:teams'
NAMES = 'vlr:identity:team-names'


def name_key(value):
    return ' '.join(str(value or '').split()).casefold()


def identity(row, ranking=False):
    tid = str(row.get('team_id' if ranking else 'id') or '')
    name = row.get('team' if ranking else 'name')
    logo = row.get('logo')
    if isinstance(logo, str) and logo.startswith('//'):
        logo = 'https:' + logo
    try:
        url = urlsplit(logo) if isinstance(logo, str) else None
        valid = url and url.scheme in ('http', 'https') and url.hostname and not url.username and not url.password
    except ValueError:
        valid = False
    if not tid.isdecimal() or not name_key(name) or not valid:
        return None
    return {'id': tid, 'name': str(name), 'logo': logo, 'short_name': row.get('tag')}


_REMEMBER = """
if ARGV[4] == '1' or redis.call('HEXISTS', KEYS[1], ARGV[1]) == 0 then
  redis.call('HSET', KEYS[1], ARGV[1], ARGV[3])
end
local old = redis.call('HGET', KEYS[2], ARGV[2])
if not old or old == ARGV[1] then
  redis.call('HSET', KEYS[2], ARGV[2], ARGV[1])
else
  redis.call('HSET', KEYS[2], ARGV[2], '?')
end
return 1
"""


async def remember(rows, *, ranking=False, replace=True):
    """No expiry. Missing artwork never overwrites a previously observed logo."""
    items = [item for row in rows if isinstance(row, dict)
             if (item := identity(row, ranking)) is not None]
    if not items:
        return
    try:
        async with get_redis().pipeline(transaction=False) as pipe:
            for item in items:
                pipe.eval(_REMEMBER, 2, IDENTITIES, NAMES, item['id'],
                          name_key(item['name']), json.dumps(item), '1' if replace else '0')
            await pipe.execute()
    except Exception:
        pass  # Artwork must not prevent fresh scores or fixtures from publishing.


async def lookup(names=(), ids=()):
    """Two bounded hash reads; ambiguous names are never used to infer an ID."""
    keys = list(dict.fromkeys(name_key(n) for n in names if name_key(n)))
    try:
        client = get_redis()
        matches = await client.hmget(NAMES, keys) if keys else []
        wanted = list(dict.fromkeys([str(i) for i in ids if i] + [i for i in matches if i and i != '?']))
        raw = await client.hmget(IDENTITIES, wanted) if wanted else []
        by_id = {}
        for tid, value in zip(wanted, raw):
            item = json.loads(value) if value else None
            if isinstance(item, dict) and item.get('id') == tid and identity(item):
                by_id[tid] = item
        by_name = {key: by_id[tid] for key, tid in zip(keys, matches) if tid in by_id}
        return by_id, by_name
    except Exception:
        return {}, {}
