"""Match-detail scraper tests (Phase 7) — the full match shape.

Parses one banked live fixture (a completed BO3, all three maps played) and
asserts structure + invariants + the known-value checks that prove the
scoreboard side-split spans are read correctly:
  - match_detail_completed.html = ABACATUDOS 2-1 Team Liquid Brazil
    (match 707486, captured live 2026-07-15 against vlr's 2026 div-grid
    scoreboard rewrite — see selectors.py MATCH_SB_* for the markup change)
No network is touched.
"""
from pathlib import Path

from selectolax.parser import HTMLParser

from app.scrapers._util import parse_numeric, parse_percent
from app.scrapers.match_detail import parse_match

FIX = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIX / name).read_text()


COMPLETED = "match_detail_completed.html"


# ---------- coercion helpers (null, never NaN) ----------
def test_parse_numeric_null_not_nan():
    assert parse_numeric("13") == 13.0
    assert parse_numeric("1.04") == 1.04
    for bad in ["", "  ", None, "nan", "inf", "-", "N/A"]:
        assert parse_numeric(bad) is None  # never NaN, never a crash


def test_parse_percent_strips_then_parses():
    assert parse_percent("64%") == 64.0
    assert parse_percent("") is None
    assert parse_percent(None) is None
    assert parse_percent("100") == 100.0


# ---------- header ----------
def test_header_event_teams_score_veto():
    d = parse_match(load(COMPLETED))
    assert d["event"] == "Challengers 2026: Brazil Gamers Club Stage 2"
    assert d["series"] and "Relegation" in d["series"]
    assert d["format"] == "BO3"
    names = [t["name"] for t in d["teams"]]
    assert names == ["ABACATUDOS", "Team Liquid Brazil"]
    ids = [t["id"] for t in d["teams"]]
    assert all(i and i.isdigit() for i in ids)
    for t in d["teams"]:
        assert isinstance(t["score"], (int, float))
    # the veto/picks strip is present and mentions a ban/pick
    assert d["veto"] and ("ban" in d["veto"] and "pick" in d["veto"])


def test_header_winner_flag_only_when_final():
    # COMPLETED is a finished BO3 -> the 2-1 winner is flagged, loser is not
    d = parse_match(load(COMPLETED))
    assert d["status"] == "final"
    won = {t["name"]: t["won"] for t in d["teams"]}
    assert won == {"ABACATUDOS": True, "Team Liquid Brazil": False}


# ---------- maps ----------
def test_maps_names_pick_decider_and_scores():
    d = parse_match(load(COMPLETED))
    assert len(d["maps"]) == 3
    by_name = {m["name"]: m for m in d["maps"]}
    assert set(by_name) == {"Lotus", "Breeze", "Split"}
    # two picked maps + exactly one decider (neither team picked it)
    assert sum(1 for m in d["maps"] if m["decider"]) == 1
    assert sum(1 for m in d["maps"] if m["picked"]) == 2
    assert by_name["Split"]["decider"] is True and by_name["Split"]["picked"] is False
    assert by_name["Lotus"]["scores"] == [13.0, 9.0]  # [team1, team2]
    # every map has both teams with five players each
    for m in d["maps"]:
        assert [len(t["players"]) for t in m["teams"]] == [5, 5]


def test_all_maps_aggregate_present():
    d = parse_match(load(COMPLETED))
    assert d["all_maps"] is not None
    assert [len(t["players"]) for t in d["all_maps"]["teams"]] == [5, 5]


# ---------- rounds timeline ----------
def test_round_timeline_structure():
    d = parse_match(load(COMPLETED))
    split = next(m for m in d["maps"] if m["name"] == "Split")
    rounds = split["rounds"]
    # the round grid always reserves 24 columns; a map that finished in fewer
    # rounds (13-8 = 21 played) leaves the trailing slots as unplayed (winner None)
    assert len(rounds) == 24
    r1 = rounds[0]
    assert r1["round"] == 1
    assert r1["winner"] in (1, 2)
    assert r1["side"] in ("t", "ct")
    assert isinstance(r1["outcome"], str) and r1["outcome"]  # elim/boom/defuse/time
    assert r1["score"] == "1-0"  # cumulative team1-team2 after round 1
    assert rounds[20]["winner"] is not None  # round 21 = the deciding round, played
    assert all(rr["winner"] is None for rr in rounds[21:])  # unplayed trailing slots


# ---------- scoreboard: THE concatenation proof ----------
def test_value_reads_mod_both_not_concatenation():
    """K=28 in span.mod-both, but the raw cell text concatenates both/t/ct into
    "281810" — a number that coerces fine and is silently WRONG. Prove we read
    the combined span, not the raw cell."""
    html = load(COMPLETED)
    tree = HTMLParser(html)
    game = tree.css("div.vm-stats-game")[0]
    row = [
        r for r in game.css("div.ovw-table")[0].css("div.ovw-row")
        if "mod-head" not in (r.attributes.get("class") or "")
    ][0]
    kcell = next(n for n in row.css("[data-col]") if n.attributes.get("data-col") == "kills")
    assert kcell.text(strip=True) == "281810"  # the dangerous concatenation

    p = parse_match(html)["maps"][0]["teams"][0]["players"][0]
    assert p["player"] == "frozeN" and p["agent"] == "jett"
    k = p["stats"]["K"]
    assert k["both"] == "28" and k["value"] == 28.0 and k["value"] != 281810.0
    assert k["t"] == "18" and k["ct"] == "10"  # side-splits preserved, not discarded


def test_percent_columns_parsed():
    stats = parse_match(load(COMPLETED))["maps"][0]["teams"][0]["players"][0]["stats"]
    assert stats["KAST"]["both"] and stats["KAST"]["both"].endswith("%")
    assert isinstance(stats["KAST"]["value"], float)
    assert stats["HS%"]["both"] and stats["HS%"]["both"].endswith("%")
    assert isinstance(stats["HS%"]["value"], float)


def test_partial_empty_stats_are_null():
    """vlr sometimes computes K/D/A live before R/ACS/ADR are ready -- the empty
    spans must coerce to None, never NaN or a crash. No live in-progress match
    was available at capture time, so this reconstructs that real, observed shape
    (div-grid scoreboard, R/ACS/ADR spans present but empty) directly."""
    html = """
    <div class="vm-stats-game" data-game-id="1">
      <div class="ovw-table">
        <div class="ovw-row mod-head">
          <div class="ovw-th"></div>
          <div class="ovw-th" data-col="rating2">R</div>
          <div class="ovw-th" data-col="acs">ACS</div>
          <div class="ovw-th mod-kda">
            <span class="ovw-kda-stat" data-col="kills">K</span>/<span class="ovw-kda-stat" data-col="deaths">D</span>/<span class="ovw-kda-stat" data-col="assists">A</span>
          </div>
          <div class="ovw-th" data-col="adr">ADR</div>
        </div>
        <div class="ovw-row">
          <div class="ovw-cell mod-player">
            <div class="ovw-player">
              <i class="flag mod-us" title="United States"></i>
              <a href="/player/1/testplayer">
                <div class="ovw-player-name text-of">TestPlayer</div>
                <div class="ovw-player-tag ge-text-light">TST</div>
              </a>
            </div>
            <div class="ovw-agents"><span class="stats-sq mod-agent small"><img src="/img/vlr/game/agents/jett.png" alt="jett"></span></div>
          </div>
          <div class="ovw-cell" data-col="rating2"><span class="stats-sq"><span class="side mod-both"></span><span class="side mod-t"></span><span class="side mod-ct"></span></span></div>
          <div class="ovw-cell" data-col="acs"><span class="stats-sq"><span class="side mod-both"></span><span class="side mod-t"></span><span class="side mod-ct"></span></span></div>
          <div class="ovw-cell mod-kda">
            <span class="stats-sq mod-kda">
              <span class="ovw-kda-stat" data-col="kills"><span class="side mod-both">12</span><span class="side mod-t">7</span><span class="side mod-ct">5</span></span>/
              <span class="ovw-kda-stat" data-col="deaths"><span class="side mod-both">10</span><span class="side mod-t">4</span><span class="side mod-ct">6</span></span>/
              <span class="ovw-kda-stat" data-col="assists"><span class="side mod-both">3</span><span class="side mod-t">1</span><span class="side mod-ct">2</span></span>
            </span>
          </div>
          <div class="ovw-cell" data-col="adr"><span class="stats-sq"><span class="side mod-both"></span><span class="side mod-t"></span><span class="side mod-ct"></span></span></div>
        </div>
      </div>
    </div>"""
    stats = parse_match(html)["maps"][0]["teams"][0]["players"][0]["stats"]
    for empty_key in ("R", "ACS", "ADR"):
        assert stats[empty_key]["both"] is None
        assert stats[empty_key]["value"] is None  # not NaN, not 0
    for live_key in ("K", "D", "A"):
        assert isinstance(stats[live_key]["value"], float)


def test_kd_and_fk_diff_keys_distinct():
    stats = parse_match(load(COMPLETED))["maps"][0]["teams"][0]["players"][0]["stats"]
    assert "KD_+/-" in stats and "FK_+/-" in stats


# ---------- streams (Twitch channel logins) ----------
def test_streams_parse_twitch_logins_from_data_site_id():
    """The banked fixture carries the official-broadcast streams strip; the Twitch
    login comes straight off data-site-id (the bare Helix user_login)."""
    d = parse_match(load(COMPLETED))
    assert isinstance(d["streams"], list) and d["streams"]
    assert all(isinstance(s, str) and s.strip() for s in d["streams"])
    # Twitch-only: YouTube/SOOP/etc. (no data-site-id, no twitch.tv link) are skipped
    assert all("youtube" not in s.lower() and "/" not in s for s in d["streams"])
    # de-duped, no empties
    assert len(d["streams"]) == len(set(d["streams"]))


def test_streams_href_fallback_when_data_site_id_missing():
    """A mod-embed entry without data-site-id falls back to the external twitch.tv
    href's last path segment."""
    html = """
    <div class="match-streams-container">
      <div class="match-streams-btn mod-embed">
        <div class="match-streams-btn-embed">no data-site-id here</div>
        <a class="match-streams-btn-external" href="https://www.twitch.tv/fallback_chan?x=1">x</a>
      </div>
    </div>"""
    assert parse_match(html)["streams"] == ["fallback_chan"]


def test_streams_dedupe_and_skip_non_twitch():
    """The same channel listed twice collapses to one; a non-Twitch mod-embed entry
    (no data-site-id, no twitch.tv link) is dropped, not emitted as empty/None."""
    html = """
    <div class="match-streams-container">
      <div class="match-streams-btn mod-embed">
        <div class="match-streams-btn-embed" data-site-id="valorant">v</div>
        <a class="match-streams-btn-external" href="https://www.twitch.tv/valorant">x</a>
      </div>
      <div class="match-streams-btn mod-embed">
        <div class="match-streams-btn-embed" data-site-id="valorant">dup</div>
      </div>
      <div class="match-streams-btn mod-embed">
        <div class="match-streams-btn-embed">no id</div>
        <a class="match-streams-btn-external" href="https://www.youtube.com/@x/live">y</a>
      </div>
    </div>"""
    assert parse_match(html)["streams"] == ["valorant"]


def test_streams_empty_is_valid():
    """A match page with no Twitch streams -> empty list, never None, never a crash."""
    assert parse_match("<html><body>no streams here</body></html>")["streams"] == []


# ---------- cross-cutting invariants ----------
def test_all_player_values_finite_or_none():
    d = parse_match(load(COMPLETED))
    groups = [t for m in d["maps"] for t in m["teams"]] + d["all_maps"]["teams"]
    for g in groups:
        for p in g["players"]:
            assert isinstance(p["player"], str) and p["player"].strip()
            for cell in p["stats"].values():
                v = cell["value"]
                assert v is None or (isinstance(v, float) and v == v)  # NaN guard
