"""Capture HLTV HTML pages for offline test fixtures.

Run on the production container (Mewtwo, 192.168.1.35) where HLTV is
reachable. The sandbox CAN reach HLTV today (verified 2026-06-20), so
the same script works locally too.

    python -m app.cs2.capture [--results-only]

For v1 we only need /results for the matches parser; other pages
(upcoming, events, rankings, etc.) get capture scripts added when
their parsers are written in Phase C.
"""
import argparse
import asyncio
import sys
from pathlib import Path

from app.cs2.http import get_client, close_client, CloudflareChallengeError


FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "cs2" / "fixtures"


async def capture(path: str) -> tuple[str, int, int]:
    """Returns (slug, status, bytes_written)."""
    client = get_client()
    try:
        resp = await client.get(path)
        slug = path.strip("/").replace("/", "_") or "root"
        out = FIXTURES / f"{slug}.html"
        out.write_text(resp.text, encoding="utf-8")
        return slug, resp.status, len(resp.text)
    finally:
        await close_client()


async def main(results_only: bool) -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    paths = ["/results"]
    if not results_only:
        # Phase C additions; left here as a TODO so the script grows naturally.
        paths.extend(["/matches", "/rankings", "/events", "/news"])
    failures = 0
    for path in paths:
        try:
            slug, status, size = await capture(path)
            if status != 200:
                print(f"FAIL {path} -> status {status}", file=sys.stderr)
                failures += 1
            else:
                print(f"OK   {path} -> fixtures/{slug}.html ({size} bytes)")
        except CloudflareChallengeError as e:
            print(f"FAIL {path} -> Cloudflare challenge (run grab_cf.py)", file=sys.stderr)
            failures += 1
        except Exception as e:
            print(f"FAIL {path} -> {type(e).__name__}: {e}", file=sys.stderr)
            failures += 1
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Capture HLTV HTML fixtures.")
    parser.add_argument(
        "--results-only",
        action="store_true",
        help="Only capture /results (used by Phase B tests).",
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.results_only)))