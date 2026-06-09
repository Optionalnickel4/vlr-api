"""One-shot live-page capture — saves raw vlr.gg HTML verbatim as a test fixture.

Fetches a single match-detail (or any) vlr.gg URL through the app's polite httpx
client (real User-Agent, throttle, retry) and writes the bytes EXACTLY as
received to tests/fixtures/. No parsing, no selectors, no DB, no cache — just save
the bytes so the live markup can be diffed against our selectors later.

Intended use: the moment a map goes live, grab that match page so we have a real
live-state fixture (scoreboard / rounds / vetos mid-game) to verify the live-path
selectors against.

    python -m app.scrapers.capture <match-url-or-path> [output_filename]

Examples:
    python -m app.scrapers.capture https://www.vlr.gg/123456/team-a-vs-team-b
    python -m app.scrapers.capture /123456/team-a-vs-team-b match_detail_live.html

A bare path (leading "/") resolves against the client's vlr.gg base_url; a full
http(s) URL is used as-is. Default output name: match_detail_live.html.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from app.core.http import get_client

# repo_root/tests/fixtures  (this file is app/scrapers/capture.py)
FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests" / "fixtures"

DEFAULT_OUT = "match_detail_live.html"


async def capture(target: str, out_name: str) -> Path:
    """Fetch `target` and write the verbatim response bytes to tests/fixtures/."""
    client = get_client()
    try:
        resp = await client.get_raw(target)
    finally:
        await client.aclose()

    out_path = FIXTURES_DIR / out_name
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(resp.content)  # raw bytes, no decode/parse

    print(f"saved {len(resp.content):,} bytes -> {out_path}")
    print(f"  HTTP {resp.status_code}  final-url {resp.url}")
    print(f"  content-type: {resp.headers.get('content-type')}")
    return out_path


def main(argv: list[str]) -> int:
    if not argv or argv[0] in {"-h", "--help"}:
        print(
            "usage: python -m app.scrapers.capture <match-url-or-path> "
            "[output_filename]",
            file=sys.stderr,
        )
        return 2
    target = argv[0]
    out_name = argv[1] if len(argv) > 1 else DEFAULT_OUT
    asyncio.run(capture(target, out_name))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
