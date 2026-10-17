from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.services import predictions as P


@pytest.fixture(autouse=True)
def live_settings(monkeypatch):
    monkeypatch.setattr(P, "get_settings", lambda: Settings(_env_file=None,
        predictions_source_api_url="http://127.0.0.1:8000/api/v1"))


async def test_team_reads_live_api_not_preview_cache(monkeypatch):
    api = AsyncMock(return_value={"id": "123", "results": []})
    monkeypatch.setattr(P, "_live_api", api)
    monkeypatch.setattr(P, "cache_get", AsyncMock(side_effect=AssertionError("No cache reads")))
    assert (await P._team("123"))["id"] == "123"
    api.assert_awaited_once_with("/team/123")


async def test_missing_utc_is_verified_without_replacing_live_api_evidence(monkeypatch):
    live = {"teams": [{"id": "1"}, {"id": "2"}], "event": "Live API event", "status": None}
    verified = {**live, "event": "Other text", "starts_at": "2026-10-13T12:00:00Z"}
    monkeypatch.setattr(P, "_live_api", AsyncMock(return_value=live))
    monkeypatch.setattr(P.R, "refresh_match", AsyncMock(return_value=verified))
    result = await P._fresh_detail("123", force=True)
    assert result["event"] == "Live API event"
    assert result["starts_at"] == verified["starts_at"]


async def test_final_check_reloads_source_even_when_live_api_has_a_start(monkeypatch):
    live = {"teams": [{"id": "1"}, {"id": "2"}], "status": "upcoming",
            "starts_at": "2026-10-20T12:00:00Z"}
    monkeypatch.setattr(P, "_live_api", AsyncMock(return_value=live))
    refresh = AsyncMock(return_value=live | {"status": "live"})
    monkeypatch.setattr(P.R, "refresh_match", refresh)
    with pytest.raises(P.EvidenceUnavailable):
        await P._fresh_detail("123", force=True)
    refresh.assert_awaited_once_with("123")


@pytest.mark.parametrize("change", [
    {"status": "live"}, {"status": "final"},
    {"teams": [{"id": "1"}, {"id": "3"}]},
])
async def test_changed_live_fixture_is_withheld(monkeypatch, change):
    live = {"teams": [{"id": "1"}, {"id": "2"}], "status": None}
    monkeypatch.setattr(P, "_live_api", AsyncMock(return_value=live))
    monkeypatch.setattr(P.R, "refresh_match", AsyncMock(return_value=live | change))
    with pytest.raises(P.EvidenceUnavailable):
        await P._fresh_detail("123")
