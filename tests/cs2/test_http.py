"""Tests for app.cs2.http.Cs2HttpClient.

Two test groups:

1. offline tests — run on every CI invocation, no network. Verify the client
   compiles, instantiates, throttles correctly, and the CF-challenge detection
   regex works against a synthetic response body. These run by default.

2. live-network tests — gated behind @pytest.mark.live_network. They hit
   HLTV.org and assert that real responses come back (not a CF interstitial).
   These are SKIPPED in CI (the sandbox cannot reach HLTV) and run manually
   on the Mewtwo container during the PR verification step (Task 3 of the
   plan).
"""
import asyncio
import time

import pytest

from app.cs2.http import (
    CloudflareChallengeError,
    Cs2HttpClient,
    Cs2NotFound,
    close_client,
    get_client,
)


# --- offline: instantiation + throttling shape ---

def test_cs2_http_client_instantiates():
    client = Cs2HttpClient()
    assert client._base == "https://www.hltv.org"
    assert "Mozilla" in client._ua
    assert client._min_interval == 3.0
    assert client._max_retries == 3


def test_cs2_http_client_throttles_between_requests():
    """Two back-to-back throttle() calls should space out by >= min_interval.

    We measure wall time across two _throttle() invocations and assert that
    the gap is at least the configured min_interval. No network involved.
    """
    client = Cs2HttpClient()
    client._min_interval = 0.5  # tighten for the test so it doesn't take 3s

    async def run():
        t0 = time.monotonic()
        await client._throttle()
        await client._throttle()
        return time.monotonic() - t0

    elapsed = asyncio.run(run())
    # Two throttle calls; the second must wait at least ~0.5s after the first.
    # Allow some slop for event-loop scheduling.
    assert elapsed >= 0.4, f"throttle did not space requests (elapsed={elapsed:.3f}s)"


# --- offline: CF challenge detection ---

@pytest.mark.parametrize(
    "status,body,expected",
    [
        # Real pages — not a challenge.
        (200, "<html><title>Results for CS2</title>...lots of content...", False),
        (200, "<!doctype html><html><body>just a moment please", False),  # "just a moment" without CF context
        # CF interstitial signatures.
        (403, "<!DOCTYPE html><html><head><title>Just a moment...</title>", True),
        (503, "<script src='/cdn-cgi/challenge-platform/...'>__cf_chl...</script>", True),
        (403, "...cf-chl-managed...challenge...", True),
        # Wrong status — even if body has CF markers, we only flag 403/503.
        (200, "Just a moment... please wait", False),
        (404, "Just a moment...", False),
    ],
)
def test_cs2_http_client_detects_cf_challenge(status, body, expected):
    client = Cs2HttpClient()
    assert client._looks_like_cf_challenge(status, body) is expected


# --- offline: 404 raises Cs2NotFound, distinct from CF challenge ---

def test_cs2_not_found_is_distinct_from_cf_challenge():
    # Two distinct exceptions — they should not be subclasses of each other.
    assert not issubclass(Cs2NotFound, CloudflareChallengeError)
    assert not issubclass(CloudflareChallengeError, Cs2NotFound)


# --- live-network: ONLY run with `pytest -m live_network` on the Mewtwo container ---

@pytest.mark.live_network
@pytest.mark.asyncio
async def test_live_hltv_results_page_returns_real_content():
    """Hit HLTV /results and assert the response is NOT the CF interstitial.

    Run on the production container (Mewtwo, 192.168.1.35), not the sandbox —
    the sandbox cannot reach HLTV (CLAUDE.md confirms this for vlr.gg; HLTV
    is the same). Skip in CI.
    """
    client = get_client()
    try:
        resp = await client.get("/results")
        assert resp.status == 200, f"expected 200, got {resp.status}"
        # Must contain real HLTV markup — not the CF "Just a moment..." page.
        assert "Just a moment" not in resp.text, "got a Cloudflare challenge page"
        assert "<title>" in resp.text
        # At least 1 KB of real content (a challenge page is usually <2 KB).
        assert len(resp.text) > 5000, f"response suspiciously small: {len(resp.text)} bytes"
    finally:
        await close_client()


@pytest.mark.live_network
@pytest.mark.asyncio
async def test_live_hltv_404_raises_cs2_not_found():
    client = get_client()
    try:
        with pytest.raises(Cs2NotFound):
            await client.get("/this-path-definitely-does-not-exist-12345")
    finally:
        await close_client()