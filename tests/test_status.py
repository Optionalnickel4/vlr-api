"""Phase 6 status dashboard — read-only, mocked db+cache, no network, no live PG/Redis.

The TestClient is built WITHOUT a `with` block on purpose: that skips the app
lifespan (which would call init_db() and touch Postgres). All db/cache access in
the status route goes through patchable module-level helpers, faked here.
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.cache import record_job_run
from app.main import app
from app import status_meta as meta

client = TestClient(app)

ISO = "2026-06-09T00:00:00+00:00"


def _patch_healthy(monkeypatch):
    """Fake a fully-up backend: db + redis reachable, every helper returns canned data."""
    async def fake_check_db():
        return True

    async def fake_count_and_newest(model, ts_col):
        return 7, ISO

    async def fake_ping():
        return True

    async def fake_cache_ttl(key):
        return 123

    async def fake_get_last_run(job):
        return ISO

    monkeypatch.setattr("app.core.db.check_db", fake_check_db)
    monkeypatch.setattr("app.core.db.count_and_newest", fake_count_and_newest)
    monkeypatch.setattr("app.core.cache.ping", fake_ping)
    monkeypatch.setattr("app.core.cache.cache_ttl", fake_cache_ttl)
    monkeypatch.setattr("app.core.cache.get_last_run", fake_get_last_run)
    # scheduler not running in this process -> next_run is null, last_run still resolves
    monkeypatch.setattr("app.jobs.scheduler.get_scheduler", lambda: None)


# ---- JSON shape -------------------------------------------------------------
def test_status_json_shape(monkeypatch):
    _patch_healthy(monkeypatch)
    r = client.get("/api/v1/status")
    assert r.status_code == 200
    body = r.json()

    assert body["service"] == "vlr-api"
    assert body["commit"] == meta.COMMIT
    # deploy is resolved at process start from the serving machine, not committed
    assert set(body["deploy"]) == {"hostname"}
    assert body["deploy"]["hostname"] and isinstance(body["deploy"]["hostname"], str)
    assert body["checks"] == {"postgres": True, "redis": True}

    # history: one row per known table, in order, each with table/rows/newest
    tables = [h["table"] for h in body["history"]]
    assert tables == meta.HISTORY_TABLES
    for h in body["history"]:
        assert set(h) == {"table", "rows", "newest"}
        assert h["rows"] == 7 and h["newest"] == ISO

    # cache_keys: the fixed league-wide namespaced keys only, name + ttl (never a value)
    keys = [c["key"] for c in body["cache_keys"]]
    assert keys == [
        "vlr:results", "vlr:upcoming", "vlr:live",
        "vlr:rankings:all", "vlr:events", "vlr:news",
    ]
    for c in body["cache_keys"]:
        assert set(c) == {"key", "ttl"}
        assert c["ttl"] == 123

    # scheduler: one entry per registered job, last from redis, next null (not running)
    jobs = [s["job"] for s in body["scheduler"]]
    assert jobs == [
        "upcoming", "live_matches", "results", "news", "events", "rankings", "player_prefetch", "stats",
    ]
    for s in body["scheduler"]:
        assert set(s) == {"job", "last_run", "next_run"}
        assert s["last_run"] == ISO
        assert s["next_run"] is None


# ---- one bad table must not 500 the endpoint --------------------------------
def test_status_one_table_error_is_null_not_500(monkeypatch):
    _patch_healthy(monkeypatch)

    async def flaky_count(model, ts_col):
        if model.__tablename__ == "player_snapshots":
            raise RuntimeError("table is on fire")
        return 7, ISO

    monkeypatch.setattr("app.core.db.count_and_newest", flaky_count)

    r = client.get("/api/v1/status")
    assert r.status_code == 200
    body = r.json()
    bad = next(h for h in body["history"] if h["table"] == "player_snapshots")
    assert bad["rows"] is None and bad["newest"] is None
    # a failed table flips the postgres check, but the endpoint still answers
    assert body["checks"]["postgres"] is False


# ---- redis down -------------------------------------------------------------
def test_status_redis_down(monkeypatch):
    _patch_healthy(monkeypatch)

    async def fake_ping():
        return False

    monkeypatch.setattr("app.core.cache.ping", fake_ping)

    r = client.get("/api/v1/status")
    assert r.status_code == 200
    assert r.json()["checks"]["redis"] is False


# ---- record_job_run writes lastrun with no TTL ------------------------------
class FakeRedis:
    def __init__(self):
        self.store: dict = {}
        self.ex: dict = {}

    async def set(self, key, value, ex=None):
        self.store[key] = value
        self.ex[key] = ex


@pytest.mark.asyncio
async def test_record_job_run_writes_iso_no_ttl(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr("app.core.cache.get_redis", lambda: fake)

    await record_job_run("results")

    assert "vlr:lastrun:results" in fake.store
    # parseable ISO-8601
    parsed = datetime.fromisoformat(fake.store["vlr:lastrun:results"])
    assert parsed.tzinfo is not None
    # no TTL — must survive to be read later
    assert fake.ex["vlr:lastrun:results"] is None


# ---- read-only invariant: status route triggers NO scrape/refresh -----------
def test_status_route_never_refreshes(monkeypatch):
    _patch_healthy(monkeypatch)

    from unittest.mock import AsyncMock

    spies = {}
    for name in (
        "refresh_results", "refresh_upcoming", "refresh_rankings",
        "refresh_events", "refresh_news", "refresh_player", "refresh_team",
    ):
        spy = AsyncMock()
        spies[name] = spy
        monkeypatch.setattr(f"app.services.refresh.{name}", spy)

    r = client.get("/api/v1/status")
    assert r.status_code == 200
    for name, spy in spies.items():
        spy.assert_not_called()


# ---- HTML smoke -------------------------------------------------------------
def test_status_html_renders_static_half():
    r = client.get("/status")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    body = r.text
    assert "vlr-api" in body
    # static phase names render server-side (works with JS off)
    for phase in meta.PHASES:
        assert phase["name"] in body
