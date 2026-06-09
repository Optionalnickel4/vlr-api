from pathlib import Path

from app.scrapers.teams import parse_team

FIX = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIX / name).read_text()


# ---------- team detail (Sentinels, id 2) ----------
# These assert STRUCTURE + INVARIANTS only — never volatile values (roster, records
# and match list all change over time), so the suite stays green as the team moves.
def test_parse_team_identity():
    t = parse_team(load("team_sentinels.html"))
    assert t["id"] and t["id"].isdigit()
    assert isinstance(t["name"], str) and t["name"].strip()
    # tag is a short uppercase-ish code; present on a real team page
    assert isinstance(t["tag"], str) and t["tag"].strip()
    # country code is a short token parsed off the header flag class
    assert isinstance(t["country_code"], str) and t["country_code"].strip()


def test_parse_team_logo_is_absolute():
    t = parse_team(load("team_sentinels.html"))
    assert isinstance(t["logo"], str) and t["logo"].startswith("https://")


def test_parse_team_roster_structure():
    t = parse_team(load("team_sentinels.html"))
    roster = t["roster"]
    assert isinstance(roster, list) and len(roster) > 0
    for m in roster:
        # every member has a non-empty alias and a numeric player id
        assert isinstance(m["alias"], str) and m["alias"].strip()
        assert m["player_id"] and m["player_id"].isdigit()
        assert m["url"].startswith("https://www.vlr.gg/player/")
        # role is either absent (active player) or a non-empty descriptor
        assert m["role"] is None or (isinstance(m["role"], str) and m["role"].strip())
        assert isinstance(m["is_captain"], bool)
        assert isinstance(m["is_staff"], bool)


def test_parse_team_roster_alias_has_no_label_bleed():
    # the alias node nests a flag <i> and an optional captain-star <i>; the alias
    # must be just the handle, never the real name or a role glued on.
    t = parse_team(load("team_sentinels.html"))
    for m in t["roster"]:
        if m["real_name"]:
            assert m["real_name"] not in m["alias"]
        if m["role"]:
            assert m["role"] not in m["alias"]


def test_parse_team_distinguishes_players_and_staff():
    # vlr groups the roster into "players" and "staff"; the parse must surface both
    # via is_staff, and at least one active player must exist.
    t = parse_team(load("team_sentinels.html"))
    assert any(not m["is_staff"] for m in t["roster"])


def test_parse_team_results_structure():
    t = parse_team(load("team_sentinels.html"))
    results = t["results"]
    assert isinstance(results, list) and len(results) > 0
    for m in results:
        assert m["id"] and m["id"].isdigit()
        assert m["url"].startswith("https://www.vlr.gg/")
        assert isinstance(m["opponent"], str) and m["opponent"].strip()
        # a completed result is always win or loss (the split guarantees it)
        assert m["result"] in {"win", "loss"}
        assert isinstance(m["event"], str) and m["event"].strip()


def test_parse_team_result_event_has_no_series_bleed():
    # the m-item-event container trails series/stage text after the name div; the
    # descendant selector must pick the name only, not the concatenated blob.
    t = parse_team(load("team_sentinels.html"))
    for m in t["results"]:
        assert "\n" not in m["event"]
        # the series suffix (e.g. "Stage 2 ⋅ LR2") would bleed extra words in; the
        # event name on this fixture is short — guard against an obvious run-on.
        assert "⋅" not in m["event"]


def test_parse_team_upcoming_is_a_list():
    # upcoming may be empty out of season — that is valid, not a failure.
    t = parse_team(load("team_sentinels.html"))
    assert isinstance(t["upcoming"], list)
    for m in t["upcoming"]:
        assert m["id"] and m["id"].isdigit()
        assert isinstance(m["opponent"], str)
        # upcoming cards have no decided result
        assert m["result"] is None
