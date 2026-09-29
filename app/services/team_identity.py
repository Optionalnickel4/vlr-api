"""Failure-tolerant team identity joins for API payloads.

List cards expose team names but no links or artwork.  Rankings and match-detail
pages expose stable team IDs plus the same source-provided logos used by team
pages.  This module joins those cached datasets without scraping, preferring a
match's ID-bearing detail and falling back to an exact normalized ranking name
only when the list source supplied no ID.  Cache reads are batched; any cache
failure returns the original valid payload unchanged.
"""
from __future__ import annotations

from typing import Any

from app.core.cache import cache_get, cache_get_many

RANKINGS_KEY = "vlr:rankings:all"
MATCH_KEY = "vlr:match:{id}"
PLAYER_KEY = "vlr:player:{id}"
TEAM_KEY = "vlr:team:{id}"


def _name_key(value: object) -> str | None:
    if value is None:
        return None
    key = " ".join(str(value).split()).casefold()
    return key or None


def _identity(raw: dict[str, Any], *, ranking: bool = False) -> dict[str, Any]:
    name = raw.get("team") if ranking else raw.get("name")
    team_id = raw.get("team_id") if ranking else raw.get("id")
    short = raw.get("tag")
    return {
        "id": str(team_id) if team_id is not None else None,
        "name": name,
        "short_name": short,
        "logo": raw.get("logo"),
        "region": raw.get("country") if ranking else raw.get("country"),
    }


def _catalog(rankings: object) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_id: dict[str, dict[str, Any]] = {}
    by_name: dict[str, dict[str, Any]] = {}
    if not isinstance(rankings, list):
        return by_id, by_name
    for row in rankings:
        if not isinstance(row, dict):
            continue
        item = _identity(row, ranking=True)
        if item["id"]:
            by_id[item["id"]] = item
        key = _name_key(item["name"])
        if key:
            by_name[key] = item
    return by_id, by_name


def _detail_teams(detail: object) -> list[dict[str, Any]]:
    if not isinstance(detail, dict) or not isinstance(detail.get("teams"), list):
        return []
    return [_identity(t) for t in detail["teams"] if isinstance(t, dict)]


async def _load(match_ids: list[str]) -> tuple[
    dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]
]:
    rankings = await cache_get(RANKINGS_KEY)
    by_id, by_name = _catalog(rankings)
    unique_ids = list(dict.fromkeys(match_ids))
    details = await cache_get_many([MATCH_KEY.format(id=mid) for mid in unique_ids])
    by_match: dict[str, list[dict[str, Any]]] = {}
    for mid, detail in zip(unique_ids, details):
        teams: list[dict[str, Any]] = []
        for item in _detail_teams(detail):
            key = _name_key(item["name"])
            existing = by_id.get(item["id"]) if item["id"] else None
            existing = existing or (by_name.get(key) if key else None)
            if existing:
                # Older cached match details predate logo parsing.  Keep their
                # stable side identity while filling missing artwork/context
                # from the ranking catalog during the cache transition.
                item = {
                    field: item.get(field) if item.get(field) is not None else existing.get(field)
                    for field in {**existing, **item}
                }
            teams.append(item)
        by_match[mid] = teams
        for item in teams:
            if item["id"]:
                by_id[item["id"]] = item
            key = _name_key(item["name"])
            if key:
                by_name[key] = item
    return by_id, by_name, by_match


def _find(name: object, by_name: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    key = _name_key(name)
    return by_name.get(key) if key else None


async def enrich_match_cards(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add index-aligned team identity fields to live/upcoming/result cards."""
    try:
        ids = [str(r["id"]) for r in rows if r.get("id") is not None]
        _, by_name, by_match = await _load(ids)
    except Exception:
        return rows

    out: list[dict[str, Any]] = []
    for row in rows:
        names = list(row.get("teams") or [])[:2]
        mid = str(row.get("id")) if row.get("id") is not None else ""
        detail = by_match.get(mid) or []
        identities: list[dict[str, Any] | None] = []
        for index, name in enumerate(names):
            # Match detail preserves side order, so its stable ID wins.  Only a
            # missing detail falls back to the exact ranking name.
            identities.append(detail[index] if index < len(detail) else _find(name, by_name))
        enriched = dict(row)
        enriched["team_ids"] = [item.get("id") if item else None for item in identities]
        enriched["team_logos"] = [item.get("logo") if item else None for item in identities]
        enriched["team_short_names"] = [
            item.get("short_name") if item else name for item, name in zip(identities, names)
        ]
        out.append(enriched)
    return out


async def enrich_rankings(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fill regional ranking artwork by stable ID using two bounded cache reads.

    VLR's world table contains logos, while its regional table does not.  The
    team-detail cache is the authoritative fallback used by team pages.  One
    MGET covers the whole ranking rather than issuing a request for each row.
    """
    missing = [row for row in rows if not row.get("logo") and row.get("team_id") is not None]
    if not missing:
        return rows
    try:
        world = await cache_get(RANKINGS_KEY)
        by_id, _ = _catalog(world)
        ids = list(dict.fromkeys(
            str(row["team_id"]) for row in missing
        ))
        details = await cache_get_many([TEAM_KEY.format(id=team_id) for team_id in ids])
        detail_by_id = dict(zip(ids, details))
    except Exception:
        return rows

    out: list[dict[str, Any]] = []
    for row in rows:
        enriched = dict(row)
        team_id = str(row.get("team_id")) if row.get("team_id") is not None else None
        world_team = by_id.get(team_id) if team_id else None
        detail = detail_by_id.get(team_id) if team_id else None
        detail_logo = detail.get("logo") if isinstance(detail, dict) else None
        logo = enriched.get("logo") or detail_logo or (
            world_team.get("logo") if world_team else None
        )
        if logo:
            enriched["logo"] = logo
        out.append(enriched)
    return out


def _enrich_opponents(
    rows: list[dict[str, Any]], owner_id: str | None,
    by_name: dict[str, dict[str, Any]], by_match: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        mid = str(row.get("id")) if row.get("id") is not None else ""
        candidates = by_match.get(mid) or []
        opponent_key = _name_key(row.get("opponent"))
        item = next((t for t in candidates if _name_key(t.get("name")) == opponent_key), None)
        if item is None:
            item = next((t for t in candidates if owner_id and t.get("id") != owner_id), None)
        if item is None:
            item = _find(row.get("opponent"), by_name)
        enriched = dict(row)
        if item:
            enriched["opponent_id"] = enriched.get("opponent_id") or item.get("id")
            enriched["opponent_logo"] = enriched.get("opponent_logo") or item.get("logo")
            enriched["opponent_short_name"] = enriched.get("opponent_tag") or item.get("short_name")
        out.append(enriched)
    return out


async def enrich_team_detail(detail: dict[str, Any]) -> dict[str, Any]:
    rows = list(detail.get("results") or []) + list(detail.get("upcoming") or [])
    try:
        ids = [str(r["id"]) for r in rows if r.get("id") is not None]
        by_id, by_name, by_match = await _load(ids)
    except Exception:
        return detail
    out = dict(detail)
    own_id = str(detail.get("id")) if detail.get("id") is not None else None
    own = by_id.get(own_id) if own_id else None
    if own:
        out["logo"] = out.get("logo") or own.get("logo")
    if "results" in detail:
        out["results"] = _enrich_opponents(list(detail.get("results") or []), own_id, by_name, by_match)
    if "upcoming" in detail:
        out["upcoming"] = _enrich_opponents(list(detail.get("upcoming") or []), own_id, by_name, by_match)
    return out


async def enrich_player_detail(detail: dict[str, Any]) -> dict[str, Any]:
    rows = list(detail.get("matches") or [])
    try:
        ids = [str(r["id"]) for r in rows if r.get("id") is not None]
        by_id, by_name, by_match = await _load(ids)
    except Exception:
        return detail
    out = dict(detail)
    team_id = str(detail.get("team_id")) if detail.get("team_id") is not None else None
    own = by_id.get(team_id) if team_id else None
    if own:
        out["team_logo"] = out.get("team_logo") or own.get("logo")
    if "matches" in detail:
        out["matches"] = _enrich_opponents(rows, team_id, by_name, by_match)
    return out


async def enrich_stats(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach team identity from already-cached player details in one MGET."""
    try:
        player_ids = [str(r["player_id"]) for r in rows if r.get("player_id") is not None]
        unique = list(dict.fromkeys(player_ids))
        players = await cache_get_many([PLAYER_KEY.format(id=pid) for pid in unique])
        rankings = await cache_get(RANKINGS_KEY)
        by_id, _ = _catalog(rankings)
        player_map = dict(zip(unique, players))
    except Exception:
        return rows
    out: list[dict[str, Any]] = []
    for row in rows:
        enriched = dict(row)
        player = player_map.get(str(row.get("player_id")))
        if isinstance(player, dict):
            team_id = str(player.get("team_id")) if player.get("team_id") is not None else None
            identity = by_id.get(team_id) if team_id else None
            enriched["team_id"] = team_id
            enriched["team_logo"] = enriched.get("team_logo") or player.get("team_logo") or (
                identity.get("logo") if identity else None
            )
        out.append(enriched)
    return out


async def enrich_search_rows(rows: list[dict[str, Any]], *, team_results: bool = False) -> list[dict[str, Any]]:
    """Enrich bounded player/team search hits from the shared ranking cache."""
    try:
        rankings = await cache_get(RANKINGS_KEY)
        by_id, by_name = _catalog(rankings)
    except Exception:
        return rows
    out: list[dict[str, Any]] = []
    for row in rows:
        enriched = dict(row)
        if team_results:
            team_id = str(row.get("id")) if row.get("id") is not None else None
            item = by_id.get(team_id) if team_id else _find(row.get("name"), by_name)
            if item:
                enriched["logo"] = enriched.get("logo") or item.get("logo")
        else:
            team_id = str(row.get("team_id")) if row.get("team_id") is not None else None
            item = by_id.get(team_id) if team_id else _find(row.get("team"), by_name)
            if item:
                enriched["team_id"] = enriched.get("team_id") or item.get("id")
                enriched["team_logo"] = enriched.get("team_logo") or item.get("logo")
        out.append(enriched)
    return out


async def enrich_team_trend(detail: dict[str, Any]) -> dict[str, Any]:
    rows = list(detail.get("results_in_window") or [])
    try:
        rankings = await cache_get(RANKINGS_KEY)
        _, by_name = _catalog(rankings)
    except Exception:
        return detail
    out = dict(detail)
    enriched_rows = []
    for row in rows:
        enriched = dict(row)
        item = _find(row.get("opponent"), by_name)
        if item:
            enriched["opponent_id"] = enriched.get("opponent_id") or item.get("id")
            enriched["opponent_logo"] = enriched.get("opponent_logo") or item.get("logo")
            enriched["opponent_short_name"] = enriched.get("opponent_short_name") or item.get("short_name")
        enriched_rows.append(enriched)
    out["results_in_window"] = enriched_rows
    team_id = str(detail.get("team_id")) if detail.get("team_id") is not None else None
    if team_id:
        by_id, _ = _catalog(rankings)
        own = by_id.get(team_id)
        if own:
            out["logo"] = out.get("logo") or own.get("logo")
    return out
