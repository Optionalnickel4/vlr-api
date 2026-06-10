"""Item 3 — team-endpoint 404 handler (Bug A).

A nonexistent team id makes vlr.gg return 404; that used to surface as an
unhandled raise_for_status -> FastAPI 500. The fix: the HTTP client raises a
domain VlrNotFound on a 404 (no wasted retries), and the team route maps it to a
clean HTTP 404. No live network here — the upstream is faked.
"""
import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.http import VlrClient, VlrNotFound
from app.main import app
from app.services import refresh as R

# No `with` block: skip the app lifespan (which would touch Postgres/Redis).
client = TestClient(app)


def test_bad_id_returns_404_not_500(monkeypatch):
    """The route maps an upstream not-found to 404 (was 500)."""
    async def fake_cache_get(key):
        return None  # force the scrape-on-miss path

    async def fake_refresh_team(team_id):
        raise VlrNotFound(f"/team/{team_id}")

    monkeypatch.setattr("app.api.v1.routes.cache_get", fake_cache_get)
    monkeypatch.setattr(R, "refresh_team", fake_refresh_team)

    resp = client.get("/api/v1/team/1")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_good_id_still_returns_200(monkeypatch):
    """A real team still returns 200 with its data (no regression)."""
    async def fake_cache_get(key):
        return None

    async def fake_refresh_team(team_id):
        return {"id": team_id, "name": "Sentinels", "roster": [], "results": []}

    monkeypatch.setattr("app.api.v1.routes.cache_get", fake_cache_get)
    monkeypatch.setattr(R, "refresh_team", fake_refresh_team)

    resp = client.get("/api/v1/team/2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "2" and body["name"] == "Sentinels"


@pytest.mark.asyncio
async def test_client_raises_vlrnotfound_on_404(monkeypatch):
    """get_raw classifies a 404 as the final VlrNotFound — not a retried 5xx and
    not a generic 500-bound error."""
    c = VlrClient()
    calls = {"n": 0}

    async def fake_get(path):
        calls["n"] += 1
        req = httpx.Request("GET", "https://www.vlr.gg" + path)
        return httpx.Response(404, request=req)

    monkeypatch.setattr(c._client, "get", fake_get)
    with pytest.raises(VlrNotFound):
        await c.get_raw("/team/1")
    assert calls["n"] == 1  # 404 is final: not retried
    await c.aclose()
