import asyncio
import time

import httpx

from app.core.config import get_settings


class VlrClient:
    """Polite async HTTP client for vlr.gg.

    - real User-Agent
    - global min-interval throttle (don't hammer vlr)
    - retry with exponential backoff on 429/5xx/network errors
    """

    def __init__(self) -> None:
        s = get_settings()
        self._settings = s
        self._client = httpx.AsyncClient(
            base_url=s.base_url,
            headers={"User-Agent": s.user_agent, "Accept-Language": "en-US,en;q=0.9"},
            timeout=s.request_timeout,
            follow_redirects=True,
        )
        self._lock = asyncio.Lock()
        self._last_request = 0.0

    async def _throttle(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self._settings.min_request_interval - (now - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = time.monotonic()

    async def get_raw(self, path: str) -> httpx.Response:
        """Fetch a path or absolute URL and return the full Response, throttled
        and retried with the same polite UA as get_html. Read `resp.content` for
        the verbatim bytes — used for one-shot fixture captures (no parsing)."""
        s = self._settings
        last_exc: Exception | None = None
        for attempt in range(s.max_retries):
            await self._throttle()
            try:
                resp = await self._client.get(path)
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"retryable {resp.status_code}", request=resp.request, response=resp
                    )
                resp.raise_for_status()
                return resp
            except (httpx.HTTPStatusError, httpx.TransportError) as exc:
                last_exc = exc
                await asyncio.sleep(2 ** attempt)
        assert last_exc is not None
        raise last_exc

    async def get_html(self, path: str) -> str:
        return (await self.get_raw(path)).text

    async def aclose(self) -> None:
        await self._client.aclose()


_client: VlrClient | None = None


def get_client() -> VlrClient:
    global _client
    if _client is None:
        _client = VlrClient()
    return _client
