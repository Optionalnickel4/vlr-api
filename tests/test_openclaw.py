import json

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.services import openclaw as O


def configured():
    return Settings(_env_file=None, openclaw_gateway_token=SecretStr("test-gateway"),
                    openclaw_access_client_id=SecretStr("test-client"),
                    openclaw_access_client_secret=SecretStr("test-secret"))


@pytest.mark.parametrize("url", ["http://example.com", "https://user:pass@example.com", "https://[invalid", "https://example.com?token=x"])
def test_connection_fails_closed(url):
    assert not O.connection_ready(configured().model_copy(update={"openclaw_base_url": url}))


async def test_server_transport_targets_dedicated_agent_and_keeps_credentials_in_headers(monkeypatch):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"winner_id":null}'}}]})
    client_type = httpx.AsyncClient
    monkeypatch.setattr(O, "get_settings", configured)
    monkeypatch.setattr(O.httpx, "AsyncClient", lambda **kw: client_type(transport=httpx.MockTransport(handler), **kw))
    assert await O.request_prediction({"match_id": "123"}) == {"winner_id": None}
    request = requests[0]
    assert request.headers["Authorization"] == "Bearer test-gateway"
    assert request.headers["CF-Access-Client-Secret"] == "test-secret"
    payload = json.loads(request.content)
    assert payload["model"] == "openclaw/val-predictions"
    assert "user" not in payload
    assert "test-secret" not in str(payload)


@pytest.mark.parametrize("status,body", [(302, "test-secret"), (403, "test-gateway"), (200, "x" * 64001), (200, "not json")], ids=["redirect", "forbidden", "oversized", "malformed"])
async def test_auth_redirect_and_invalid_responses_are_safe_failures(monkeypatch, status, body):
    client_type = httpx.AsyncClient
    monkeypatch.setattr(O, "get_settings", configured)
    monkeypatch.setattr(O.httpx, "AsyncClient", lambda **kw: client_type(
        transport=httpx.MockTransport(lambda request: httpx.Response(status, text=body)), **kw))
    with pytest.raises(O.OpenClawUnavailable) as caught:
        await O.request_prediction({})
    assert "test-secret" not in str(caught.value)
    assert "test-gateway" not in str(caught.value)
