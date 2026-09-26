"""Retention/coalescing integration tests against a PRIVATE Unix-socket Redis.

No TCP listener, external network, production Redis, VLR, or Postgres is used.
Skip this module if redis-server is unavailable; the normal suite stays portable.
"""
import asyncio
import json
import shutil
import subprocess
import sys
import time
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import redis.asyncio as redis

from app.core import cache as C
from app.main import app
from app.services import refresh as R


@pytest.fixture(scope="module")
def redis_socket(tmp_path_factory):
    binary = shutil.which("redis-server")
    if binary is None:
        pytest.skip("redis-server needed for isolated cache integration tests")
    directory = tmp_path_factory.mktemp("cache-redis")
    socket = directory / "redis.sock"
    with (directory / "redis.log").open("w+") as log:
        process = subprocess.Popen(
            [binary, "--port", "0", "--unixsocket", str(socket),
             "--unixsocketperm", "700", "--save", "", "--appendonly", "no",
             "--dir", str(directory)], stdout=log, stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + 5
            while not socket.exists():
                if process.poll() is not None or time.monotonic() >= deadline:
                    log.seek(0)
                    pytest.fail(f"Private Redis did not start: {log.read()}")
                time.sleep(0.01)
            yield str(socket)
        finally:
            process.terminate()
            process.wait(timeout=5)


@pytest.fixture
async def store(redis_socket, monkeypatch):
    client = redis.Redis(unix_socket_path=redis_socket, decode_responses=True)
    await client.flushdb()  # exclusively the temporary server above
    monkeypatch.setattr(C, "get_redis", lambda: client)
    yield client
    await client.aclose()


@pytest.fixture
async def api():
    # ASGITransport does not run lifespan: no production DB/scheduler startup.
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


@pytest.fixture(params=["events", "rankings"])
def dataset(request, monkeypatch):
    if request.param == "events":
        key, path, module, name = R.CACHE_EVENTS, "/events", R.ev, "fetch_events"
    else:
        key, path, module, name = (
            R.CACHE_RANKINGS.format(region="all"), "/rankings", R.rk, "fetch_rankings"
        )
    # No named ranking rows => no DB writes; payload still exercises bare JSON.
    rows = [{"team": None, "id": "1", "rank": "1"}]
    fetch = AsyncMock(return_value=rows)
    monkeypatch.setattr(module, name, fetch)
    return key, "/api/v1" + path, rows, fetch


async def seed_stale(store, key, rows):
    await C.refresh_retained(key, 60, AsyncMock(return_value=rows))
    # Expire only the freshness key, as Redis would when its TTL elapses.
    await store.pexpire(key, 1)
    await asyncio.sleep(0.01)
    assert await C.cache_get(key) is None


async def test_fresh_data_never_scrapes(store, api, dataset):
    key, path, rows, fetch = dataset
    await C.cache_set(key, rows, 60)  # also proves compatibility with legacy keys
    response = await api.get(path)
    assert response.status_code == 200 and response.json() == rows
    assert response.headers["X-VLR-Cache"] == "fresh"
    assert response.headers["Cache-Control"] == "no-store"
    fetch.assert_not_awaited()


async def test_success_publishes_fresh_and_retained_payload(store, api, dataset):
    key, path, rows, fetch = dataset
    response = await api.get(path)
    assert response.status_code == 200 and response.json() == rows
    assert response.headers["X-VLR-Cache"] == "fresh"
    assert await C.cache_get(key) == rows
    assert await C.cache_get(key + ":retained") == rows
    assert await store.ttl(key) > 0
    assert await store.ttl(key + ":retained") == -1
    fetch.assert_awaited_once()


async def test_stale_refresh_failure_keeps_last_payload_and_backs_off(store, api, dataset):
    key, path, rows, fetch = dataset
    await seed_stale(store, key, rows)
    fetch.side_effect = RuntimeError("upstream unavailable")
    for _ in range(2):
        response = await api.get(path)
        assert response.status_code == 200 and response.json() == rows
        assert response.headers["X-VLR-Cache"] == "stale"
    assert await C.cache_get(key) is None  # stale is not relabelled fresh
    assert await C.cache_get(key + ":retained") == rows
    fetch.assert_awaited_once()


async def test_stale_success_replaces_both_copies(store, api, dataset):
    key, path, rows, fetch = dataset
    await seed_stale(store, key, [{"old": True}])
    response = await api.get(path)
    assert response.json() == [{"old": True}]
    assert response.headers["X-VLR-Cache"] == "stale"
    # ASGITransport waits for background completion; the actual response was
    # sent before that work (proved by the ASGI send-boundary test below).
    assert await C.cache_get(key + ":retained") == rows
    fetch.assert_awaited_once()
    response = await api.get(path)
    assert response.json() == rows and response.headers["X-VLR-Cache"] == "fresh"


async def test_cold_failure_is_503_not_fabricated_empty_list(store, api, dataset):
    key, path, _, fetch = dataset
    fetch.side_effect = RuntimeError("private upstream detail")
    responses = await asyncio.gather(*(api.get(path) for _ in range(8)))
    assert all(r.status_code == 503 for r in responses)
    assert all(r.json() == {"detail": "Data temporarily unavailable"} for r in responses)
    assert all(r.headers["Cache-Control"] == "no-store" for r in responses)
    assert all("X-VLR-Cache" not in r.headers for r in responses)
    assert await C.cache_get(key + ":retained") is None
    fetch.assert_awaited_once()


async def test_successful_empty_list_is_valid_and_retained(store, api, dataset):
    key, path, _, fetch = dataset
    fetch.return_value = []
    assert (await api.get(path)).json() == []
    await store.delete(key)
    fetch.side_effect = RuntimeError("offline")
    response = await api.get(path)
    assert response.status_code == 200 and response.json() == []
    assert response.headers["X-VLR-Cache"] == "stale"


async def test_concurrent_cold_requests_share_one_scrape(store, api, dataset):
    _, path, rows, fetch = dataset
    started, finish = asyncio.Event(), asyncio.Event()

    async def slow(*args):
        started.set()
        await finish.wait()
        return rows

    fetch.side_effect = slow
    owner = asyncio.create_task(api.get(path))
    await asyncio.wait_for(started.wait(), 2)
    followers = [asyncio.create_task(api.get(path)) for _ in range(8)]
    await asyncio.sleep(0.05)
    finish.set()
    responses = await asyncio.wait_for(asyncio.gather(owner, *followers), 3)
    assert all(r.status_code == 200 and r.json() == rows for r in responses)
    fetch.assert_awaited_once()


async def test_stale_followers_do_not_wait_for_inflight_scrape(store, api, dataset):
    key, path, rows, fetch = dataset
    await seed_stale(store, key, rows)
    started, finish = asyncio.Event(), asyncio.Event()

    async def slow(*args):
        started.set()
        await finish.wait()
        raise RuntimeError("offline")

    fetch.side_effect = slow
    owner = asyncio.create_task(api.get(path))
    await asyncio.wait_for(started.wait(), 2)
    try:
        responses = await asyncio.wait_for(
            asyncio.gather(*(api.get(path) for _ in range(8))), 1
        )
        assert all(r.status_code == 200 and r.json() == rows for r in responses)
    finally:
        finish.set()
        await owner
    fetch.assert_awaited_once()


async def test_scheduler_and_request_share_refresh(store, api, monkeypatch):
    started, finish = asyncio.Event(), asyncio.Event()

    async def slow():
        started.set()
        await finish.wait()
        return [{"id": "event"}]

    fetch = AsyncMock(side_effect=slow)
    monkeypatch.setattr(R.ev, "fetch_events", fetch)
    job = asyncio.create_task(R.refresh_events())
    await asyncio.wait_for(started.wait(), 2)
    request = asyncio.create_task(api.get("/api/v1/events"))
    await asyncio.sleep(0.05)
    finish.set()
    count, response = await asyncio.wait_for(asyncio.gather(job, request), 3)
    assert count == 1 and response.json() == [{"id": "event"}]
    fetch.assert_awaited_once()


async def test_regions_have_independent_retention(store, api, monkeypatch):
    async def fetch(region):
        return [{"team": None, "region": region}]

    monkeypatch.setattr(R.rk, "fetch_rankings", fetch)
    for region in ("all", "europe"):
        response = await api.get(f"/api/v1/rankings?region={region}")
        assert response.json() == [{"team": None, "region": region}]
        assert await C.cache_get(f"vlr:rankings:{region}:retained") == response.json()


async def test_failed_attempt_can_retry_after_backoff(store):
    fetch = AsyncMock(side_effect=RuntimeError("offline"))
    with pytest.raises(C.RefreshUnavailable):
        await C.refresh_retained("test", 60, fetch)
    assert await store.ttl("test:refresh") > 0
    await store.pexpire("test:refresh", 1)
    await asyncio.sleep(0.01)
    rows = [{"id": "recovered"}]
    data, refreshed = await C.refresh_retained("test", 60, AsyncMock(return_value=rows))
    assert data == rows and refreshed


async def test_expired_owner_cannot_overwrite_newer_payload(store):
    async def lost_lease():
        await store.set("test:refresh", "new-owner", ex=60)
        await C.cache_set("test", [{"newer": True}], 60)
        await store.set("test:retained", '[{"newer": true}]')
        return [{"older": True}]

    with pytest.raises(C.RefreshUnavailable):
        await C.refresh_retained("test", 60, lost_lease)
    assert await C.cache_get("test:retained") == [{"newer": True}]
    assert await store.get("test:refresh") == "new-owner"


async def test_cancelled_owner_leaves_retained_data_and_expiring_backoff(store):
    await seed_stale(store, "test", [{"old": True}])
    started = asyncio.Event()

    async def blocked():
        started.set()
        await asyncio.Event().wait()

    task = asyncio.create_task(C.refresh_retained("test", 60, blocked))
    await asyncio.wait_for(started.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert await C.cache_get("test:retained") == [{"old": True}]
    assert await store.ttl("test:refresh") > 0


async def test_timeout_preserves_retained_data(store, monkeypatch):
    await seed_stale(store, "test", [{"old": True}])
    monkeypatch.setattr(C, "REFRESH_TIMEOUT", 0.02)

    async def blocked():
        await asyncio.Event().wait()

    with pytest.raises(C.RefreshUnavailable):
        await C.refresh_retained("test", 60, blocked)
    assert await C.cache_get("test:retained") == [{"old": True}]
    assert await C.cache_get("test") is None
    assert await store.get("test:refresh") == "failed"


async def test_cold_follower_timeout_does_not_start_scrape(store, monkeypatch):
    monkeypatch.setattr(C, "REFRESH_TIMEOUT", 0.02)
    await store.set("test:refresh", "other-process", ex=60)
    fetch = AsyncMock(return_value=[])
    with pytest.raises(C.RefreshUnavailable):
        await C.refresh_retained("test", 60, fetch)
    fetch.assert_not_awaited()
    assert await store.get("test:refresh") == "other-process"


async def test_invalid_result_does_not_replace_retained_payload(store):
    await seed_stale(store, "test", [{"old": True}])
    with pytest.raises(C.RefreshUnavailable):
        await C.refresh_retained("test", 60, AsyncMock(return_value=None))
    assert await C.cache_get("test:retained") == [{"old": True}]


async def test_refresh_without_payload_is_explicitly_unavailable(store, api, monkeypatch):
    monkeypatch.setattr(R, "refresh_events", AsyncMock(return_value=0))
    response = await api.get("/api/v1/events")
    assert response.status_code == 503


async def test_rankings_history_is_written_only_by_scraping_owner(store, monkeypatch):
    row = {"team_id": "1", "team": "Test", "rank": "1", "rating": "1000", "record": None}
    fetch = AsyncMock(return_value=[row])
    monkeypatch.setattr(R.rk, "fetch_rankings", fetch)
    session = MagicMock()
    session.commit = AsyncMock()
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=session)
    context.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(R, "SessionLocal", lambda: context)
    counts = await asyncio.gather(*(R.refresh_rankings("europe") for _ in range(8)))
    assert counts == [1] * 8
    fetch.assert_awaited_once_with("europe")
    session.add_all.assert_called_once()
    session.commit.assert_awaited_once()
    snapshot = session.add_all.call_args.args[0][0]
    assert snapshot.team_id == "1" and snapshot.region == "europe"


async def test_rankings_db_failure_does_not_erase_published_data(store, api, monkeypatch):
    rows = [{"team_id": "1", "team": "Test", "rank": "1", "rating": "1000", "record": None}]
    monkeypatch.setattr(R.rk, "fetch_rankings", AsyncMock(return_value=rows))
    context = MagicMock()
    context.__aenter__ = AsyncMock(side_effect=RuntimeError("database offline"))
    context.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr(R, "SessionLocal", lambda: context)
    response = await api.get("/api/v1/rankings")
    assert response.status_code == 200 and response.json() == rows
    assert await C.cache_get("vlr:rankings:all:retained") == rows


async def test_redis_failure_is_not_treated_as_empty_success(api, monkeypatch):
    broken = MagicMock()
    broken.get = AsyncMock(side_effect=redis.ConnectionError("Redis unavailable"))
    monkeypatch.setattr(C, "get_redis", lambda: broken)
    with pytest.raises(redis.ConnectionError):
        await api.get("/api/v1/events")


@pytest.mark.parametrize("fails", [False, True])
async def test_stale_owner_sends_body_before_refresh_finishes(store, dataset, fails):
    """Observe ASGI sends, not httpx's background-waiting in-process transport."""
    key, path, rows, fetch = dataset
    await seed_stale(store, key, rows)
    started, finish, sent = asyncio.Event(), asyncio.Event(), asyncio.Event()
    messages = []

    async def slow(*args):
        started.set()
        await finish.wait()
        if fails:
            raise RuntimeError("upstream offline")
        return [{"team": None, "id": "new"}]

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)
        if message["type"] == "http.response.body" and not message.get("more_body", False):
            sent.set()

    fetch.side_effect = slow
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "GET", "scheme": "http", "path": path,
        "raw_path": path.encode(), "query_string": b"", "root_path": "",
        "headers": [], "server": ("test", 80), "client": ("test", 123),
    }
    request = asyncio.create_task(app(scope, receive, send))
    try:
        await asyncio.wait_for(sent.wait(), 1)
        await asyncio.wait_for(started.wait(), 1)
        assert not finish.is_set()
        assert not request.done()  # server still owns/awaits background work
        start = next(m for m in messages if m["type"] == "http.response.start")
        assert start["status"] == 200
        assert dict(start["headers"])[b"x-vlr-cache"] == b"stale"
        body = b"".join(m.get("body", b"") for m in messages)
        assert json.loads(body) == rows
        assert await store.get(key + ":refresh") not in (None, "failed")
    finally:
        finish.set()
        await asyncio.wait_for(request, 2)
    fetch.assert_awaited_once()
    if fails:
        assert await C.cache_get(key + ":retained") == rows
        assert await store.get(key + ":refresh") == "failed"
    else:
        assert await C.cache_get(key) == [{"team": None, "id": "new"}]


async def test_scheduler_process_and_stale_api_requests_share_lease(
    store, redis_socket, api, monkeypatch,
):
    """A separate scheduler process owns the real Redis lease, not a local lock."""
    rows = [{"id": "old"}]
    await seed_stale(store, R.CACHE_EVENTS, rows)
    local_fetch = AsyncMock(side_effect=AssertionError("API must not scrape"))
    monkeypatch.setattr(R.ev, "fetch_events", local_fetch)
    script = """
import asyncio, sys
import redis.asyncio as redis
from app.core import cache as C
from app.services import refresh as R

async def main():
    client = redis.Redis(unix_socket_path=sys.argv[1], decode_responses=True)
    C.get_redis = lambda: client
    async def fetch():
        await client.incr('test:scrapes')
        while not await client.get('test:finish'):
            await asyncio.sleep(0.01)
        return [{'id': 'new'}]
    R.ev.fetch_events = fetch
    try:
        await R.refresh_events()
    finally:
        await client.aclose()
asyncio.run(main())
"""
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-c", script, redis_socket,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        async with asyncio.timeout(5):
            while not await store.get("test:scrapes"):
                await asyncio.sleep(0.01)
        responses = await asyncio.wait_for(
            asyncio.gather(*(api.get("/api/v1/events") for _ in range(8))), 1,
        )
        assert all(r.json() == rows and r.headers["X-VLR-Cache"] == "stale" for r in responses)
        local_fetch.assert_not_awaited()
        assert await store.get("test:scrapes") == "1"
    finally:
        await store.set("test:finish", "1")
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), 5)
        except TimeoutError:
            process.kill()
            await process.communicate()
            raise
    assert process.returncode == 0, (stdout + stderr).decode()
    response = await api.get("/api/v1/events")
    assert response.json() == [{"id": "new"}]
    assert response.headers["X-VLR-Cache"] == "fresh"


async def test_background_unexpected_error_does_not_break_stale_response(store, api, monkeypatch):
    await seed_stale(store, R.CACHE_EVENTS, [])
    monkeypatch.setattr(R, "refresh_events", AsyncMock(side_effect=RuntimeError("failure")))
    response = await api.get("/api/v1/events")
    assert response.status_code == 200 and response.json() == []
    assert response.headers["X-VLR-Cache"] == "stale"
