"""Verify selectors against LIVE vlr.gg. Run ON THE CONTAINER (has internet).

    python -m app.scrapers.verify

Reports element counts per page. Zero counts = selector needs fixing in selectors.py.
"""
import asyncio

from app.core.http import get_client
from app.scrapers.events import parse_events, parse_news
from app.scrapers.matches import parse_match_list, split_live_upcoming
from app.scrapers.players import parse_player
from app.scrapers.rankings import parse_rankings
from app.scrapers.teams import parse_team

# real player used to probe the detail-page selectors (TenZ has deep history)
PROBE_PLAYER_ID = "9"
# real team used to probe the team-page selectors (Sentinels = id 2)
PROBE_TEAM_ID = "2"


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

    print(f"== /player/{PROBE_PLAYER_ID} (timespan=all) ==")
    html = await client.get_html(f"/player/{PROBE_PLAYER_ID}/?timespan=all")
    pl = parse_player(html)
    print(f"  alias: {pl['alias']}  team: {pl['team']} ({pl['team_id']})  country: {pl['country']}")
    print(f"  agent_stats rows: {len(pl['agent_stats'])}  matches: {len(pl['matches'])}")
    if pl["agent_stats"]:
        print(f"  agent sample: {pl['agent_stats'][0]}")
    if pl["matches"]:
        print(f"  match sample: {pl['matches'][0]}")

    print(f"== /team/{PROBE_TEAM_ID} ==")
    html = await client.get_html(f"/team/{PROBE_TEAM_ID}")
    tm = parse_team(html)
    print(f"  name: {tm['name']} [{tm['tag']}]  id: {tm['id']}  country: {tm['country']} ({tm['country_code']})")
    print(f"  roster: {len(tm['roster'])}  results: {len(tm['results'])}  upcoming: {len(tm['upcoming'])}")
    if tm["roster"]:
        print(f"  roster sample: {tm['roster'][0]}")
    if tm["results"]:
        print(f"  result sample: {tm['results'][0]}")

    await client.aclose()

    bad = []
    if not res: bad.append("results")
    if not rk: bad.append("rankings")
    if not evs: bad.append("events")
    if not nw: bad.append("news")
    # player page: alias + at least one agent row and one match are the invariants
    if not (pl["alias"] and pl["agent_stats"] and pl["matches"]):
        bad.append("player")
    # team page: name + a non-empty roster + at least one result are the invariants
    # (upcoming may legitimately be empty out of season, so it is not checked here)
    if not (tm["name"] and tm["roster"] and tm["results"]):
        bad.append("team")
    print()
    if bad:
        print(f"NEEDS FIXING in selectors.py: {', '.join(bad)}")
    else:
        print("ALL SELECTORS MATCHED")


if __name__ == "__main__":
    asyncio.run(main())
