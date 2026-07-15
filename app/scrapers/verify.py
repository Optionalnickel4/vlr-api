"""Verify selectors against LIVE vlr.gg. Run ON THE CONTAINER (has internet).

    python -m app.scrapers.verify

Reports element counts per page. Zero counts = selector needs fixing in selectors.py.

The _check_* helpers are PURE (parsed data in, failure strings out) so their
assertion logic is exercisable offline against captured pages; only main() does
network. Each check asserts the invariant that is SEMANTICALLY required — e.g.
numeric scores only on COMPLETED cards, never on upcoming/TBD ones — because an
over-strict assert that fails on valid sparse data trains us to ignore this
script, which defeats its purpose.
"""
import asyncio
import json
from typing import Any

from app.core.http import get_client
from app.scrapers.events import parse_events, parse_news
from app.scrapers.match_detail import parse_match
from app.scrapers.matches import parse_match_list, split_live_upcoming
from app.scrapers.players import parse_player
from app.scrapers.rankings import parse_rankings
from app.scrapers.stats import parse_stats
from app.scrapers.teams import parse_team
from app.services.search import parse_vlr_autocomplete

# real player used to probe the detail-page selectors (TenZ has deep history).
# TenZ is retired from pro play -> also the NULL control for current-team
# resolution (a non-null club here means we regressed to reading Past Teams).
PROBE_PLAYER_ID = "9"
# johnqt (Sentinels IGL) = the NON-NULL current-team probe: his club must
# resolve (to Sentinels as of 2026-07; update the pin if he transfers). This
# pair would have caught the national-team/club mixup AND a dead PLAYER_TEAM
# selector, which the TenZ probe alone cannot (null looks like "no team").
PROBE_PLAYER_CLUB_ID = "1265"
PROBE_PLAYER_CLUB_TEAM = "Sentinels"
# real team used to probe the team-page selectors (Sentinels = id 2)
PROBE_TEAM_ID = "2"
# regional rankings slug (full name, not the nav abbreviation)
PROBE_REGION = "north-america"

_STATUSES = {"live", "upcoming", "completed"}


# ---- pure checks (parsed data in, failure strings out) ----------------------
def _check_match_cards(cards: list[dict[str, Any]], page: str) -> list[str]:
    """Every card: an ml-status that parsed to a known status, 2 team names, an
    event. COMPLETED cards only: 2 numeric scores (upcoming render the '–'
    placeholder — legitimately non-numeric). eta/series are legitimately sparse
    and never asserted. 0 live matches is a valid state, never required."""
    bad: list[str] = []
    if not cards:
        return [f"{page}: no match cards"]
    no_status = [c["id"] for c in cards if c["status"] not in _STATUSES]
    if no_status:
        bad.append(f"{page}: {len(no_status)} cards without a live/upcoming/completed ml-status (e.g. {no_status[:3]})")
    short_teams = [c["id"] for c in cards if len([t for t in c["teams"] if t]) != 2]
    if short_teams:
        bad.append(f"{page}: {len(short_teams)} cards without exactly 2 team names (e.g. {short_teams[:3]})")
    no_event = [c["id"] for c in cards if not c["event"]]
    if no_event:
        bad.append(f"{page}: {len(no_event)} cards without an event (e.g. {no_event[:3]})")
    completed = [c for c in cards if c["status"] == "completed"]
    bad_scores = [
        c["id"] for c in completed
        if len(c["scores"]) != 2 or not all(s and any(ch.isdigit() for ch in s) for s in c["scores"])
    ]
    if bad_scores:
        bad.append(f"{page}: {len(bad_scores)} COMPLETED cards without 2 numeric scores (e.g. {bad_scores[:3]})")
    return bad


def _check_regional_rankings(rows: list[dict[str, Any]]) -> list[str]:
    """Regional rows carry record + earnings (unlike the world view), and team
    names must be tag-free — a '#' in a name means the ge-text child spans bled
    into the direct-text read (the exact bug this catches)."""
    if not rows:
        return ["rankings-regional: no rows"]
    bad: list[str] = []
    tagged = [r["team"] for r in rows if r["team"] and "#" in r["team"]]
    if tagged:
        bad.append(f"rankings-regional: team names polluted with #tag (e.g. {tagged[:3]})")
    unnamed = sum(1 for r in rows if not r["team"])
    if unnamed:
        bad.append(f"rankings-regional: {unnamed}/{len(rows)} rows without a team name")
    no_record = sum(1 for r in rows if not (r["record"] and r["wins"] and r["losses"]))
    if no_record:
        bad.append(f"rankings-regional: {no_record}/{len(rows)} rows without a W/L record")
    no_earnings = sum(1 for r in rows if not r["earnings"])
    if no_earnings:
        bad.append(f"rankings-regional: {no_earnings}/{len(rows)} rows without earnings")
    return bad


def _check_match_detail(mt: dict[str, Any]) -> list[str]:
    """On a COMPLETED match: header must name both teams and carry a BoN format,
    and at least one played map must have a round timeline. (A live/partial map
    with few rounds is fine — this probes the most recent completed result.)"""
    bad: list[str] = []
    named = [t for t in mt["teams"] if t.get("name")]
    if len(named) != 2:
        bad.append(f"match-header: {len(named)}/2 teams named")
    if not mt["format"]:
        bad.append("match-header: no BoN format parsed from the vs-notes")
    if not mt["maps"]:
        bad.append("match-detail: no per-map games parsed")
    elif not any(m["rounds"] for m in mt["maps"]):
        bad.append("match-rounds: no map has a round timeline (completed match must)")
    return bad


def _check_autocomplete(raw: str | bytes) -> list[str]:
    """/search/auto must still be a JSON list, and player hits must carry a
    numeric id + an alias (the shape parse_vlr_autocomplete banks on)."""
    try:
        items = json.loads(raw)
    except (ValueError, TypeError):
        return ["search-auto: response is not valid JSON"]
    if not isinstance(items, list):
        return ["search-auto: JSON is not a list"]
    hits = parse_vlr_autocomplete(raw)
    if not hits:
        return ["search-auto: no player hits parsed (id scheme changed?)"]
    malformed = [h for h in hits if not (h["id"] and h["id"].isdigit() and h["alias"])]
    if malformed:
        return [f"search-auto: {len(malformed)} hits missing id/alias (e.g. {malformed[:2]})"]
    return []


def _check_current_team(pl: dict[str, Any], expect_club: str | None, who: str) -> list[str]:
    """expect_club=None asserts the NULL control (no current club must resolve
    to a null team, not fall back to Past Teams / a national side)."""
    if expect_club is None:
        if pl["team"] is not None:
            return [f"current-team: {who} must have a NULL club, got {pl['team']!r} (Past-Teams bleed?)"]
        return []
    if pl["team"] != expect_club:
        return [f"current-team: {who} club is {pl['team']!r}, expected {expect_club!r}"]
    return []


async def main() -> None:
    client = get_client()
    bad: list[str] = []

    print("== /matches/results ==")
    html = await client.get_html("/matches/results")
    res = parse_match_list(html)
    print(f"  matches parsed: {len(res)}")
    if res:
        print(f"  sample: {res[0]}")
    bad += _check_match_cards(res, "results")

    print("== /matches (live/upcoming) ==")
    html = await client.get_html("/matches")
    upcoming_cards = parse_match_list(html)
    split = split_live_upcoming(upcoming_cards)
    print(f"  live: {len(split['live'])}  upcoming: {len(split['upcoming'])}")
    bad += _check_match_cards(upcoming_cards, "matches")

    print("== /rankings ==")
    html = await client.get_html("/rankings")
    rk = parse_rankings(html)
    print(f"  rows: {len(rk)}")
    if rk:
        print(f"  sample: {rk[0]}")
    if not rk:
        bad.append("rankings: no rows")

    print(f"== /rankings/{PROBE_REGION} (regional) ==")
    html = await client.get_html(f"/rankings/{PROBE_REGION}")
    rk_regional = parse_rankings(html)
    print(f"  rows: {len(rk_regional)}")
    if rk_regional:
        print(f"  sample: {rk_regional[0]}")
    bad += _check_regional_rankings(rk_regional)

    print("== /events ==")
    html = await client.get_html("/events")
    evs = parse_events(html)
    print(f"  events: {len(evs)}")
    if evs:
        print(f"  sample: {evs[0]}")
    if not evs:
        bad.append("events: no cards")

    print("== /news ==")
    html = await client.get_html("/news")
    nw = parse_news(html)
    print(f"  news: {len(nw)}")
    if nw:
        print(f"  sample: {nw[0]}")
    if not nw:
        bad.append("news: no items")

    print(f"== /player/{PROBE_PLAYER_ID} (timespan=all) ==")
    html = await client.get_html(f"/player/{PROBE_PLAYER_ID}/?timespan=all")
    pl = parse_player(html)
    print(f"  alias: {pl['alias']}  team: {pl['team']} ({pl['team_id']})  country: {pl['country']}")
    print(f"  agent_stats rows: {len(pl['agent_stats'])}  matches: {len(pl['matches'])}")
    if pl["agent_stats"]:
        print(f"  agent sample: {pl['agent_stats'][0]}")
    if pl["matches"]:
        print(f"  match sample: {pl['matches'][0]}")
    # player page: alias + at least one agent row and one match are the invariants
    if not (pl["alias"] and pl["agent_stats"] and pl["matches"]):
        bad.append("player: alias/agent_stats/matches missing")
    bad += _check_current_team(pl, None, f"TenZ ({PROBE_PLAYER_ID})")

    print(f"== /player/{PROBE_PLAYER_CLUB_ID} (current-team probe) ==")
    html = await client.get_html(f"/player/{PROBE_PLAYER_CLUB_ID}/?timespan=all")
    pl_club = parse_player(html)
    print(f"  alias: {pl_club['alias']}  team: {pl_club['team']} ({pl_club['team_id']})")
    bad += _check_current_team(
        pl_club, PROBE_PLAYER_CLUB_TEAM, f"johnqt ({PROBE_PLAYER_CLUB_ID})"
    )

    print(f"== /team/{PROBE_TEAM_ID} ==")
    html = await client.get_html(f"/team/{PROBE_TEAM_ID}")
    tm = parse_team(html)
    print(f"  name: {tm['name']} [{tm['tag']}]  id: {tm['id']}  country: {tm['country']} ({tm['country_code']})")
    print(f"  roster: {len(tm['roster'])}  results: {len(tm['results'])}  upcoming: {len(tm['upcoming'])}")
    if tm["roster"]:
        print(f"  roster sample: {tm['roster'][0]}")
    if tm["results"]:
        print(f"  result sample: {tm['results'][0]}")
    # team page: name + a non-empty roster + at least one result are the invariants
    # (upcoming may legitimately be empty out of season, so it is not checked here)
    if not (tm["name"] and tm["roster"] and tm["results"]):
        bad.append("team: name/roster/results missing")

    # match-detail scoreboard: this page shape was NOT covered here before (the
    # blind spot that let the 2026 table -> div-grid scoreboard rewrite ship
    # silently, see selectors.py MATCH_SB_*) -- pick the most recent COMPLETED
    # result dynamically so this check never goes stale.
    print("== match detail (first completed result) ==")
    mt = None
    if res:
        mid = res[0]["id"]
        html = await client.get_html(f"/{mid}")
        mt = parse_match(html)
        rows = [p for m in mt["maps"] for t in m["teams"] for p in t["players"]]
        print(f"  match {mid}: maps={len(mt['maps'])}  scoreboard rows={len(rows)}")
        print(f"  header: teams={[t['name'] for t in mt['teams']]}  format={mt['format']}  "
              f"rounds/map={[len(m['rounds']) for m in mt['maps']]}")
        if rows:
            p0 = rows[0]
            acs = p0["stats"].get("ACS", {}).get("value")
            k = p0["stats"].get("K", {}).get("value")
            print(f"  sample: {p0['player']} ({p0['agent']})  ACS={acs}  K={k}")
        bad += _check_match_detail(mt)
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
        bad.append("match scoreboard: no sane stat rows")

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
    # stats: rows present AND R2.0 populated (the headline must coerce, not be null)
    if not (sl and any(r["r2"] is not None for r in sl)):
        bad.append("stats: no rows / R2.0 all null")

    print("== /search/auto (autocomplete JSON) ==")
    raw = await client.get_html("/search/auto/?term=tenz")
    auto_bad = _check_autocomplete(raw)
    hits = parse_vlr_autocomplete(raw)
    print(f"  player hits: {len(hits)}")
    if hits:
        print(f"  sample: {hits[0]}")
    bad += auto_bad

    await client.aclose()

    print()
    if bad:
        print("NEEDS FIXING in selectors.py:")
        for b in bad:
            print(f"  - {b}")
    else:
        print("ALL SELECTORS MATCHED")


if __name__ == "__main__":
    asyncio.run(main())
