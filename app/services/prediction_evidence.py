"""Bounded historical evidence; no all-time stats or inferred player identities."""
import asyncio
import math
import re
from collections import defaultdict


def number(value, maximum):
    return value if (isinstance(value, (int, float)) and not isinstance(value, bool)
                     and math.isfinite(value) and 0 <= value <= maximum) else None


def add_history(evidence, teams, history):
    """Only use details corroborated by a dated result in the form snapshot."""
    identities = {t["id"] for t in evidence["teams"]}
    for team, form in zip(teams, evidence["facts"][:2]):
        tid = form["team_id"]
        roster = {str(p.get("player_id")): str(p.get("alias") or p.get("player_id"))[:80] for p in team.get("roster", [])
                  if isinstance(p, dict) and p.get("is_staff") is False
                  and not re.search(r"inactive|bench|substitute|coach|manager", str(p.get("role") or ""), re.I)
                  and str(p.get("player_id", "")).isdigit()}
        maps, players, meetings = defaultdict(list), defaultdict(list), []
        for row in form["matches"]:
            mid = row["match_id"]
            match = history.get(mid)
            if not isinstance(match, dict) or str(match.get("id")) != mid or match.get("status") != "final":
                continue
            sides = match.get("teams", [])
            if len(sides) != 2 or any(not isinstance(s, dict) for s in sides):
                continue
            ids = [str(s.get("id")) for s in sides]
            if tid not in ids or len(set(ids)) != 2:
                continue
            side = ids.index(tid)
            scores = [number(s.get("score"), 5) for s in sides]
            if None in scores or scores[0] == scores[1]:
                continue
            won = scores[side] > scores[1-side]
            if won != (row["result"] == "win"):
                continue
            source = {"match_id": mid, "date": row["date"], "opponent_id": ids[1-side]}
            if set(ids) == identities:
                meetings.append({**source, "result": row["result"]})
            seen = set()
            for game in match.get("maps", []):
                if not isinstance(game, dict):
                    continue
                gid, name = game.get("game_id"), game.get("name")
                rounds = game.get("scores", [])
                scoreboard = game.get("teams", [])
                if (not isinstance(gid, (str, int)) or not gid or gid in seen
                        or not isinstance(name, str) or not re.fullmatch(r"[A-Za-z][A-Za-z ]{0,39}", name)
                        or name.casefold() in ("all", "all maps", "tbd", "unknown") or len(rounds) != 2
                        or len(scoreboard) != 2 or any(not isinstance(s, dict) for s in scoreboard)
                        or [s.get("name") for s in scoreboard] != [s.get("name") for s in sides]):
                    continue
                rounds = [number(v, 100) for v in rounds]
                if (None in rounds or any(v != int(v) for v in rounds)
                        or max(rounds) < 13 or abs(rounds[0]-rounds[1]) < 2):
                    continue
                seen.add(gid)
                maps[name].append({**source, "won": rounds[side] > rounds[1-side]})
                seen_players = set()
                for player in scoreboard[side].get("players", []):
                    if not isinstance(player, dict):
                        continue
                    pid = str(player.get("player_id"))
                    if pid not in roster or pid in seen_players:
                        continue
                    seen_players.add(pid)
                    stats = player.get("stats", {})
                    if not isinstance(stats, dict):
                        continue
                    values = {}
                    for metric, cap in (("ACS", 1000), ("ADR", 1000), ("R", 5)):
                        cell = stats.get(metric)
                        v = number(cell.get("value"), cap) if isinstance(cell, dict) else None
                        if v is not None:
                            values[metric] = v
                    if values:
                        players[pid].append({**source, "map": name, "values": values})
        def fact(kind, text, samples):
            evidence["facts"].append({"id": f"{kind}:{tid}", "team_id": tid,
                                      "text": text, "source_url": f"https://www.vlr.gg/team/{tid}",
                                      "samples": samples})
        if meetings:
            wins = sum(m["result"] == "win" for m in meetings)
            fact("h2h", f"Head-to-head in the recent sample: {wins} wins and {len(meetings)-wins} losses for {team.get('name', tid)} across {len(meetings)} verified meetings.", meetings)
        else:
            evidence["limitations"].append(f"Team {tid}: no verified head-to-head meeting in the sampled recent results.")
        if maps:
            summary = "; ".join(f"{name}: {sum(s['won'] for s in samples)} wins and {sum(not s['won'] for s in samples)} losses ({len(samples)} maps)" for name, samples in sorted(maps.items()))
            fact("maps", "Recent map performance: " + summary + ".", dict(maps))
        else:
            evidence["limitations"].append(f"Team {tid}: completed named-map scoreboards unavailable in this sample.")
        if players:
            summaries = []
            for pid, samples in sorted(players.items()):
                metrics = []
                for metric in ("ACS", "ADR", "R"):
                    values = [s["values"][metric] for s in samples if metric in s["values"]]
                    if values:
                        metrics.append(f"{metric} {sum(values)/len(values):.2f} over {len(values)} maps")
                summaries.append(f"{roster[pid]} (player {pid}): " + ", ".join(metrics))
            fact("players", "Current listed players, unweighted per-map averages: " + "; ".join(summaries) + ".", dict(players))
        else:
            evidence["limitations"].append(f"Team {tid}: current-roster player statistics unavailable in this sample.")
    return evidence


async def enrich(evidence, teams, load):
    history = {}
    ids = list(dict.fromkeys(r["match_id"] for f in evidence["facts"] for r in f["matches"]))
    # Prioritize shared result IDs, which may establish head-to-head identity.
    shared = set(r["match_id"] for r in evidence["facts"][0]["matches"]) & set(r["match_id"] for r in evidence["facts"][1]["matches"])
    ids.sort(key=lambda mid: mid not in shared)
    try:
        async with asyncio.timeout(60):
            for mid in ids[:10]:
                try:
                    async with asyncio.timeout(8):
                        history[mid] = await load(mid)
                except Exception:
                    continue
    except TimeoutError:
        pass
    evidence["limitations"] = ["Evidence covers up to five recent series per team within 90 days; missing or slow scoreboards are excluded.",
                               "Samples are not opponent-adjusted. Map results do not establish the upcoming veto or current patch suitability.",
                               "Listed rosters do not confirm match availability; historical player averages are unweighted by rounds.",
                               "Same-day results are excluded. Missing evidence is not evidence of poor performance."]
    return add_history(evidence, teams, history)
