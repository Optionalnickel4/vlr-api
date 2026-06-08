"""Verify selectors against LIVE vlr.gg. Run ON THE CONTAINER (has internet).

    python -m app.scrapers.verify

Reports element counts per page. Zero counts = selector needs fixing in selectors.py.
"""
import asyncio

from app.core.http import get_client
from app.scrapers.events import parse_events, parse_news
from app.scrapers.matches import parse_match_list, split_live_upcoming
from app.scrapers.rankings import parse_rankings


async def main() -> None:
    client = get_client()

    print("== /matches/results ==")
    html = await client.get_html("/matches/results")
    res = parse_match_list(html)
    print(f"  matches parsed: {len(res)}")
    if res:
        print(f"  sample: {res[0]}")

    print("== /matches (live/upcoming) ==")
    html = await client.get_html("/matches")
    split = split_live_upcoming(parse_match_list(html))
    print(f"  live: {len(split['live'])}  upcoming: {len(split['upcoming'])}")

    print("== /rankings ==")
    html = await client.get_html("/rankings")
    rk = parse_rankings(html)
    print(f"  rows: {len(rk)}")
    if rk:
        print(f"  sample: {rk[0]}")

    print("== /events ==")
    html = await client.get_html("/events")
    evs = parse_events(html)
    print(f"  events: {len(evs)}")
    if evs:
        print(f"  sample: {evs[0]}")

    print("== /news ==")
    html = await client.get_html("/news")
    nw = parse_news(html)
    print(f"  news: {len(nw)}")
    if nw:
        print(f"  sample: {nw[0]}")

    await client.aclose()

    bad = []
    if not res: bad.append("results")
    if not rk: bad.append("rankings")
    if not evs: bad.append("events")
    if not nw: bad.append("news")
    print()
    if bad:
        print(f"NEEDS FIXING in selectors.py: {', '.join(bad)}")
    else:
        print("ALL SELECTORS MATCHED")


if __name__ == "__main__":
    asyncio.run(main())
