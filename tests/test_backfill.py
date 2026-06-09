"""Pure-function tests for phase-5 backfill: team-results persistence shaping and
migration idempotency. No DB, no network — same contract as the other suites.
"""
from app.core.migrations import migration_statements
from app.services.refresh import _split_score, team_results_to_match_rows


# ---- score split ------------------------------------------------------------
def test_split_score_keeps_raw_halves():
    assert _split_score("2:1") == ("2", "1")
    assert _split_score("1:2") == ("1", "2")


def test_split_score_is_defensive():
    # malformed / missing -> (None, None), never raises (coercion is read-time)
    assert _split_score(None) == (None, None)
    assert _split_score("") == (None, None)
    assert _split_score("TBD") == (None, None)


# ---- team-results persistence shaping ---------------------------------------
def _parsed_results():
    # shaped exactly like teams.parse_team()["results"] entries
    return [
        {"id": "681336", "opponent": "LOUD", "opponent_id": "13", "result": "loss",
         "score": "1:2", "event": "EWC 2026: AMER Qualifier",
         "url": "https://www.vlr.gg/681336/loud-vs-sentinels"},
        {"id": "681334", "opponent": "KRÜ Esports", "opponent_id": None,
         "result": "win", "score": "2:1", "event": "EWC 2026: AMER Qualifier",
         "url": "https://www.vlr.gg/681334/sentinels-vs-kru"},
        {"id": None, "opponent": "X", "opponent_id": None, "result": "win",
         "score": "1:0", "event": "x", "url": "u"},  # no vlr id -> dropped
    ]


def test_shaping_sets_page_team_and_opponent_ids():
    rows = team_results_to_match_rows("2", "Sentinels", _parsed_results())
    # the row without a vlr id is dropped (can't dedup it)
    assert [r["vlr_id"] for r in rows] == ["681336", "681334"]
    r0 = rows[0]
    # page team is side A and always carries its id; opponent is side B
    assert r0["team_a"] == "Sentinels" and r0["team_a_id"] == "2"
    assert r0["team_b"] == "LOUD" and r0["team_b_id"] == "13"
    # scores stored as RAW text, left:right, page-team first
    assert r0["score_a"] == "1" and r0["score_b"] == "2"
    assert r0["event"] == "EWC 2026: AMER Qualifier"
    assert r0["url"].startswith("https://www.vlr.gg/")


def test_shaping_opponent_id_null_does_not_crash():
    rows = team_results_to_match_rows("2", "Sentinels", _parsed_results())
    # opponent id absent on the card -> null on the row, page team id still set
    assert rows[1]["team_b_id"] is None
    assert rows[1]["team_a_id"] == "2"
    assert rows[1]["score_a"] == "2" and rows[1]["score_b"] == "1"


def test_shaping_every_row_carries_the_dedup_key():
    rows = team_results_to_match_rows("2", "Sentinels", _parsed_results())
    assert rows and all(r["vlr_id"] for r in rows)  # vlr_id is the on-conflict key


# ---- migration idempotency --------------------------------------------------
def test_migration_statements_are_idempotent_by_construction():
    stmts = migration_statements()
    # deterministic: running the generator twice yields the same SQL (safe to repeat)
    assert stmts == migration_statements()
    # every statement is IF NOT EXISTS -> re-applying the whole list is a no-op
    assert all("IF NOT EXISTS" in s for s in stmts)


def test_migration_adds_both_id_columns_without_dropping():
    joined = " ".join(migration_statements()).lower()
    assert "team_a_id" in joined and "team_b_id" in joined
    # must NEVER drop/recreate the table that holds banked history
    assert "drop table" not in joined and "drop column" not in joined
