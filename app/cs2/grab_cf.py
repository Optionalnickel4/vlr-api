"""Solve HLTV's Cloudflare JS challenge once with a real browser and capture
the resulting cf_clearance cookie for Cs2HttpClient.

Why this exists: cloudscraper's TLS-fingerprint bypass (app/cs2/http.py) is
enough for HLTV's *basic* challenge, but stopped being enough as of 2026-07 —
requests from claude-dev started getting served the interstitial regardless.
This script is the escalation the original http.py docstring anticipated:
drive an actual headless Chromium (via nodriver) to the page, let Cloudflare's
JS challenge run and pass naturally, then pull the cf_clearance cookie it was
issued plus the exact User-Agent that earned it.

Requires:
    - A system Chromium/Chrome binary (apt install chromium)
    - The scrape-browser extra: pip install -e '.[scrape-browser]'

Usage:
    python -m app.cs2.grab_cf

This OVERWRITES the HLTV_CF_CLEARANCE and HLTV_USER_AGENT lines in .env (adds
them if missing). Restart whatever's using HltvSettings (the API process
and/or hltv-scheduler, once that exists) afterward — settings are cached via
@lru_cache in app/core/config.py and won't pick up the new .env on their own.

Cookie lifetime: short (observed on the order of hours, not days). Re-run this
whenever CloudflareChallengeError starts showing up in logs again. Not
automated/cron'd yet — v1 is a manual operator step.
"""
import asyncio
import sys
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"

CHALLENGE_MARKERS = ("just a moment", "cf-chl", "__cf_chl")


def _update_env(cf_clearance: str, user_agent: str) -> None:
    """Set HLTV_CF_CLEARANCE and HLTV_USER_AGENT in .env, preserving everything else."""
    if not ENV_PATH.exists():
        print(f"FAIL: {ENV_PATH} does not exist. Copy .env.example to .env first.", file=sys.stderr)
        sys.exit(1)

    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    wants = {
        "HLTV_CF_CLEARANCE": cf_clearance,
        "HLTV_USER_AGENT": user_agent,
    }
    seen = set()
    out = []
    for line in lines:
        key = line.split("=", 1)[0] if "=" in line else None
        if key in wants:
            out.append(f"{key}={wants[key]}")
            seen.add(key)
        else:
            out.append(line)
    for key, value in wants.items():
        if key not in seen:
            out.append(f"{key}={value}")

    ENV_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")


async def _grab() -> tuple[str, str]:
    import nodriver as uc  # deferred import — only required for this script

    from app.core.config import get_hltv_settings

    s = get_hltv_settings()
    browser = await uc.start(headless=True)
    try:
        tab = await browser.get(s.base_url)

        # Poll for the challenge to clear. HLTV's JS challenge normally resolves
        # in a few seconds; we give it generous headroom and fail loudly if it
        # doesn't (rather than silently capturing a still-challenged cookie).
        cleared = False
        for _ in range(30):
            html = await tab.get_content()
            if not any(marker in html.lower() for marker in CHALLENGE_MARKERS):
                cleared = True
                break
            await asyncio.sleep(1)

        if not cleared:
            print("FAIL: challenge did not clear after 30s.", file=sys.stderr)
            sys.exit(1)

        cookies = await browser.cookies.get_all()
        cf_cookie = next((c for c in cookies if c.name == "cf_clearance"), None)
        if cf_cookie is None:
            print("FAIL: page cleared but no cf_clearance cookie was set.", file=sys.stderr)
            sys.exit(1)

        user_agent = await tab.evaluate("navigator.userAgent")
        return cf_cookie.value, user_agent
    finally:
        await browser.stop()


def main() -> None:
    cf_clearance, user_agent = asyncio.get_event_loop().run_until_complete(_grab())
    _update_env(cf_clearance, user_agent)
    print("OK: captured cf_clearance and matching User-Agent, wrote to .env")
    print(f"  HLTV_USER_AGENT={user_agent}")
    print(f"  HLTV_CF_CLEARANCE={cf_clearance[:20]}... ({len(cf_clearance)} chars)")
    print("Restart the API process (and hltv-scheduler, if running) to pick this up.")


if __name__ == "__main__":
    main()
