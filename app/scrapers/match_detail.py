"""Match-detail scraper (Phase 7) — the full match page shape.

Produces the rich shape the broadcast match page needs: header (event, teams +
series score, veto line), the per-map list (name, pick/decider, map score), the
per-map per-team scoreboards, and the round-by-round timeline.

The hard-won scoreboard rule (from the banked live fixtures): every value cell is
side-split into three spans — mod-both (combined), mod-t (attack), mod-ct (defense).
We read mod-both as the value and keep mod-t/mod-ct alongside. Reading raw td.text()
instead would CONCATENATE the three (K=13 -> "1385"), a number that coerces fine and
is silently wrong. Live-state empties (R/ACS/ADR not yet computed) -> None, never NaN.
"""
import re
from typing import Any

from selectolax.parser import HTMLParser, Node

from app.core.http import get_client
from app.scrapers import selectors as S
from app.scrapers._util import (
    clean_spaces,
    country_from_flag,
    id_from_href,
    parse_numeric,
    parse_percent,
    text_of,
)

VLR = "https://www.vlr.gg"
_LEADING_INDEX = re.compile(r"^\s*\d+\s*")  # "1Pearl" -> "Pearl"


# ---- scoreboard cells (per-player stat rows) -------------------------------
def _coerce(key: str, both: str | None) -> float | None:
    """KAST and HS% carry a percent sign -> parse_percent; the rest -> parse_numeric.
    Both return None (never NaN) for empty live-partial cells."""
    if key in S.MATCH_SB_PCT_KEYS or (both is not None and both.endswith("%")):
        return parse_percent(both)
    return parse_numeric(both)


def _read_stat(td: Node) -> tuple[str | None, str | None, str | None]:
    """(both, t, ct) clean strings from the side-split spans. Defaults to mod-both."""
    both = td.css_first(S.MATCH_SB_VAL_BOTH)
    t = td.css_first(S.MATCH_SB_VAL_T)
    ct = td.css_first(S.MATCH_SB_VAL_CT)
    return (
        clean_spaces(text_of(both)) or None,
        clean_spaces(text_of(t)) or None,
        clean_spaces(text_of(ct)) or None,
    )


def _parse_identity(tr: Node) -> dict[str, Any]:
    cell = tr.css_first(S.MATCH_SB_PLAYER)
    if cell is None:
        return {"player": None, "team": None, "player_id": None, "country": None}
    link = cell.css_first(S.MATCH_SB_PLAYER_LINK)
    href = (link.attributes.get("href", "") if link else "") or ""
    return {
        "player": clean_spaces(text_of(cell.css_first(S.MATCH_SB_PLAYER_ALIAS))) or None,
        "team": clean_spaces(text_of(cell.css_first(S.MATCH_SB_PLAYER_TEAM))) or None,
        "player_id": id_from_href(href),
        "country": country_from_flag(cell.css_first(S.MATCH_SB_PLAYER_FLAG)),
    }


def _parse_player_row(tr: Node) -> dict[str, Any]:
    agent_img = tr.css_first(S.MATCH_SB_AGENT)
    agent = (agent_img.attributes.get("alt") if agent_img else None) or None
    stats: dict[str, Any] = {}
    # every data-col element is a value: the 9 top-level cells PLUS the 3
    # kills/deaths/assists spans nested inside the mod-kda cell (see selectors.py)
    for node in tr.css(S.MATCH_SB_STAT_CELL):
        key = S.MATCH_SB_COL_KEYS.get(node.attributes.get("data-col") or "")
        if not key:
            continue
        both, t, ct = _read_stat(node)
        # value reads mod-both, NEVER the concatenated raw cell text
        stats[key] = {"value": _coerce(key, both), "both": both, "t": t, "ct": ct}
    return {**_parse_identity(tr), "agent": agent, "stats": stats}


def _parse_table(table: Node) -> list[dict[str, Any]]:
    return [
        _parse_player_row(tr)
        for tr in table.css(S.MATCH_SB_ROW)
        if tr.css(S.MATCH_SB_CELL)
    ]


# ---- rounds ----------------------------------------------------------------
def _outcome_from_img(sq: Node) -> str | None:
    img = sq.css_first(S.MATCH_RND_IMG)
    src = (img.attributes.get("src", "") if img else "") or ""
    # /img/vlr/game/round/elim.webp -> "elim"
    if not src:
        return None
    return src.rsplit("/", 1)[-1].split(".")[0] or None


def _parse_rounds(game: Node) -> list[dict[str, Any]]:
    row = game.css_first(S.MATCH_RND_ROW)
    if row is None:
        return []
    rounds: list[dict[str, Any]] = []
    for col in row.css(S.MATCH_RND_COL):
        num = col.css_first(S.MATCH_RND_NUM)
        if num is None:  # the leading team-label col carries no round number
            continue
        winner = side = outcome = None
        for i, sq in enumerate(col.css(S.MATCH_RND_SQ)):  # [team1, team2]
            cls = sq.attributes.get("class", "") or ""
            if "mod-win" in cls:
                winner = i + 1  # 1 = team1 (top), 2 = team2 (bottom)
                side = "t" if "mod-t" in cls else "ct" if "mod-ct" in cls else None
                outcome = _outcome_from_img(sq)
        n = parse_numeric(text_of(num))
        rounds.append(
            {
                "round": int(n) if n is not None else None,
                "winner": winner,
                "side": side,
                "outcome": outcome,
                "score": col.attributes.get("title"),  # cumulative "team1-team2"
            }
        )
    return rounds


# ---- header ----------------------------------------------------------------
def _parse_header(tree: HTMLParser) -> dict[str, Any]:
    links = tree.css(S.MATCH_H_TEAM_LINK)
    teams: list[dict[str, Any]] = []
    for ln in links[:2]:
        href = ln.attributes.get("href", "") or ""
        name = clean_spaces(text_of(ln.css_first(S.MATCH_H_TEAM_NAME))) or None
        teams.append({"name": name, "id": id_from_href(href)})

    spoiler = tree.css_first(S.MATCH_H_SCORE_SPOILER)
    a, b = None, None
    if spoiler is not None:
        m = re.findall(r"\d+", spoiler.text())
        if len(m) >= 2:
            a, b = int(m[0]), int(m[1])

    notes = [clean_spaces(text_of(n)).lower() for n in tree.css(S.MATCH_H_VS_NOTE)]
    status = "final" if any("final" in n for n in notes) else (
        "live" if any("live" in n for n in notes) else None
    )
    fmt = next((n.upper() for n in notes if re.fullmatch(r"bo\d", n)), None)

    if len(teams) == 2:
        teams[0]["score"], teams[1]["score"] = a, b
        decided = status == "final" and a is not None and b is not None and a != b
        teams[0]["won"] = decided and a > b
        teams[1]["won"] = decided and b > a

    return {
        "event": clean_spaces(text_of(tree.css_first(S.MATCH_H_EVENT_NAME))) or None,
        "series": clean_spaces(text_of(tree.css_first(S.MATCH_H_SERIES))) or None,
        "status": status,
        "format": fmt,
        "teams": teams,
        "veto": clean_spaces(text_of(tree.css_first(S.MATCH_H_VETO))) or None,
    }


# ---- maps ------------------------------------------------------------------
def _nav_map_names(tree: HTMLParser) -> dict[str, str]:
    """game-id -> clean map name, from the games nav ("1Pearl" -> "Pearl")."""
    out: dict[str, str] = {}
    for nav in tree.css(S.MATCH_NAV_ITEM):
        gid = nav.attributes.get("data-game-id")
        if not gid:
            continue
        out[gid] = _LEADING_INDEX.sub("", clean_spaces(text_of(nav))) or gid
    return out


def _parse_game(game: Node, names: dict[str, str]) -> dict[str, Any]:
    gid = game.attributes.get("data-game-id")
    tables = game.css(S.MATCH_SB_TABLE)  # [team1, team2]
    team_names = [clean_spaces(text_of(n)) or None for n in game.css(S.MATCH_GAME_HEADER_TEAM)]
    scores = [parse_numeric(text_of(s)) for s in game.css(S.MATCH_GAME_HEADER_SCORE)]
    map_text = clean_spaces(text_of(game.css_first(S.MATCH_GAME_MAP)))
    picked = S.MATCH_GAME_PICK_TOKEN in map_text
    name = names.get(gid or "", "") or _LEADING_INDEX.sub("", map_text.replace(S.MATCH_GAME_PICK_TOKEN, "")) or None

    teams = []
    for i, table in enumerate(tables):
        teams.append(
            {
                "name": team_names[i] if i < len(team_names) else None,
                "score": scores[i] if i < len(scores) else None,
                "players": _parse_table(table),
            }
        )
    return {
        "game_id": gid,
        "name": name,
        "picked": picked,
        "decider": not picked,  # the one map neither side picked
        "scores": [t["score"] for t in teams] or None,
        "teams": teams,
        "rounds": _parse_rounds(game),
    }


# ---- streams (Twitch channel logins) --------------------------------------
def _twitch_login_from_href(href: str) -> str | None:
    """"https://www.twitch.tv/valorant_br?foo" -> "valorant_br". Only twitch.tv
    hosts; anything else (YouTube/SOOP/...) -> None."""
    if not href or S.MATCH_STREAM_TWITCH_HOST not in href:
        return None
    tail = href.split(S.MATCH_STREAM_TWITCH_HOST + "/", 1)[-1]
    tail = tail.split("?", 1)[0].split("#", 1)[0].strip("/")
    return tail.split("/", 1)[0] or None


def _parse_streams(tree: HTMLParser) -> list[str]:
    """Flat, de-duped list of Twitch channel logins from the match-page streams strip.

    Only the embeddable (mod-embed) entries are Twitch; their inner embed div carries
    data-site-id = the bare login, read directly (feeds Helix user_login). If that attr
    is ever missing we fall back to the last path segment of the external twitch.tv href.
    Non-Twitch platforms have no data-site-id and no twitch.tv link -> skipped. No
    official/co-streamer distinction (the markup doesn't expose one). Empty list = valid."""
    out: list[str] = []
    seen: set[str] = set()
    for btn in tree.css(S.MATCH_STREAM_BTN):
        embed = btn.css_first(S.MATCH_STREAM_EMBED)
        login = (embed.attributes.get(S.MATCH_STREAM_SITE_ID) if embed else None) or ""
        login = login.strip()
        if not login:  # attr absent -> fall back to the external twitch.tv link
            ext = btn.css_first(S.MATCH_STREAM_EXTERNAL)
            login = _twitch_login_from_href((ext.attributes.get("href", "") if ext else "") or "") or ""
        if not login or login.lower() in seen:
            continue
        seen.add(login.lower())
        out.append(login)
    return out


# ---- top-level -------------------------------------------------------------
def parse_match(html: str) -> dict[str, Any]:
    """Pure: HTML -> match detail dict. Network-free (like the other scrapers).

    `maps` is the per-map games in play order (Pearl/Fracture/Split). `all_maps`
    is the aggregate scoreboard (vlr's "All Maps" tab). Each map carries both teams'
    player rows + the round timeline; the aggregate has no map score or rounds."""
    tree = HTMLParser(html)
    names = _nav_map_names(tree)
    maps: list[dict[str, Any]] = []
    all_maps: dict[str, Any] | None = None
    for game in tree.css(S.MATCH_GAME):
        parsed = _parse_game(game, names)
        if parsed["game_id"] == S.MATCH_GAME_ALL_ID:
            # aggregate: keep only the player tables, drop the (absent) map meta
            all_maps = {"teams": [{"name": t["name"], "players": t["players"]} for t in parsed["teams"]]}
        else:
            maps.append(parsed)
    return {
        "id": None,
        **_parse_header(tree),
        "streams": _parse_streams(tree),
        "maps": maps,
        "all_maps": all_maps,
    }


async def fetch_match(match_id: str) -> dict[str, Any]:
    html = await get_client().get_html(f"/{match_id}")
    data = parse_match(html)
    data["id"] = str(match_id)  # trust the requested id
    data["url"] = f"{VLR}/{match_id}"
    return data
