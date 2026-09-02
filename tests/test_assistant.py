"""Assistant orchestration — the name-driven LIVE > NEXT > LAST answer.

Pure helpers (round counting, current-map pick, live-card matching, shaping) test
on plain dicts; the orchestrator is exercised with the name resolver and the
cache-first detail reads mocked, so the suite never touches a DB or vlr.gg. The
round-score null-stub rule is asserted directly — that is the whole point of the
LIVE branch and the one bit of logic vlr's markup actively tries to trip.
"""
from app.services import assistant as A


# ---- fixtures (plain dicts shaped like the real scraper output) --------------
def _round(winner):
    """A played round (winner 1|2) or a trailing null-stub (winner None)."""
    if winner is None:
        return {"round": None, "winner": None, "side": None, "outcome": None, "score": None}
    return {"round": 1, "winner": winner, "side": "t", "outcome": "elim", "score": "x"}


def _live_map(name, t1_wins, t2_wins, null_stub=True):
    """A map with t1_wins rounds for team1, t2_wins for team2, and (by default) a
    trailing not-yet-played null-stub round appended."""
    rounds = [_round(1)] * t1_wins + [_round(2)] * t2_wins
    if null_stub:
        rounds.append(_round(None))
    return {"name": name, "rounds": rounds, "teams": [{"name": "A"}, {"name": "B"}]}


def _match_detail():
    """Sentinels (id 2, side 0) vs NRG (id 1034, side 1), live on Ascent: map score
    1-0, current map 4 rounds SEN to 2 NRG, plus a trailing null stub."""
    return {
        "id": "500",
        "url": "https://www.vlr.gg/500",
        "event": "VCT Champions",
        "series": "Grand Final",
        "format": "BO5",
        "status": "live",
        "teams": [
            {"name": "Sentinels", "id": "2", "score": 1},
            {"name": "NRG", "id": "1034", "score": 0},
        ],
        "maps": [
            _live_map("Sunset", 13, 9, null_stub=False),   # completed earlier map
            _live_map("Ascent", 4, 2, null_stub=True),      # the live map
        ],
    }


def _live_card():
    return {"id": "500", "teams": ["Sentinels", "NRG"], "scores": ["1", "0"], "status": "live"}


TEAM = {"id": "2", "name": "Sentinels", "tag": "SEN"}


# ---- pure: round counting (the null-stub rule) ------------------------------
def test_count_map_rounds_skips_trailing_null_stub():
    # 6 played rounds (4 + 2) plus 1 null stub -> totals sum to 6, never 7
    m = _live_map("Ascent", 4, 2, null_stub=True)
    t1, t2 = A.count_map_rounds(m)
    assert (t1, t2) == (4, 2)
    assert t1 + t2 == 6


def test_count_map_rounds_empty_and_all_null_is_zero():
    assert A.count_map_rounds({"rounds": []}) == (0, 0)
    assert A.count_map_rounds({"rounds": [_round(None), _round(None)]}) == (0, 0)


def test_pick_current_map_is_last_with_played_rounds():
    m = A.pick_current_map(_match_detail())
    assert m is not None and m["name"] == "Ascent"


def test_pick_current_map_none_when_no_played_rounds():
    detail = {"maps": [{"name": "Ascent", "rounds": [_round(None)]}]}
    assert A.pick_current_map(detail) is None


# ---- pure: side alignment ----------------------------------------------------
def test_team_side_index_prefers_id():
    d = _match_detail()
    assert A._team_side_index(d, "1034", "NRG") == 1  # NRG is side 1
    assert A._team_side_index(d, "2", "Sentinels") == 0


def test_team_side_index_falls_back_to_name_then_zero():
    d = _match_detail()
    assert A._team_side_index(d, None, "NRG") == 1  # id absent -> name match
    assert A._team_side_index(d, "999", "Nobody") == 0  # no match -> default side 0


# ---- pure: live-card matching -----------------------------------------------
def test_find_live_card_exact_and_contains():
    cards = [{"id": "500", "teams": ["Sentinels", "NRG"]}]
    assert A.find_live_card_for_team(cards, "sentinels")["id"] == "500"  # case-insensitive
    assert A.find_live_card_for_team(cards, "NRG Esports")["id"] == "500"  # contains


def test_find_live_card_none_when_absent():
    cards = [{"id": "9", "teams": ["Fnatic", "LOUD"]}]
    assert A.find_live_card_for_team(cards, "Sentinels") is None
    assert A.find_live_card_for_team([], "Sentinels") is None


# ---- pure: shaping -----------------------------------------------------------
def test_shape_live_orients_round_score_to_the_team():
    ans = A.shape_live(TEAM, _match_detail(), _live_card())
    assert ans["state"] == "live"
    m = ans["match"]
    assert m["opponent"] == "NRG"
    assert m["map_score"] == {"team": 1, "opponent": 0}
    assert m["current_map"]["name"] == "Ascent"
    # SEN is side 0 -> team=4, opponent=2 (not 5/3 — the null stub was skipped)
    assert m["current_map"]["round_score"] == {"team": 4, "opponent": 2}


def test_shape_live_orients_to_the_opponent_when_team_is_side_two():
    nrg = {"id": "1034", "name": "NRG", "tag": "NRG"}
    ans = A.shape_live(nrg, _match_detail(), _live_card())
    m = ans["match"]
    assert m["opponent"] == "Sentinels"
    assert m["map_score"] == {"team": 0, "opponent": 1}
    assert m["current_map"]["round_score"] == {"team": 2, "opponent": 4}


def test_shape_upcoming_and_completed():
    up = A.shape_upcoming(TEAM, {"id": "7", "opponent": "LOUD", "event": "VCT", "date": "Sep 5"})
    assert up["state"] == "upcoming" and up["match"]["opponent"] == "LOUD"
    assert up["match"]["status"] == "upcoming"
    done = A.shape_completed(TEAM, {"id": "6", "opponent": "G2", "score": "2:1", "result": "win", "event": "VCT"})
    assert done["state"] == "completed" and done["match"]["result"] == "win"
    assert done["match"]["score"] == "2:1"


# ---- orchestrator: priority LIVE > NEXT > LAST, envelope, graceful -----------
def _resolve(team):
    async def fake(name):
        return {"data": [team] if team else [], "stale": False, "error": None}
    return fake


async def test_not_found_returns_clean_envelope(monkeypatch):
    monkeypatch.setattr(A, "search_teams", _resolve(None))
    res = await A.team_match("no such org")
    assert res["error"] and "not found" in res["error"]
    assert res["data"]["state"] == "none" and res["data"]["team"] is None


async def test_live_priority_returns_live_with_round_score(monkeypatch):
    monkeypatch.setattr(A, "search_teams", _resolve(TEAM))

    async def live_list():
        return [_live_card()]

    async def match_detail(mid):
        assert mid == "500"
        return _match_detail()

    async def no_team(tid):
        raise AssertionError("team detail must not be read when a live match exists")

    monkeypatch.setattr(A, "_get_live_list", live_list)
    monkeypatch.setattr(A, "_get_match_detail", match_detail)
    monkeypatch.setattr(A, "_get_team_detail", no_team)

    res = await A.team_match("Sentinels")
    assert res["error"] is None
    body = res["data"]
    assert body["state"] == "live"
    assert body["match"]["current_map"]["round_score"] == {"team": 4, "opponent": 2}


async def test_upcoming_when_no_live(monkeypatch):
    monkeypatch.setattr(A, "search_teams", _resolve(TEAM))

    async def no_live():
        return []  # nothing live -> fall through

    async def team_detail(tid):
        assert tid == "2"
        return {"upcoming": [{"id": "7", "opponent": "LOUD", "event": "VCT", "date": "Sep 5"}],
                "results": [{"id": "6", "opponent": "G2", "score": "2:1", "result": "win"}]}

    monkeypatch.setattr(A, "_get_live_list", no_live)
    monkeypatch.setattr(A, "_get_team_detail", team_detail)

    res = await A.team_match("Sentinels")
    assert res["data"]["state"] == "upcoming"
    assert res["data"]["match"]["opponent"] == "LOUD"


async def test_completed_when_no_live_no_upcoming(monkeypatch):
    monkeypatch.setattr(A, "search_teams", _resolve(TEAM))

    async def no_live():
        return []

    async def team_detail(tid):
        return {"upcoming": [], "results": [{"id": "6", "opponent": "G2", "score": "2:1", "result": "win"}]}

    monkeypatch.setattr(A, "_get_live_list", no_live)
    monkeypatch.setattr(A, "_get_team_detail", team_detail)

    res = await A.team_match("Sentinels")
    assert res["data"]["state"] == "completed"
    assert res["data"]["match"]["opponent"] == "G2" and res["data"]["match"]["result"] == "win"


async def test_none_when_team_has_no_matches_at_all(monkeypatch):
    monkeypatch.setattr(A, "search_teams", _resolve(TEAM))

    async def no_live():
        return []

    async def team_detail(tid):
        return {"upcoming": [], "results": []}

    monkeypatch.setattr(A, "_get_live_list", no_live)
    monkeypatch.setattr(A, "_get_team_detail", team_detail)

    res = await A.team_match("Sentinels")
    assert res["data"]["state"] == "none" and res["data"]["team"]["id"] == "2"
    assert res["error"] is None  # resolved fine, just quiet — not an error


async def test_live_lookup_failure_degrades_and_falls_through(monkeypatch):
    monkeypatch.setattr(A, "search_teams", _resolve(TEAM))

    async def boom_live():
        raise RuntimeError("redis down")

    async def team_detail(tid):
        return {"upcoming": [{"id": "7", "opponent": "LOUD"}], "results": []}

    monkeypatch.setattr(A, "_get_live_list", boom_live)
    monkeypatch.setattr(A, "_get_team_detail", team_detail)

    res = await A.team_match("Sentinels")
    # live branch failed -> stale flagged, but the NEXT match still answers
    assert res["data"]["state"] == "upcoming"
    assert res["stale"] is True and "redis down" in res["error"]
