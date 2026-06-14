"""Recon: discover the column inventory on vlr.gg/stats.

Fetches one region + each time-window, dumps:
  - column names (from <thead>)
  - per-column population rate (non-empty cells / total rows)
  - player count per window
  - the raw URL params vlr actually accepts

Run ON THE CONTAINER (needs internet):
    python -m app.scrapers.stats_recon
"""
import asyncio
import sys
from collections import defaultdict
from urllib.parse import urlencode

from selectolax.parser import HTMLParser

from app.core.http import get_client
from app.scrapers._util import text_of

# ── params to probe ──────────────────────────────────────────────────────────
# vlr /stats accepts: timespan={30d,60d,90d,all} and region/event filters
# We'll probe the most common combinations.
REGIONS = [
    ("na", "North America"),
    ("eu", "Europe"),
    ("all", "World"),
]
TIMESPANS = ["30d", "60d", "90d", "all"]

STATS_PATH = "/stats"


def _build_url(region: str, timespan: str) -> str:
    params: dict[str, str] = {"timespan": timespan}
    if region != "all":
        params["region"] = region
    return f"{STATS_PATH}?{urlencode(params)}"


def _parse_stats_table(html: str) -> dict:
    """Return column names, per-column fill rates, player count, and raw sample."""
    tree = HTMLParser(html)

    # Find the main stats table — vlr uses wf-table on this page
    table = tree.css_first("table.wf-table")
    if table is None:
        # Try any table
        table = tree.css_first("table")

    result: dict = {
        "table_found": table is not None,
        "columns": [],
        "player_count": 0,
        "fill_rates": {},
        "sample_row": None,
    }

    if table is None:
        # Dump page shape clues so we can debug
        first_divs = [
            n.attributes.get("class", "")
            for n in tree.css("div")
            if n.attributes.get("class")
        ][:20]
        result["page_div_classes"] = first_divs
        return result

    # Header
    headers: list[str] = []
    thead = table.css_first("thead")
    if thead:
        for th in thead.css("th"):
            raw = text_of(th).strip()
            headers.append(raw if raw else f"col_{len(headers)}")
    result["columns"] = headers

    # Body rows
    tbody = table.css_first("tbody")
    if tbody is None:
        return result

    rows = tbody.css("tr")
    result["player_count"] = len(rows)

    # Per-column fill counts
    fill: dict[str, int] = defaultdict(int)
    for row in rows:
        cells = row.css("td")
        for i, cell in enumerate(cells):
            col = headers[i] if i < len(headers) else f"col_{i}"
            val = text_of(cell).strip()
            if val:
                fill[col] += 1

    n = len(rows)
    result["fill_rates"] = {
        col: round(fill[col] / n, 3) if n else 0.0
        for col in (headers or list(fill.keys()))
    }

    # Sample row (first player)
    if rows:
        cells = rows[0].css("td")
        result["sample_row"] = {
            (headers[i] if i < len(headers) else f"col_{i}"): text_of(c).strip()
            for i, c in enumerate(cells)
        }

    return result


def _print_section(label: str, data: dict) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {label}")
    print(f"{'─' * 60}")
    if not data["table_found"]:
        print("  !! TABLE NOT FOUND — page div classes:")
        for cls in data.get("page_div_classes", []):
            print(f"    {cls}")
        return

    print(f"  players : {data['player_count']}")
    print(f"  columns : {data['columns']}")
    print()
    print(f"  {'Column':<18}  fill%")
    print(f"  {'──────':<18}  ─────")
    for col, rate in data["fill_rates"].items():
        bar = "█" * int(rate * 20)
        print(f"  {col:<18}  {rate * 100:5.1f}%  {bar}")

    if data["sample_row"]:
        print()
        print("  sample (first row):")
        for k, v in data["sample_row"].items():
            print(f"    {k:<18} = {v!r}")


async def main() -> None:
    client = get_client()

    # 1. Quick shape recon: one region × all timespans
    probe_region, probe_label = REGIONS[0]  # NA
    print(f"\n{'═' * 60}")
    print(f"  VLR /stats recon — region={probe_label}")
    print(f"{'═' * 60}")

    all_results: dict[str, dict] = {}
    for ts in TIMESPANS:
        url = _build_url(probe_region, ts)
        print(f"  fetching {url} … ", end="", flush=True)
        try:
            html = await client.get_html(url)
            data = _parse_stats_table(html)
            print(f"ok  ({data['player_count']} players)")
        except Exception as exc:
            print(f"ERROR: {exc}")
            data = {"table_found": False, "error": str(exc)}
        all_results[ts] = data

    # 2. Print per-timespan inventory
    for ts, data in all_results.items():
        _print_section(f"timespan={ts}  region={probe_label}", data)

    # 3. Compare player counts and column stability across timespans
    print(f"\n{'═' * 60}")
    print("  CROSS-TIMESPAN SUMMARY")
    print(f"{'═' * 60}")
    print(f"  {'timespan':<8}  {'players':>7}  columns")
    for ts, data in all_results.items():
        n = data.get("player_count", "?")
        cols = data.get("columns", [])
        print(f"  {ts:<8}  {n:>7}  {cols}")

    # 4. Quick cross-region check (single timespan=all)
    print(f"\n{'═' * 60}")
    print("  CROSS-REGION CHECK (timespan=all)")
    print(f"{'═' * 60}")
    print(f"  {'region':<8}  {'players':>7}  first 5 cols")
    for region_code, region_label in REGIONS:
        url = _build_url(region_code, "all")
        print(f"  fetching {url} … ", end="", flush=True)
        try:
            html = await client.get_html(url)
            data = _parse_stats_table(html)
            n = data.get("player_count", "?")
            cols = data.get("columns", [])[:5]
            print(f"ok — {n:>4} players  {cols}")
        except Exception as exc:
            print(f"ERROR: {exc}")

    await client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
