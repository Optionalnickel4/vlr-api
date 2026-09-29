"""Shared team-identity enrichment: stable IDs first, one batched cache read."""

from app.services import team_identity as I


RANKINGS = [
    {"team_id": "13576", "team": "JD Gaming", "logo": "https://cdn/jdg.png", "country": "China"},
    {"team_id": "1184", "team": "FUT Esports", "logo": "https://cdn/fut.png", "country": "Europe"},
]


async def test_match_enrichment_prefers_cached_detail_ids_and_batches(monkeypatch):
    rows = [{"id": "753445", "teams": ["JD Gaming", "FUT Esports"], "scores": ["0", "2"]}]
    detail = {"teams": [
        {"id": "13576", "name": "JD Gaming", "logo": "https://detail/jdg.png"},
        {"id": "1184", "name": "FUT Esports", "logo": "https://detail/fut.png"},
    ]}
    calls = []

    async def cache_get(key):
        return RANKINGS

    async def cache_get_many(keys):
        calls.append(keys)
        return [detail]

    monkeypatch.setattr(I, "cache_get", cache_get)
    monkeypatch.setattr(I, "cache_get_many", cache_get_many)
    got = await I.enrich_match_cards(rows)

    assert calls == [["vlr:match:753445"]]
    assert got[0]["team_ids"] == ["13576", "1184"]
    assert got[0]["team_logos"] == ["https://detail/jdg.png", "https://detail/fut.png"]
    assert got[0]["scores"] == ["0", "2"]


async def test_match_enrichment_uses_exact_ranked_name_only_without_detail(monkeypatch):
    async def cache_get(key):
        return RANKINGS

    async def cache_get_many(keys):
        return [None]

    monkeypatch.setattr(I, "cache_get", cache_get)
    monkeypatch.setattr(I, "cache_get_many", cache_get_many)
    got = await I.enrich_match_cards([{"id": "x", "teams": ["JD Gaming", "FUT Esports"]}])
    assert got[0]["team_ids"] == ["13576", "1184"]
    assert got[0]["team_logos"] == ["https://cdn/jdg.png", "https://cdn/fut.png"]


async def test_old_cached_match_identity_keeps_ids_and_backfills_ranked_logos(monkeypatch):
    async def cache_get(key):
        return RANKINGS

    async def cache_get_many(keys):
        return [{"teams": [
            {"id": "13576", "name": "JD Gaming"},
            {"id": "1184", "name": "FUT Esports"},
        ]}]

    monkeypatch.setattr(I, "cache_get", cache_get)
    monkeypatch.setattr(I, "cache_get_many", cache_get_many)
    got = await I.enrich_match_cards([{"id": "753445", "teams": ["JD Gaming", "FUT Esports"]}])
    assert got[0]["team_ids"] == ["13576", "1184"]
    assert got[0]["team_logos"] == ["https://cdn/jdg.png", "https://cdn/fut.png"]


async def test_enrichment_failure_returns_valid_match_payload_unchanged(monkeypatch):
    original = [{"id": "753445", "teams": ["JD Gaming", "FUT Esports"], "scores": ["0", "2"]}]

    async def fail(key):
        raise RuntimeError("redis unavailable")

    monkeypatch.setattr(I, "cache_get", fail)
    got = await I.enrich_match_cards(original)
    assert got == original
    assert got is original


async def test_team_history_gets_stable_opponent_identity_without_losing_rows(monkeypatch):
    async def cache_get(key):
        return RANKINGS

    async def cache_get_many(keys):
        return [None]

    monkeypatch.setattr(I, "cache_get", cache_get)
    monkeypatch.setattr(I, "cache_get_many", cache_get_many)
    detail = {"id": "13576", "name": "JD Gaming", "logo": "https://cdn/jdg.png", "results": [
        {"id": "753445", "opponent": "FUT Esports", "score": "0:2"},
    ], "upcoming": []}
    got = await I.enrich_team_detail(detail)
    assert got["results"][0]["opponent_id"] == "1184"
    assert got["results"][0]["opponent_logo"] == "https://cdn/fut.png"
    assert got["results"][0]["score"] == "0:2"


async def test_regional_rankings_use_team_detail_then_world_logo_in_one_batch(monkeypatch):
    calls = []

    async def cache_get(key):
        return RANKINGS

    async def cache_get_many(keys):
        calls.append(keys)
        return [{"id": "13576", "logo": "https://team/jdg.png"}, None]

    monkeypatch.setattr(I, "cache_get", cache_get)
    monkeypatch.setattr(I, "cache_get_many", cache_get_many)
    rows = [
        {"team_id": "13576", "team": "JD Gaming", "logo": None},
        {"team_id": "1184", "team": "FUT Esports", "logo": None},
    ]
    got = await I.enrich_rankings(rows)

    assert calls == [["vlr:team:13576", "vlr:team:1184"]]
    assert got[0]["logo"] == "https://team/jdg.png"
    assert got[1]["logo"] == "https://cdn/fut.png"


async def test_rankings_enrichment_failure_preserves_valid_rows(monkeypatch):
    original = [{"team_id": "13576", "team": "JD Gaming", "rank": "1"}]

    async def fail(key):
        raise RuntimeError("redis unavailable")

    monkeypatch.setattr(I, "cache_get", fail)
    assert await I.enrich_rankings(original) is original
