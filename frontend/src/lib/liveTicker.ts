// Live-ticker derivations — PURE + isomorphic (no fetch, no node APIs, no clock,
// no randomness beyond the seed handed in). Safe to import into the client poll
// island AND the server seed loader. Every stat here is derived from the EXISTING
// Phase 7 match-detail shape (grounding confirmed the rest aren't scraped).
//
// Order is computed once on the server (seededOrder) and carried into the first
// client render unchanged — NOTHING here is called during React render. The trap
// we must not reintroduce (match-page hydration fix): no SSR↔hydrate divergence.

import type { MatchDetail, MatchMap, MatchMapTeam, TickerItem } from "@/types/vlr";

// --- notability gates (exported so the curation contract is testable, not vibes)
export const STREAK_MIN = 2; // consecutive rounds before a streak is worth showing
export const MOMENTUM_WINDOW = 5; // "won X of last Y" window
export const MOMENTUM_MIN_ROUNDS = 3; // need at least this many decided rounds
export const FK_MIN = 1; // at least one first blood recorded

function fmtInt(n: number | null | undefined): string {
  return n === null || n === undefined ? "—" : String(Math.round(n));
}

/** The live match id to seed/poll: the first live match that has an id. */
export function pickLiveMatchId(
  live: { id: string | null }[],
): string | null {
  return live.find((m) => m.id)?.id ?? null;
}

/** The currently-playing map: the last map (play order) with ≥1 decided round —
 *  a finished earlier map yields to the in-progress one. Falls back to the first
 *  map (a freshly-started series → veto/decider recap still has something). */
function currentLiveMap(m: MatchDetail): MatchMap | null {
  let cur: MatchMap | null = null;
  for (const mp of m.maps) {
    if (mp.rounds.some((r) => r.winner !== null)) cur = mp;
  }
  return cur ?? m.maps[0] ?? null;
}

function decidedWinners(map: MatchMap | null): (1 | 2)[] {
  if (!map) return [];
  return map.rounds
    .filter((r) => r.winner === 1 || r.winner === 2)
    .map((r) => r.winner as 1 | 2);
}

function flatPlayers(teams: MatchMapTeam[]) {
  return teams.flatMap((t) =>
    t.players.map((p) => ({ p, teamName: p.team ?? t.name })),
  );
}

/** Running, match-wide leaders read off the all-maps aggregate (falls back to the
 *  current map if the aggregate is absent). */
function aggregateTeams(m: MatchDetail): MatchMapTeam[] {
  if (m.allMaps?.teams.length) return m.allMaps.teams;
  return currentLiveMap(m)?.teams ?? [];
}

// --- the six derived live stats (each returns one item or null when not notable)

/** LIVE headline: current map score + round number. tone=down (LIVE red). */
function liveScore(m: MatchDetail): TickerItem | null {
  const map = currentLiveMap(m);
  if (!map) return null;
  const s1 = map.scores[0] ?? map.teams[0]?.score ?? null;
  const s2 = map.scores[1] ?? map.teams[1]?.score ?? null;
  const decided = map.rounds.filter((r) => r.winner !== null);
  const lastNum = decided.length
    ? decided[decided.length - 1].round ?? decided.length
    : 0;
  const t1 = m.teams[0]?.name ?? "TBD";
  const t2 = m.teams[1]?.name ?? "TBD";
  return {
    id: "live:score",
    kind: "live-score",
    label: "LIVE",
    tone: "down",
    primary: `${t1} vs ${t2}`,
    value: `${fmtInt(s1)}–${fmtInt(s2)}`,
    detail: `${map.name ?? "Map"} · Round ${lastNum + 1}`,
  };
}

/** Top performer by live ACS across both teams; FALLS BACK to K–D–A while ACS is
 *  still null (early-live, before vlr computes it — see the partial fixture). */
function topPerformer(m: MatchDetail): TickerItem | null {
  const players = flatPlayers(aggregateTeams(m)).filter((x) => x.p.player);
  if (!players.length) return null;

  const hasAcs = players.some((x) => x.p.stats["ACS"]?.value != null);
  if (hasAcs) {
    let best: { name: string; team: string | null; acs: number } | null = null;
    for (const x of players) {
      const acs = x.p.stats["ACS"]?.value ?? null;
      if (acs === null) continue;
      if (!best || acs > best.acs)
        best = { name: x.p.player as string, team: x.teamName, acs };
    }
    if (!best) return null;
    return {
      id: "live:performer",
      kind: "live-performer",
      label: "TOP ACS",
      tone: "accent",
      primary: best.name,
      value: fmtInt(best.acs),
      detail: best.team ?? "live leader",
    };
  }

  // fallback: rank by kills (K), break ties by fewer deaths.
  let best: { name: string; team: string | null; score: number; kda: string } | null = null;
  for (const x of players) {
    const k = x.p.stats["K"]?.value ?? null;
    if (k === null) continue;
    const d = x.p.stats["D"]?.value ?? 0;
    const a = x.p.stats["A"]?.value ?? null;
    const score = k * 1000 - d; // K dominates; fewer deaths breaks ties
    if (!best || score > best.score)
      best = {
        name: x.p.player as string,
        team: x.teamName,
        score,
        kda: `${fmtInt(k)}–${fmtInt(d)}–${fmtInt(a)}`,
      };
  }
  if (!best) return null;
  return {
    id: "live:performer",
    kind: "live-performer",
    label: "TOP FRAGGER",
    tone: "accent",
    primary: best.name,
    value: best.kda,
    detail: best.team ?? "live leader",
  };
}

/** Consecutive rounds won (current map), gated at STREAK_MIN. tone=up. */
function streak(m: MatchDetail): TickerItem | null {
  const map = currentLiveMap(m);
  const winners = decidedWinners(map);
  if (!winners.length) return null;
  const last = winners[winners.length - 1];
  let s = 0;
  for (let i = winners.length - 1; i >= 0 && winners[i] === last; i--) s++;
  if (s < STREAK_MIN) return null;
  const name = m.teams[last - 1]?.name ?? `Team ${last}`;
  return {
    id: "live:streak",
    kind: "live-streak",
    label: "STREAK",
    tone: "up",
    primary: name,
    value: fmtInt(s),
    detail: `${s} rounds in a row · ${map?.name ?? "current map"}`,
  };
}

/** Momentum: "won X of last Y rounds" (current map), Y=MOMENTUM_WINDOW. */
function momentum(m: MatchDetail): TickerItem | null {
  const winners = decidedWinners(currentLiveMap(m));
  if (winners.length < MOMENTUM_MIN_ROUNDS) return null;
  const Y = Math.min(MOMENTUM_WINDOW, winners.length);
  const lastY = winners.slice(-Y);
  const t1 = lastY.filter((w) => w === 1).length;
  const t2 = Y - t1;
  if (t1 === t2) return null; // dead even → no momentum edge
  const team = t1 > t2 ? 1 : 2;
  const won = Math.max(t1, t2);
  const name = m.teams[team - 1]?.name ?? `Team ${team}`;
  return {
    id: "live:momentum",
    kind: "live-momentum",
    label: "MOMENTUM",
    tone: "up",
    primary: name,
    value: `${won}/${Y}`,
    detail: `won ${won} of the last ${Y} rounds`,
  };
}

/** First-blood leader by FK across both teams (running, all-maps). tone=warn. */
function fkLeader(m: MatchDetail): TickerItem | null {
  const players = flatPlayers(aggregateTeams(m)).filter((x) => x.p.player);
  let best: { name: string; team: string | null; fk: number } | null = null;
  for (const x of players) {
    const fk = x.p.stats["FK"]?.value ?? null;
    if (fk === null) continue;
    if (!best || fk > best.fk)
      best = { name: x.p.player as string, team: x.teamName, fk };
  }
  if (!best || best.fk < FK_MIN) return null;
  return {
    id: "live:fk",
    kind: "live-fk",
    label: "FIRST BLOODS",
    tone: "warn",
    primary: best.name,
    value: fmtInt(best.fk),
    detail: best.team ? `${best.team} · most first kills` : "most first kills",
  };
}

/** Veto / decider recap for the live match. tone=neutral. */
function vetoRecap(m: MatchDetail): TickerItem | null {
  if (!m.veto) return null;
  const decider = m.maps.find((mp) => mp.decider)?.name ?? null;
  return {
    id: "live:veto",
    kind: "live-veto",
    label: "VETO",
    tone: "neutral",
    primary: "Map veto",
    value: decider ?? "—",
    detail: m.veto,
  };
}

/** Build the live in-game tape from the match detail. Canonical order
 *  (score → performer → streak → momentum → first-bloods → veto); seededOrder
 *  reorders it once on the server. Pure: same match → same items. */
export function buildLiveTicker(m: MatchDetail): TickerItem[] {
  return [
    liveScore(m),
    topPerformer(m),
    streak(m),
    momentum(m),
    fkLeader(m),
    vetoRecap(m),
  ].filter((x): x is TickerItem => x !== null);
}

/** Deterministic, seed-driven order — STABLE per (id, seed) so it survives a poll
 *  (the item set's ids are fixed; only their values churn) and is reproducible in
 *  tests. The server computes this once and hands the ordered array + seed to the
 *  client island, which reuses the SAME seed on each poll — so the order never
 *  jumps and the first client render matches SSR exactly. */
export function seededOrder<T extends { id: string }>(
  items: T[],
  seed: number,
): T[] {
  return items
    .map((item) => ({ item, k: hashSeed(item.id, seed) }))
    .sort((a, b) => a.k - b.k || a.item.id.localeCompare(b.item.id))
    .map((x) => x.item);
}

function hashSeed(id: string, seed: number): number {
  let h = (seed >>> 0) ^ 0x9e3779b9;
  for (let i = 0; i < id.length; i++) {
    h = Math.imul(h ^ id.charCodeAt(i), 0x01000193) >>> 0;
  }
  return h >>> 0;
}
