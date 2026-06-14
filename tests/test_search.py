"""Player search — hybrid DB-first + VLR-autocomplete fallback.

Pure helpers (the statement shape, the autocomplete parser) test without a DB or
network; the orchestrator is exercised with both sources mocked. The actual
ILIKE/DISTINCT-ON semantics are container-verified — the suite never hits Postgres
or vlr.gg (same discipline as the other suites).
"""
import json

from sqlalchemy.dialects import postgresql

from app.services import search as S


# ---- primary: the DB statement shape (compiled, no live DB) -----------------
def _sql(q: str, cap: int = 12) -> str:
    stmt = S.db_search_stmt(q, cap)
    return str(
        stmt.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    ).lower()


def test_db_stmt_ilikes_alias_and_real_name():
    sql = _sql("ten")
    assert "ilike" in sql
    assert "alias" in sql and "real_name" in sql  # matches on BOTH name columns
    assert "%ten%" in sql


def test_db_stmt_is_distinct_latest_per_player_and_capped():
    sql = _sql("ten", cap=5)
    # DISTINCT ON player_id + ORDER BY player_id, captured_at DESC == latest snapshot
    assert "distinct on" in sql and "player_id" in sql
    assert "captured_at" in sql and "desc" in sql
    assert "limit 5" in sql


# ---- fallback: the autocomplete parser (pure) -------------------------------
REAL_AUTO = json.dumps(
    [
        {"id": "#", "value": "players", "label": "<div>Players</div>"},  # header -> skip
        {"id": "/search/r/player/9/ac", "value": "TenZ", "label": "<a>TenZ</a>"},
        {"id": "/search/r/player/29839/ac", "value": "TenTen", "label": "x"},
        {"id": "#", "value": "events", "label": "x"},  # header -> skip
        {"id": "/search/r/event/123/x", "value": "Champions", "label": "x"},  # event -> skip
        {"id": "#", "value": "teams", "label": "x"},  # header -> skip
        {"id": "/search/r/team/2/sen", "value": "Sentinels", "label": "x"},  # team -> skip
    ]
)


def test_parse_autocomplete_keeps_players_skips_categories_events_teams():
    hits = S.parse_vlr_autocomplete(REAL_AUTO)
    assert [(h["id"], h["alias"]) for h in hits] == [("9", "TenZ"), ("29839", "TenTen")]
    assert all(h["source"] == "vlr" for h in hits)


def test_parse_autocomplete_dedupes_by_id_and_caps():
    dupe = json.dumps(
        [
            {"id": "/search/r/player/9/ac", "value": "TenZ"},
            {"id": "/search/r/player/9/zz", "value": "TenZ again"},  # same id -> deduped
            {"id": "/search/r/player/10/x", "value": "Two"},
            {"id": "/search/r/player/11/x", "value": "Three"},
        ]
    )
    assert [h["id"] for h in S.parse_vlr_autocomplete(dupe, cap=2)] == ["9", "10"]


def test_parse_autocomplete_bad_or_nonlist_json_is_empty():
    assert S.parse_vlr_autocomplete("not json at all") == []
    assert S.parse_vlr_autocomplete("{}") == []  # a dict, not a list


# ---- orchestrator: DB-first, fallback, cache, graceful ----------------------
async def test_min_length_guard_returns_empty_without_touching_db(monkeypatch):
    async def boom(*a, **k):
        raise AssertionError("db_search must not run for a too-short query")

    monkeypatch.setattr(S, "db_search", boom)
    assert await S.search_players("t") == {"data": [], "stale": False, "error": None}
    assert await S.search_players("  ") == {"data": [], "stale": False, "error": None}


async def test_db_hit_returns_db_source_and_skips_fallback(monkeypatch):
    async def fake_db(q, cap):
        return [{"id": "9", "alias": "TenZ", "team": "SEN", "country": "ca", "source": "db"}]

    async def no_vlr(*a, **k):
        raise AssertionError("VLR fallback must not run on a DB hit")

    monkeypatch.setattr(S, "db_search", fake_db)
    monkeypatch.setattr(S, "vlr_fallback", no_vlr)
    res = await S.search_players("tenz")
    assert res["stale"] is False and res["error"] is None
    assert res["data"][0]["id"] == "9" and res["data"][0]["source"] == "db"


async def test_empty_db_triggers_vlr_fallback(monkeypatch):
    calls = {"html": 0}

    async def empty_db(q, cap):
        return []

    async def miss(key):
        return None

    async def noop_set(key, val, ttl):
        return None

    class FakeClient:
        async def get_html(self, path):
            calls["html"] += 1
            assert "term=tenz" in path
            return REAL_AUTO

    monkeypatch.setattr(S, "db_search", empty_db)
    monkeypatch.setattr(S, "cache_get", miss)
    monkeypatch.setattr(S, "cache_set", noop_set)
    monkeypatch.setattr(S, "get_client", lambda: FakeClient())

    res = await S.search_players("tenz")
    assert [h["id"] for h in res["data"]] == ["9", "29839"]
    assert all(h["source"] == "vlr" for h in res["data"])
    assert calls["html"] == 1


async def test_fallback_is_cached_second_identical_miss_does_not_refetch(monkeypatch):
    store: dict[str, object] = {}
    calls = {"html": 0}

    async def empty_db(q, cap):
        return []

    async def fake_get(key):
        return store.get(key)

    async def fake_set(key, val, ttl):
        store[key] = val

    class FakeClient:
        async def get_html(self, path):
            calls["html"] += 1
            return REAL_AUTO

    monkeypatch.setattr(S, "db_search", empty_db)
    monkeypatch.setattr(S, "cache_get", fake_get)
    monkeypatch.setattr(S, "cache_set", fake_set)
    monkeypatch.setattr(S, "get_client", lambda: FakeClient())

    await S.search_players("tenz")
    res2 = await S.search_players("tenz")  # same term -> served from cache
    assert calls["html"] == 1  # vlr hit exactly once
    assert [h["id"] for h in res2["data"]] == ["9", "29839"]


async def test_db_error_is_graceful_not_a_crash(monkeypatch):
    async def boom_db(q, cap):
        raise RuntimeError("pg down")

    monkeypatch.setattr(S, "db_search", boom_db)
    res = await S.search_players("tenz")
    assert res["data"] == [] and res["stale"] is True and "pg down" in res["error"]


async def test_vlr_fallback_failure_returns_graceful_empty(monkeypatch):
    async def empty_db(q, cap):
        return []

    async def miss(key):
        return None

    class FakeClient:
        async def get_html(self, path):
            raise RuntimeError("vlr 503")

    monkeypatch.setattr(S, "db_search", empty_db)
    monkeypatch.setattr(S, "cache_get", miss)
    monkeypatch.setattr(S, "get_client", lambda: FakeClient())
    res = await S.search_players("zzzobscure")
    assert res["data"] == [] and res["stale"] is True and "vlr 503" in res["error"]
