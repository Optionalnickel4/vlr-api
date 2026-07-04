"""Async-friendly HLTV client built on cloudscraper.

cloudscraper wraps the requests library with a TLS fingerprint that bypasses
the basic Cloudflare challenge HLTV serves to all requests. Async-friendly
via run_in_executor because cloudscraper itself is sync.

For v1 we accept this sync-over-executor shape — the scheduler jobs are
sequential within a single refresh call, and the request pacing comes from
MIN_REQUEST_INTERVAL, not concurrency. If HLTV raises the bar and we have
to add the nodriver+grab_cf.py cookie-refresh flow (v2), this file is the
one that grows the cookie+UA loading logic.
"""
import asyncio
import logging
from dataclasses import dataclass

import cloudscraper

from app.core.config import get_hltv_settings

log = logging.getLogger("cs2.http")


class CloudflareChallengeError(Exception):
    """HLTV returned a Cloudflare challenge page instead of real content.

    Trigger: a 403 or 503 response whose body looks like the CF interstitial
    (contains 'cf-chl' or 'Just a moment...'). Recovery path is documented in
    the plan: when this fires in production, the operator must (a) re-run
    grab_cf.py on the Mewtwo container to refresh cf_clearance, then (b)
    either wait for the cookie to be picked up or restart hltv-scheduler.

    In v2 we'll add nodriver support so grab_cf.py can be automated; for v1
    the manual flow is acceptable because the basic challenge shouldn't fire
    on the v1 surface (results/upcoming/live/events/rankings/news) at the
    3s MIN_REQUEST_INTERVAL pace.
    """


@dataclass
class Cs2Response:
    status: int
    text: str
    url: str


class Cs2HttpClient:
    """Polite async client for hltv.org.

    - real Chrome User-Agent (configured via HLTV_USER_AGENT)
    - global min-interval throttle (default 3.0s — matches M3MONs/hltv-scraper-api)
    - retry with exponential backoff on 429/5xx/network errors
    - raises CloudflareChallengeError if the response body is the CF interstitial
    """

    def __init__(self) -> None:
        s = get_hltv_settings()
        # browser={"browser": "chrome", "platform": "windows", "mobile": False} tells
        # cloudscraper to pick the Chrome Windows TLS fingerprint. The default
        # fingerprint selector is fine — we override the UA separately via the
        # request header to keep it in sync with what the browser would actually send.
        self._scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
        self._base = s.base_url.rstrip("/")
        self._ua = s.user_agent
        self._timeout = s.request_timeout
        self._min_interval = s.min_request_interval
        self._max_retries = s.max_retries
        self._lock = asyncio.Lock()
        self._last_request_at = 0.0
        # If grab_cf.py has captured a live cf_clearance cookie, ride it along on
        # every request. cloudscraper's TLS fingerprint alone stopped being enough
        # (confirmed 2026-07, HLTV started serving the JS challenge to the sandbox/
        # claude-dev egress); the cookie is what actually gets past it. The cookie
        # is bound to the UA that solved the challenge, so we don't override self._ua
        # separately — HLTV_USER_AGENT and HLTV_CF_CLEARANCE are written together by
        # grab_cf.py and must be kept in sync.
        if s.cf_clearance:
            host = self._base.split("://", 1)[-1].split("/", 1)[0]
            domain = "." + host if not host.startswith(".") else host
            self._scraper.cookies.set("cf_clearance", s.cf_clearance, domain=domain)

    async def _throttle(self) -> None:
        async with self._lock:
            now = asyncio.get_event_loop().time()
            wait = self._min_interval - (now - self._last_request_at)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request_at = asyncio.get_event_loop().time()

    def _looks_like_cf_challenge(self, status: int, body: str) -> bool:
        # The CF interstitial has a distinctive title ("Just a moment...") and a
        # cf-chl / __cf_chl_ marker script. 403 + body match = the TLS/UA
        # fingerprint was rejected (we need to update the cookie). 503 + body
        # match = the CF "origin unreachable" path.
        if status not in (403, 503):
            return False
        body_l = body.lower()
        return "just a moment" in body_l or "cf-chl" in body_l or "__cf_chl" in body_l

    async def get(self, path: str) -> Cs2Response:
        """Fetch a path (relative to HLTV_BASE_URL) and return the body.

        Throttled and retried with the same polite semantics as app/core/http.py
        for vlr.gg, but with the CF interstitial detection above.
        """
        url = f"{self._base}{path if path.startswith('/') else '/' + path}"
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            await self._throttle()
            loop = asyncio.get_event_loop()
            try:
                resp = await loop.run_in_executor(
                    None,
                    lambda: self._scraper.get(
                        url,
                        headers={"User-Agent": self._ua, "Accept-Language": "en-US,en;q=0.9"},
                        timeout=self._timeout,
                    ),
                )
            except Exception as exc:  # cloudscraper wraps requests.Timeout etc.
                last_exc = exc
                log.warning("cs2.http transport error on %s (attempt %d): %s", url, attempt + 1, exc)
                await asyncio.sleep(2 ** attempt)
                continue

            if self._looks_like_cf_challenge(resp.status_code, resp.text):
                # Don't retry — the CF challenge won't resolve without a new cf_clearance cookie.
                raise CloudflareChallengeError(url)

            if resp.status_code == 404:
                # Final — distinct domain error so routers can map to HTTP 404.
                raise Cs2NotFound(path)

            if resp.status_code == 429 or resp.status_code >= 500:
                last_exc = RuntimeError(f"retryable {resp.status_code} on {url}")
                log.warning("cs2.http retryable %d on %s (attempt %d)", resp.status_code, url, attempt + 1)
                await asyncio.sleep(2 ** attempt)
                continue

            if resp.status_code >= 400:
                # Other 4xx — final, surface to caller.
                resp.raise_for_status()

            return Cs2Response(status=resp.status_code, text=resp.text, url=url)

        assert last_exc is not None
        raise last_exc

    async def aclose(self) -> None:
        # cloudscraper wraps requests.Session — close it to release the pool.
        # Cloudscraper doesn't expose aclose() directly, but the underlying
        # session has a close() that's safe to call.
        try:
            close = getattr(self._scraper, "close", None)
            if close is not None:
                close()
        except Exception:  # pragma: no cover — defensive
            pass


class Cs2NotFound(Exception):
    """hltv.org returned 404 for a path — the resource genuinely doesn't exist.

    Distinct from a transient 5xx/429 (retried) and from CloudflareChallengeError
    (raises separately). Routers map this to HTTP 404.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        super().__init__(f"hltv.org 404 for {path}")


_client: Cs2HttpClient | None = None


def get_client() -> Cs2HttpClient:
    global _client
    if _client is None:
        _client = Cs2HttpClient()
    return _client


async def close_client() -> None:
    """Close the lazy cloudscraper session. Safe to call when no client was ever created."""
    global _client
    if _client is not None:
        try:
            await _client.aclose()
        finally:
            _client = None