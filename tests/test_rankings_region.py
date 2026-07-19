"""Issues #2 + #3 — /rankings region allow-list and shared-client shutdown.

#2: a bogus ?region= used to trigger an inline refresh against vlr.gg (404
upstream) on every cache miss, forever. The route now rejects unknown slugs
with a 400 before any refresh runs.

#3: the lazy shared VlrClient was never aclose()d on shutdown. aclose_client()
closes and clears it; the app lifespan and the standalone scheduler call it.
No live network here — cache and refresh are faked.
"""
import pytest
from fastapi.testclient import TestClient

from app.core import http as http_core
from app.core.http import VlrClient, aclose_client
from app.main import app
from app.services import refresh as R

# No `with` block: skip the app lifespan (which would touch Postgres/Redis).
client = TestClient(app)


def test_bogus_region_returns_400_without_refresh(monkeypatch):
    calls = {"n": 0}

    async def fake_refresh(region):
        calls["n"] += 1

    monkeypatch.setattr(R, "refresh_rankings", fake_refresh)
    resp = client.get("/api/v1/rankings?region=asia")
    assert resp.status_code == 400
    assert "region must be one of" in resp.json()["detail"]
    assert calls["n"] == 0  # rejected before any upstream refresh


def test_valid_region_reads_cache(monkeypatch):
    rows = [{"team_id": "2", "team": "Sentinels", "rank": 1}]

    async def fake_cache_get(key):
        assert key == R.CACHE_RANKINGS.format(region="north-america")
        return rows

    monkeypatch.setattr("app.api.v1.routes.cache_get", fake_cache_get)
    resp = client.get("/api/v1/rankings?region=North-America")  # case-insensitive
    assert resp.status_code == 200
    assert resp.json() == rows


def test_default_region_all_still_allowed(monkeypatch):
    async def fake_cache_get(key):
        assert key == R.CACHE_RANKINGS.format(region="all")
        return []

    monkeypatch.setattr("app.api.v1.routes.cache_get", fake_cache_get)
    assert client.get("/api/v1/rankings").status_code == 200


@pytest.mark.asyncio
async def test_aclose_client_closes_and_clears(monkeypatch):
    monkeypatch.setattr(http_core, "_client", None)
    c = http_core.get_client()
    assert isinstance(c, VlrClient)
    await aclose_client()
    assert http_core._client is None
    assert c._client.is_closed


@pytest.mark.asyncio
async def test_aclose_client_noop_when_never_created(monkeypatch):
    monkeypatch.setattr(http_core, "_client", None)
    await aclose_client()  # must not raise
    assert http_core._client is None
