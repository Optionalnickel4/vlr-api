import asyncio
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from app.api import jarvis as API
from app.main import app
from app.services import jarvis as J, refresh as R


AUTH = {"Authorization": "Bearer query-test-credential"}
URL = "/api/v1/jarvis/query"


@pytest.fixture
def stored(monkeypatch):
    values = {
        R.CACHE_LIVE: [
            {
                "id": "101", "status": "live", "teams": ["Sentinels", "NRG"],
                "scores": ["1", "0"], "event": "VCT Americas", "series": "Week 1",
                "time": "LIVE", "eta": None,
            },
        ],
        R.CACHE_UPCOMING: [
            {
                "id": "201", "status": "upcoming", "teams": ["G2 Esports", "Paper Rex"],
                "scores": ["–", "–"], "event": "Valorant Champions 2026",
                "series": "Group Stage", "time": "5:00 AM", "eta": "4h",
            },
            {
                "id": "202", "status": "upcoming", "teams": ["Karmine Corp", "NRG"],
                "scores": ["–", "–"], "event": "Valorant Champions 2026",
                "series": "Group Stage", "time": "8:00 AM", "eta": "7h",
            },
            {
                "id": "203", "status": "upcoming", "teams": ["Sentinels", "LOUD"],
                "scores": ["–", "–"], "event": "VCT Americas",
                "series": "Playoffs", "time": "Tomorrow", "eta": "1d",
            },
        ],
        R.CACHE_RESULTS: [
            {
                "id": "301", "status": "completed", "teams": ["JD Gaming", "FUT Esports"],
                "scores": ["0", "2"], "event": "Valorant Champions 2026",
                "series": "Opening", "time": "7:35 AM", "eta": "1d",
            },
        ],
    }

    async def read(key):
        return values.get(key)

    monkeypatch.setattr(J, "cache_get", read)
    monkeypatch.setattr(J, "_db_match", AsyncMock(return_value=None))
    monkeypatch.setattr(J, "_db_team_detail", AsyncMock(return_value=None))
    return values


@pytest.fixture
def client(monkeypatch, tmp_path):
    token = tmp_path / "token"
    token.write_text("query-test-credential")
    monkeypatch.setattr(API.get_settings(), "jarvis_token_file", str(token))
    redis = AsyncMock()
    redis.eval.return_value = [1, 60]
    monkeypatch.setattr(API, "get_redis", lambda: redis)
    return TestClient(app), redis


def post(client, operation, params=None, headers=AUTH):
    body = {"operation": operation}
    if params is not None:
        body["params"] = params
    return client.post(URL, headers=headers, json=body)


def test_general_upcoming_order_limit_and_unknown_time(client, stored):
    response = post(client[0], "matches.list", {"state": "upcoming", "limit": 2})
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "ok"
    assert [item["id"] for item in body["items"]] == ["201", "202"]
    assert body["coverage"]["ordering"] == "source_order"
    assert body["coverage"]["truncated"] is True
    assert body["coverage"]["status"] == "partial"
    assert body["items"][0]["starts_at"] is None
    assert body["items"][0]["source_time"] == {
        "display_time": "5:00 AM", "relative_eta": "4h",
    }
    assert body["items"][0]["teams"][0]["score"] is None
    assert body["freshness"]["status"] == "unknown"
    assert body["freshness"]["captured_at"] is None


@pytest.mark.parametrize(
    ("state", "expected", "score"),
    [("live", "101", 1), ("completed", "301", 0)],
)
def test_live_and_completed_lists(client, stored, state, expected, score):
    body = post(client[0], "matches.list", {"state": state}).json()
    assert body["state"] == "ok"
    assert body["items"][0]["id"] == expected
    assert body["items"][0]["state"] == state
    assert body["items"][0]["teams"][0]["score"] == score
    assert body["items"][0]["url"] == f"https://www.vlr.gg/{expected}"


def test_supported_filters(client, stored):
    team = post(client[0], "matches.list", {
        "state": "upcoming", "team": "  nrg  ", "limit": 25,
    }).json()
    assert [item["id"] for item in team["items"]] == ["202"]

    event = post(client[0], "matches.list", {
        "state": "upcoming", "event": "champions", "limit": 25,
    }).json()
    assert [item["id"] for item in event["items"]] == ["201", "202"]
    assert event["coverage"]["supported_filters"] == ["team", "event"]
    assert event["coverage"]["unsupported_filters"] == ["region", "time_window"]


def test_empty_is_distinct_from_unavailable(client, stored):
    stored[R.CACHE_LIVE] = []
    empty = post(client[0], "matches.list", {"state": "live"})
    assert empty.status_code == 200
    assert empty.json()["state"] == "empty"
    assert empty.json()["coverage"]["cache_status"] == "present"
    assert empty.json()["coverage"]["status"] == "partial"

    stored.pop(R.CACHE_LIVE)
    missing = post(client[0], "matches.list", {"state": "live"})
    assert missing.status_code == 503
    assert missing.json()["state"] == "unavailable"
    assert missing.json()["error"] == "cache_miss"
    assert missing.json()["coverage"]["cache_status"] == "missing"


def test_capabilities_disclose_supported_and_gaps(client, stored):
    body = post(client[0], "capabilities").json()
    by_name = {item["operation"]: item for item in body["items"]}
    assert by_name["matches.list"]["available"] is True
    assert by_name["matches.list"]["parameters"]["filters"] == ["team", "event"]
    for name in ["rankings.list", "players.summary", "news.list", "matches.head_to_head"]:
        assert by_name[name]["available"] is False
        assert by_name[name]["gap"]


def test_closed_typed_request_validation_happens_after_auth(client, stored):
    c, redis = client
    assert c.post(URL, json={"operation": "matches.list", "params": {"state": "live"}}).status_code == 401
    assert c.post(URL, headers={"Authorization": "Bearer wrong"}, json={}).status_code == 401
    redis.eval.assert_not_called()

    invalid = [
        {"operation": "matches.list", "params": {"state": "future"}},
        {"operation": "matches.list", "params": {"state": "live", "limit": 26}},
        {"operation": "matches.list", "params": {"state": "live", "region": "na"}},
        {"operation": "fetch.url", "params": {"url": "https://example.test"}},
        {"operation": "matches.list", "params": {"state": "live", "sql": "select 1"}},
    ]
    for payload in invalid:
        response = c.post(URL, headers=AUTH, json=payload)
        assert response.status_code == 422
        assert response.json()["state"] == "error"
        assert response.json()["error"] == "invalid_request"
    redis.eval.assert_not_called()


def test_query_rate_limit(client, stored):
    c, redis = client
    redis.eval.return_value = [31, 17]
    response = post(c, "capabilities")
    assert response.status_code == 429
    assert response.headers["retry-after"] == "17"
    assert response.json()["error"] == "rate_limited"


def test_query_timeout_and_storage_failure(client, stored, monkeypatch):
    c, redis = client

    async def slow(*args):
        await asyncio.sleep(1)

    monkeypatch.setattr(API, "REQUEST_TIMEOUT", 0.01)
    redis.eval.side_effect = slow
    response = post(c, "capabilities")
    assert response.status_code == 504
    assert response.json()["error"] == "timeout"

    redis.eval.side_effect = RuntimeError("private storage detail")
    response = post(c, "capabilities")
    assert response.status_code == 503
    assert response.json()["error"] == "storage_unavailable"
    assert "private storage detail" not in response.text


async def test_match_lookup_and_team_search_are_cache_db_only(stored, monkeypatch):
    stored[R.CACHE_MATCH.format(id="201")] = {
        "status": None, "teams": [
            {"id": "10", "name": "G2 Esports", "score": None},
            {"id": "11", "name": "Paper Rex", "score": None},
        ], "event": "Valorant Champions 2026", "series": "Group Stage",
    }
    match = await J.query(API.JARVIS_REQUEST_ADAPTER.validate_python({
        "operation": "matches.get", "params": {"match_id": "201"},
    }))
    assert match["items"][0]["url"] == "https://www.vlr.gg/201"
    assert match["items"][0]["teams"][0]["id"] == "10"
    assert match["items"][0]["state"] is None

    monkeypatch.setattr(J.S, "db_team_search", AsyncMock(return_value=[{
        "id": "2", "name": "Sentinels", "country": "United States",
    }]))
    team = await J.query(API.JARVIS_REQUEST_ADAPTER.validate_python({
        "operation": "teams.search", "params": {"query": "Sentinels", "limit": 1},
    }))
    assert team["items"] == [{
        "id": "2", "name": "Sentinels", "tag": None,
        "region": "United States", "url": "https://www.vlr.gg/team/2",
    }]
