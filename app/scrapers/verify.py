"""Verify selectors against LIVE vlr.gg. Run ON THE CONTAINER (has internet).

    python -m app.scrapers.verify

Reports element counts per page. Zero counts = selector needs fixing in selectors.py.
"""
import asyncio

from app.core.http import get_client
from app.scrapers.events import parse_events, parse_news
from app.scrapers.match_detail import parse_match
from app.scrapers.matches import parse_match_list, split_live_upcoming
from app.scrapers.players import parse_player
from app.scrapers.rankings import parse_rankings
from app.scrapers.stats import parse_stats
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

    # match-detail scoreboard: this page shape was NOT covered here before (the
    # blind spot that let the 2026 table -> div-grid scoreboard rewrite ship
    # silently, see selectors.py MATCH_SB_*) -- pick the most recent COMPLETED
    # result dynamically so this check never goes stale.
    print("== match scoreboard (first completed result) ==")
    mt = None
    if res:
        mid = res[0]["id"]
        html = await client.get_html(f"/{mid}")
        mt = parse_match(html)
        rows = [p for m in mt["maps"] for t in m["teams"] for p in t["players"]]
        print(f"  match {mid}: maps={len(mt['maps'])}  scoreboard rows={len(rows)}")
        if rows:
            p0 = rows[0]
            acs = p0["stats"].get("ACS", {}).get("value")
            k = p0["stats"].get("K", {}).get("value")
            print(f"  sample: {p0['player']} ({p0['agent']})  ACS={acs}  K={k}")

    print("== /stats (region=na, timespan=all) ==")
    html = await client.get_html("/stats/?region=na&timespan=all")
    sl = parse_stats(html)
    print(f"  rows: {len(sl)}")
    if sl:
        s0 = sl[0]
        print(f"  sample: {s0['player']} (id {s0['player_id']})  R2.0={s0['r2']}  "
              f"ACS={s0['acs']}  KAST={s0['kast']}  CL={s0['cl_won']}/{s0['cl_played']}")
        # spot-check the column inventory landed (R2.0 is the headline at 100% fill)
        filled_r2 = sum(1 for r in sl if r["r2"] is not None)
        print(f"  R2.0 filled: {filled_r2}/{len(sl)}")

    await client.aclose()

    bad = []
    if not res: bad.append("results")
    if not rk: bad.append("rankings")
    # stats: rows present AND R2.0 populated (the headline must coerce, not be null)
    if not (sl and any(r["r2"] is not None for r in sl)):
        bad.append("stats")
    if not evs: bad.append("events")
    if not nw: bad.append("news")
    # player page: alias + at least one agent row and one match are the invariants
    if not (pl["alias"] and pl["agent_stats"] and pl["matches"]):
        bad.append("player")
    # team page: name + a non-empty roster + at least one result are the invariants
    # (upcoming may legitimately be empty out of season, so it is not checked here)
    if not (tm["name"] and tm["roster"] and tm["results"]):
        bad.append("team")
    # match scoreboard: nonzero rows AND at least one sane, non-concatenated stat
    # (a concatenated cell like K="1385" would still be a nonzero float, so check
    # magnitude too -- a real single-map K/ACS never reaches these bounds)
    sb_rows = [p for m in mt["maps"] for t in m["teams"] for p in t["players"]] if mt else []
    sb_ok = bool(sb_rows) and any(
        (p["stats"].get("K", {}).get("value") or 0) < 100
        and (p["stats"].get("ACS", {}).get("value") or 0) < 1000
        for p in sb_rows
    )
    if not sb_ok:
        bad.append("match scoreboard")
    print()
    if bad:
        print(f"NEEDS FIXING in selectors.py: {', '.join(bad)}")
    else:
        print("ALL SELECTORS MATCHED")


if __name__ == "__main__":
    asyncio.run(main())
