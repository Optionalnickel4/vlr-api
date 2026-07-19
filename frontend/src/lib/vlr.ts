// Data layer — the single boundary between the broadcast UI and vlr-api.
//
// Rules (carried from v5 + the frontend spec):
// - `fetchUpstream(path)` is the ONLY place that touches the network. Base is
//   process.env.VLR_API_BASE ?? "http://127.0.0.1:8000/api/v1". Server-side only.
// - vlr-api URLs are already absolute — never prepend a domain.
// - parseNumeric returns null, never NaN.
// - Loaders are graceful-empty: on any failure they return
//   { data: [], stale: true, error } and never throw to the page.
// - UI never sees raw vlr-api JSON; all mapping lives here + in @/types/vlr.

import type {
  AgentStat,
  ApiResponse,
  LiveMapScore,
  LiveMatch,
  MatchDetail,
  MatchMap,
  MatchMapTeam,
  MatchPlayer,
  MatchRound,
  MatchStatCell,
  MatchTeam,
  NewsArticle,
  PlayerDetail,
  PlayerDimensions,
  PlayerMatch,
  PlayerOverall,
  PlayerSearchResult,
  PlayerTrend,
  RankedTeam,
  ResultMatch,
  RosterMember,
  SignatureAgent,
  StatLeader,
  TeamDetail,
  TeamMatch,
  TeamTrend,
  TickerItem,
  TickerSources,
  TrendResult,
  UpcomingMatch,
} from "@/types/vlr";

export const VLR_API_BASE =
  process.env.VLR_API_BASE ?? "http://127.0.0.1:8000/api/v1";

/** The home page (match center) shows a compact SNAPSHOT of this many
 *  upcoming/results rows each; the full ~50-row lists live on the dedicated
 *  /schedule and /results pages (same endpoints, no slice). */
export const HOME_SNAPSHOT_LIMIT = 5;

/** Parse a raw upstream value to a number, or null. Never returns NaN.
 *  "1" -> 1, "2000" -> 2000, "1.17" -> 1.17, "–"/""/null/"19h 34m" -> null. */
export function parseNumeric(value: unknown): number | null {
  if (value === null || value === undefined) return null;
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  const s = String(value).trim();
  if (s === "") return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

// ---- the single network boundary -------------------------------------------

/** Fetch a path off VLR_API_BASE and return parsed JSON. Throws on non-2xx or
 *  network error so loaders can map failures to graceful-empty. */
export async function fetchUpstream(path: string): Promise<unknown> {
  const res = await fetch(`${VLR_API_BASE}${path}`, {
    headers: { accept: "application/json" },
    // live data is polled by the caller; the data layer itself never caches.
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`vlr-api ${path} -> ${res.status}`);
  }
  return res.json();
}

// ---- helpers ----------------------------------------------------------------

function asList(raw: unknown): Record<string, unknown>[] {
  return Array.isArray(raw) ? (raw as Record<string, unknown>[]) : [];
}

function str(value: unknown): string | null {
  if (value === null || value === undefined) return null;
  const s = String(value);
  return s === "" ? null : s;
}

/** Upstream results carry "win" | "loss" | null; normalize defensively. */
function winLoss(value: unknown): "win" | "loss" | null {
  return value === "win" || value === "loss" ? value : null;
}

/** A match card (results/upcoming/live share one upstream parser). */
function teamsScores(raw: Record<string, unknown>): {
  team1: string | null;
  team2: string | null;
  score1: number | null;
  score2: number | null;
} {
  const teams = Array.isArray(raw.teams) ? (raw.teams as unknown[]) : [];
  const scores = Array.isArray(raw.scores) ? (raw.scores as unknown[]) : [];
  return {
    team1: str(teams[0]),
    team2: str(teams[1]),
    score1: parseNumeric(scores[0]),
    score2: parseNumeric(scores[1]),
  };
}

// ---- transforms (pure) ------------------------------------------------------

export function normalizeResult(raw: unknown): ResultMatch[] {
  return asList(raw).map((m) => ({
    id: str(m.id),
    ...teamsScores(m),
    time: str(m.eta) ?? str(m.time), // eta || time
    series: str(m.series),
    event: str(m.event),
    url: str(m.url),
  }));
}

export function normalizeUpcoming(raw: unknown): UpcomingMatch[] {
  return asList(raw).map((m) => {
    const { team1, team2 } = teamsScores(m);
    return {
      id: str(m.id),
      team1,
      team2,
      timeUntil: str(m.eta),
      series: str(m.series),
      event: str(m.event),
      url: str(m.url),
    };
  });
}

export function normalizeLive(raw: unknown): LiveMatch[] {
  // Same card shape as results; current-map UI has no upstream source (degraded).
  return asList(raw).map((m) => ({
    id: str(m.id),
    ...teamsScores(m),
    series: str(m.series),
    event: str(m.event),
    url: str(m.url),
  }));
}

export function normalizeRankings(raw: unknown): RankedTeam[] {
  return asList(raw).map((t) => ({
    id: str(t.team_id),
    rank: parseNumeric(t.rank),
    team: str(t.team),
    country: str(t.country),
    rating: parseNumeric(t.rating),
  }));
}

/** Split "•June 8, 2026•by raezeri" into date + author. Falls back to showing
 *  the raw meta as the date when the split is fragile (never invents fields). */
export function normalizeNews(raw: unknown): NewsArticle[] {
  return asList(raw).map((n) => {
    const meta = str(n.meta);
    let date: string | null = meta;
    let author: string | null = null;
    if (meta) {
      const parts = meta
        .split("•")
        .map((p) => p.trim())
        .filter(Boolean);
      const authorPart = parts.find((p) => p.toLowerCase().startsWith("by "));
      const datePart = parts.find((p) => !p.toLowerCase().startsWith("by "));
      if (authorPart) author = authorPart.slice(3).trim() || null;
      if (datePart) date = datePart;
      // if the split yielded nothing useful, `date` stays the verbatim meta.
    }
    return {
      title: str(n.title),
      description: str(n.description),
      date,
      author,
      url: str(n.url),
    };
  });
}

function normalizeAgentStats(raw: unknown): AgentStat[] {
  if (!Array.isArray(raw)) return [];
  return (raw as Record<string, unknown>[]).map((a) => ({
    agent: str(a.agent),
    // VERBATIM: keep upstream keys ("K:D", "KAST", ...) and values as-is.
    stats:
      a.stats && typeof a.stats === "object"
        ? (a.stats as Record<string, string>)
        : {},
  }));
}

function normalizePlayerMatches(raw: unknown): PlayerMatch[] {
  if (!Array.isArray(raw)) return [];
  return (raw as Record<string, unknown>[]).map((m) => ({
    id: str(m.id),
    url: str(m.url),
    opponent: str(m.opponent),
    result: winLoss(m.result),
    score: str(m.score),
    event: str(m.event),
  }));
}

/** Player detail is a single object; we wrap it as a one-element list to keep
 *  the ApiResponse<T> envelope uniform. */
export function normalizePlayer(raw: unknown): PlayerDetail[] {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return [];
  const p = raw as Record<string, unknown>;
  return [
    {
      id: str(p.id),
      alias: str(p.alias),
      realName: str(p.real_name),
      country: str(p.country),
      team: str(p.team),
      teamId: str(p.team_id),
      teamUrl: str(p.team_url),
      agentStats: normalizeAgentStats(p.agent_stats),
      matches: normalizePlayerMatches(p.matches),
    },
  ];
}

/** Round to `d` decimals, returning a plain number (Number(toFixed) avoids the
 *  trailing-float noise of raw division). */
function roundTo(n: number, d: number): number {
  return Number(n.toFixed(d));
}

/** The card-header overall: a ROUNDS-WEIGHTED collapse of the per-agent rows
 *  (VLR exposes no totals row — confirmed against real markup — only per-agent
 *  stats). Mirrors the Phase 8 trend service's weighting EXACTLY: weight by RND,
 *  fall back to weight 1 so a parseable stat is never dropped, and skip a row
 *  whose stat doesn't parse. A 5881-round Omen therefore dominates a 15-round
 *  Harbor — a naive average would let the 15-round line distort the headline.
 *  K/D is the summed total kills / total deaths (NOT a mean of per-agent ratios).
 *  Every value via parseNumeric (null-not-NaN); nothing parseable → null. */
export function playerOverall(agentStats: AgentStat[]): PlayerOverall {
  let ratingNum = 0;
  let ratingDen = 0;
  let acsNum = 0;
  let acsDen = 0;
  let totalK = 0;
  let totalD = 0;
  for (const row of agentStats) {
    const s = row.stats;
    const rnd = parseNumeric(s["RND"]);
    const weight = rnd !== null && rnd > 0 ? rnd : 1; // fallback so a parseable stat counts
    const rating = parseNumeric(s["Rating"]);
    if (rating !== null) {
      ratingNum += rating * weight;
      ratingDen += weight;
    }
    const acs = parseNumeric(s["ACS"]);
    if (acs !== null) {
      acsNum += acs * weight;
      acsDen += weight;
    }
    const k = parseNumeric(s["K"]);
    const d = parseNumeric(s["D"]);
    if (k !== null) totalK += k;
    if (d !== null) totalD += d;
  }
  return {
    rating: ratingDen > 0 ? roundTo(ratingNum / ratingDen, 2) : null,
    acs: acsDen > 0 ? roundTo(acsNum / acsDen, 1) : null,
    kd: totalD > 0 ? roundTo(totalK / totalD, 2) : null,
  };
}

/** The player's signature agent: the most-played row (by rounds), with its usage
 *  % read VERBATIM from the "Use" cell ("(286) 48%" → "48%"). Identity only — the
 *  full stat line stays in the agent table below. Null when there are no rows. */
export function signatureAgent(agentStats: AgentStat[]): SignatureAgent | null {
  let best: { agent: string; rounds: number; use: string | undefined } | null = null;
  for (const row of agentStats) {
    if (!row.agent) continue;
    const rounds = parseNumeric(row.stats["RND"]) ?? 0;
    if (best === null || rounds > best.rounds) {
      best = { agent: row.agent, rounds, use: row.stats["Use"] };
    }
  }
  if (best === null) return null;
  const pct = best.use?.match(/(\d+%)/);
  return { agent: best.agent, usage: pct ? pct[1] : null };
}

function normalizeRoster(raw: unknown): RosterMember[] {
  if (!Array.isArray(raw)) return [];
  return (raw as Record<string, unknown>[]).map((r) => ({
    alias: str(r.alias),
    realName: str(r.real_name),
    role: str(r.role),
    country: str(r.country),
    playerId: str(r.player_id),
    url: str(r.url),
    isCaptain: r.is_captain === true,
    isStaff: r.is_staff === true,
  }));
}

function normalizeTeamMatches(raw: unknown): TeamMatch[] {
  if (!Array.isArray(raw)) return [];
  return (raw as Record<string, unknown>[]).map((m) => ({
    id: str(m.id),
    url: str(m.url),
    opponent: str(m.opponent),
    opponentId: str(m.opponent_id),
    result: winLoss(m.result),
    score: str(m.score),
    event: str(m.event),
    date: str(m.date),
  }));
}

export function normalizeTeam(raw: unknown): TeamDetail[] {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return [];
  const t = raw as Record<string, unknown>;
  return [
    {
      id: str(t.id),
      name: str(t.name),
      tag: str(t.tag),
      country: str(t.country),
      countryCode: str(t.country_code),
      logo: str(t.logo),
      roster: normalizeRoster(t.roster),
      results: normalizeTeamMatches(t.results),
      upcoming: normalizeTeamMatches(t.upcoming),
    },
  ];
}

export function normalizeTrend(raw: unknown): TeamTrend[] {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return [];
  const t = raw as Record<string, unknown>;
  const trend = Array.isArray(t.rating_trend)
    ? (t.rating_trend as Record<string, unknown>[])
    : [];
  const results = Array.isArray(t.results_in_window)
    ? (t.results_in_window as Record<string, unknown>[])
    : [];
  const summaryRaw =
    t.summary && typeof t.summary === "object"
      ? (t.summary as Record<string, unknown>)
      : null;
  const resultsInWindow: TrendResult[] = results.map((r) => ({
    vlrId: str(r.vlr_id),
    opponent: str(r.opponent),
    result: winLoss(r.result),
    score: str(r.score),
    event: str(r.event),
    capturedAt: str(r.captured_at),
  }));
  // The trend line MUST be time-ordered on the real timestamp, never lexically
  // and never on the rating value (the Phase-4 string-sort trap). Sort here in
  // the data layer so the sparkline can trust the order. Undated points sink to
  // the end rather than crashing the comparator.
  const ratingTrend = trend
    .map((p) => ({
      capturedAt: str(p.captured_at),
      rating: parseNumeric(p.rating),
      rank: parseNumeric(p.rank),
    }))
    .sort((a, b) => {
      const ta = a.capturedAt ? Date.parse(a.capturedAt) : NaN;
      const tb = b.capturedAt ? Date.parse(b.capturedAt) : NaN;
      if (Number.isNaN(ta) && Number.isNaN(tb)) return 0;
      if (Number.isNaN(ta)) return 1;
      if (Number.isNaN(tb)) return -1;
      return ta - tb;
    });
  return [
    {
      teamId: str(t.team_id),
      team: str(t.team),
      windowDays: parseNumeric(t.window_days),
      ratingTrend,
      ratingChange: parseNumeric(t.rating_change),
      resultsInWindow,
      summary: summaryRaw
        ? {
            points: parseNumeric(summaryRaw.points) ?? 0,
            wins: parseNumeric(summaryRaw.wins) ?? 0,
            losses: parseNumeric(summaryRaw.losses) ?? 0,
            currentRating: parseNumeric(summaryRaw.current_rating),
            peakRating: parseNumeric(summaryRaw.peak_rating),
          }
        : null,
      ...(str(t.note) ? { note: str(t.note) as string } : {}),
    },
  ];
}

/** Player trend (Phase 8): the player analog of normalizeTrend. Different upstream
 *  shape — points are {captured_at, rating, acs, rounds}, there is no results join,
 *  and the summary carries ACS too. Same discipline: parseNumeric (null-not-NaN)
 *  at the boundary, and the line is time-ordered on the real captured_at, NEVER on
 *  the rating value. Undated points sink to the end rather than crashing the sort. */
export function normalizePlayerTrend(raw: unknown): PlayerTrend[] {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return [];
  const t = raw as Record<string, unknown>;
  const trend = Array.isArray(t.rating_trend)
    ? (t.rating_trend as Record<string, unknown>[])
    : [];
  const summaryRaw =
    t.summary && typeof t.summary === "object"
      ? (t.summary as Record<string, unknown>)
      : null;
  const ratingTrend = trend
    .map((p) => ({
      capturedAt: str(p.captured_at),
      rating: parseNumeric(p.rating),
      acs: parseNumeric(p.acs),
      rounds: parseNumeric(p.rounds),
    }))
    .sort((a, b) => {
      const ta = a.capturedAt ? Date.parse(a.capturedAt) : NaN;
      const tb = b.capturedAt ? Date.parse(b.capturedAt) : NaN;
      if (Number.isNaN(ta) && Number.isNaN(tb)) return 0;
      if (Number.isNaN(ta)) return 1;
      if (Number.isNaN(tb)) return -1;
      return ta - tb;
    });
  return [
    {
      playerId: str(t.player_id),
      player: str(t.player),
      team: str(t.team),
      windowDays: parseNumeric(t.window_days),
      ratingTrend,
      ratingChange: parseNumeric(t.rating_change),
      acsChange: parseNumeric(t.acs_change),
      summary: summaryRaw
        ? {
            points: parseNumeric(summaryRaw.points) ?? 0,
            currentRating: parseNumeric(summaryRaw.current_rating),
            peakRating: parseNumeric(summaryRaw.peak_rating),
            currentAcs: parseNumeric(summaryRaw.current_acs),
            peakAcs: parseNumeric(summaryRaw.peak_acs),
          }
        : null,
      ...(str(t.note) ? { note: str(t.note) as string } : {}),
    },
  ];
}

/** Below this spread (max − min rating across the window) the trend is
 *  effectively flat: a straight line carries no signal and reads as a render
 *  bug, so the panel shows the honest thin-history note instead. NOT a data fix
 *  — a ceiling team genuinely holds rating; this is purely a presentation gate.
 *  TEAM scale: ratings live around ~1500–2000, so 0.5 is "basically no move". */
export const FLAT_EPSILON = 0.5;

/** PLAYER scale: a player's rating sits around ~0.8–1.4, so the team's 0.5
 *  epsilon would mark every real player trend "flat". A move of ~0.03 is already
 *  meaningful for a player rating — gate the player line on that instead. */
export const PLAYER_FLAT_EPSILON = 0.03;

/** Whether a trend series has enough real, *moving* data to draw a sparkline.
 *  Two thin states collapse to "no line": fewer than 2 real values (history
 *  still young) OR ≥2 values with spread < `epsilon` (the degenerate flat case
 *  — e.g. a rank-1 team pinned at 2000). Generic over any `{ rating }`-shaped
 *  point so the team AND player panels share it; the per-scale flatness gate is
 *  the `epsilon` arg. The honest-state decision lives here in the tested data
 *  layer, not inline in the component. */
export function shouldRenderTrendLine(
  points: { rating: number | null }[],
  epsilon: number = FLAT_EPSILON,
): boolean {
  const ratings = points
    .map((p) => p.rating)
    .filter((r): r is number => r !== null);
  if (ratings.length < 2) return false;
  return Math.max(...ratings) - Math.min(...ratings) >= epsilon;
}

// ---- match detail (Phase 7) -------------------------------------------------

function normalizeStatCell(raw: unknown): MatchStatCell {
  const c =
    raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  return {
    // value arrives numeric from the API; parseNumeric re-coerces defensively so
    // an empty live-partial cell is null, never NaN. KAST/HS% are bare numbers.
    value: parseNumeric(c.value),
    both: str(c.both),
    t: str(c.t),
    ct: str(c.ct),
  };
}

function normalizeMatchPlayer(raw: Record<string, unknown>): MatchPlayer {
  const statsRaw =
    raw.stats && typeof raw.stats === "object"
      ? (raw.stats as Record<string, unknown>)
      : {};
  const stats: Record<string, MatchStatCell> = {};
  for (const [k, v] of Object.entries(statsRaw)) stats[k] = normalizeStatCell(v);
  return {
    player: str(raw.player),
    team: str(raw.team),
    playerId: str(raw.player_id),
    country: str(raw.country),
    agent: str(raw.agent),
    stats,
  };
}

function normalizeMapTeam(raw: unknown): MatchMapTeam {
  const t = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  return {
    name: str(t.name),
    score: parseNumeric(t.score),
    players: (Array.isArray(t.players) ? t.players : []).map((p) =>
      normalizeMatchPlayer(p as Record<string, unknown>),
    ),
  };
}

function normalizeRound(raw: Record<string, unknown>): MatchRound {
  const w = parseNumeric(raw.winner);
  const side = raw.side === "t" || raw.side === "ct" ? raw.side : null;
  return {
    round: parseNumeric(raw.round),
    winner: w === 1 ? 1 : w === 2 ? 2 : null,
    side,
    outcome: str(raw.outcome),
    score: str(raw.score),
  };
}

function normalizeMap(raw: Record<string, unknown>): MatchMap {
  return {
    gameId: str(raw.game_id),
    name: str(raw.name),
    picked: raw.picked === true,
    decider: raw.decider === true,
    scores: (Array.isArray(raw.scores) ? raw.scores : []).map(parseNumeric),
    teams: (Array.isArray(raw.teams) ? raw.teams : []).map(normalizeMapTeam),
    rounds: (Array.isArray(raw.rounds) ? raw.rounds : []).map((r) =>
      normalizeRound(r as Record<string, unknown>),
    ),
  };
}

function normalizeMatchTeam(raw: unknown): MatchTeam {
  const t = raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
  return {
    name: str(t.name),
    id: str(t.id),
    score: parseNumeric(t.score),
    won: t.won === true,
  };
}

/** Match detail is a single object; wrap it as a one-element list to keep the
 *  ApiResponse<T> envelope uniform (like player/team). */
export function normalizeMatch(raw: unknown): MatchDetail[] {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return [];
  const m = raw as Record<string, unknown>;
  const allMapsRaw =
    m.all_maps && typeof m.all_maps === "object"
      ? (m.all_maps as Record<string, unknown>)
      : null;
  return [
    {
      id: str(m.id),
      event: str(m.event),
      series: str(m.series),
      status: str(m.status),
      format: str(m.format),
      url: str(m.url),
      veto: str(m.veto),
      teams: (Array.isArray(m.teams) ? m.teams : []).map(normalizeMatchTeam),
      maps: (Array.isArray(m.maps) ? m.maps : []).map((x) =>
        normalizeMap(x as Record<string, unknown>),
      ),
      allMaps: allMapsRaw
        ? {
            teams: (Array.isArray(allMapsRaw.teams) ? allMapsRaw.teams : []).map(
              normalizeMapTeam,
            ),
          }
        : null,
      // Twitch channel logins (bare user_login) — drop any empties; the
      // featured-streamers bar (lib/twitch) unions these across live matches.
      streams: (Array.isArray(m.streams) ? m.streams : [])
        .map(str)
        .filter((s): s is string => Boolean(s)),
    },
  ];
}

/** During a LIVE match the team-level `score` is the SERIES score (maps won),
 *  which stays 0:0 until a map is awarded — so the scorebug reads 0:0 even while
 *  the current map is at e.g. 9–3. This returns the in-progress map's round score
 *  so the scorebug can show it instead. Returns null (→ show the series score)
 *  when: the match isn't live, a map has already been won (series underway — the
 *  series score is correct then), or no map has started yet (0:0 is honest).
 *
 *  With the series level at 0:0, exactly one map is in progress and the rest are
 *  0–0, so the live map is simply the one with rounds played (max total score). */
export function liveMapScore(match: MatchDetail): LiveMapScore | null {
  if (match.status !== "live") return null;
  const [t1, t2] = match.teams;
  const seriesDecided = (t1?.score ?? 0) > 0 || (t2?.score ?? 0) > 0;
  if (seriesDecided) return null; // a map's been won → the series score is right

  let bestIdx = -1;
  let bestTotal = 0;
  match.maps.forEach((mp, i) => {
    const total = (mp.scores[0] ?? 0) + (mp.scores[1] ?? 0);
    if (total > bestTotal) {
      bestTotal = total;
      bestIdx = i;
    }
  });
  if (bestIdx < 0) return null; // no map has started → 0:0 is the honest value

  const mp = match.maps[bestIdx];
  return {
    mapNumber: bestIdx + 1,
    name: mp.name,
    score1: mp.scores[0] ?? null,
    score2: mp.scores[1] ?? null,
  };
}

// ---- loaders (graceful-empty) ----------------------------------------------

async function load<T>(
  path: string,
  transform: (raw: unknown) => T[],
): Promise<ApiResponse<T>> {
  try {
    const raw = await fetchUpstream(path);
    return { data: transform(raw), stale: false };
  } catch (err) {
    // Never throw to the page; surface a stale-empty envelope instead.
    return { data: [], stale: true, error: String(err) };
  }
}

export const getResults = () =>
  load<ResultMatch>("/matches/results", normalizeResult);

export const getUpcoming = () =>
  load<UpcomingMatch>("/matches/upcoming", normalizeUpcoming);

export const getLive = () => load<LiveMatch>("/matches/live", normalizeLive);

export const getRankings = (region = "all") =>
  load<RankedTeam>(`/rankings?region=${encodeURIComponent(region)}`, normalizeRankings);

export const getNews = () => load<NewsArticle>("/news", normalizeNews);

export const getPlayer = (id: string) =>
  load<PlayerDetail>(`/player/${encodeURIComponent(id)}`, normalizePlayer);

/** Player search result row (from /players?q=). The backend wraps this in the
 *  standard {data, stale, error} envelope; this normalizer maps one row. */
export function normalizePlayerSearch(raw: unknown): PlayerSearchResult[] {
  return asList(raw).map((r) => ({
    id: str(r.id),
    alias: str(r.alias),
    team: str(r.team),
    country: str(r.country),
    source: r.source === "vlr" ? "vlr" : "db",
  }));
}

// ---- stats leaderboard (Phase 12) ------------------------------------------
// VLR's region-wide player leaderboard. The headline is R2.0 (VLR's own rating);
// we never compute a composite. The backend already coerces, but we re-coerce
// defensively at this boundary (parseNumeric, null-not-NaN) so the client can
// sort NUMERICALLY — never lexically (the "998" < "1024" string-sort trap).

export function normalizeStats(raw: unknown): StatLeader[] {
  return asList(raw).map((r) => ({
    player: str(r.player),
    playerId: str(r.player_id),
    team: str(r.team),
    r2: parseNumeric(r.r2),
    acs: parseNumeric(r.acs),
    kd: parseNumeric(r.kd),
    kast: parseNumeric(r.kast),
    adr: parseNumeric(r.adr),
    kpr: parseNumeric(r.kpr),
    apr: parseNumeric(r.apr),
    fkpr: parseNumeric(r.fkpr),
    fdpr: parseNumeric(r.fdpr),
    hs: parseNumeric(r.hs),
    clutchPct: parseNumeric(r.clutch_pct),
    clWon: parseNumeric(r.cl_won),
    clPlayed: parseNumeric(r.cl_played),
    kmax: parseNumeric(r.kmax),
    rnd: parseNumeric(r.rnd),
    k: parseNumeric(r.k),
    d: parseNumeric(r.d),
    a: parseNumeric(r.a),
    fk: parseNumeric(r.fk),
    fd: parseNumeric(r.fd),
  }));
}

/** Columns the leaderboard can sort on. "player" sorts alphabetically; every
 *  other key sorts on its NUMERIC value (never the raw string). */
export type StatSortKey =
  | "player"
  | "r2"
  | "acs"
  | "kd"
  | "kast"
  | "adr"
  | "kpr"
  | "fk"
  | "hs";
export type SortDir = "asc" | "desc";

/** R2.0 descending — the leaderboard's natural order (best rating on top). */
export const DEFAULT_STAT_SORT: StatSortKey = "r2";
export const DEFAULT_STAT_DIR: SortDir = "desc";

export const STAT_REGIONS = ["na", "eu"] as const;
export const STAT_TIMESPANS = ["30d", "60d", "90d", "all"] as const;

/** Sort leaderboard rows. CRITICAL: numeric columns compare on the coerced
 *  number, NEVER the raw string — so 1024 sorts above 998 (the lexical-sort trap
 *  would put "1024" below "998"). Nulls always sink to the bottom regardless of
 *  direction. Pure + stable-ish (copies first); returns a new array. */
export function sortLeaders(
  rows: StatLeader[],
  key: StatSortKey,
  dir: SortDir,
): StatLeader[] {
  const sign = dir === "desc" ? -1 : 1;
  return [...rows].sort((a, b) => {
    if (key === "player") {
      return sign * (a.player ?? "").localeCompare(b.player ?? "");
    }
    const av = a[key] as number | null;
    const bv = b[key] as number | null;
    if (av === null && bv === null) return 0;
    if (av === null) return 1; // nulls last
    if (bv === null) return -1;
    return sign * (av - bv); // NUMERIC compare — never lexical
  });
}

/** Load + normalize one leaderboard. The backend returns the {data, stale, error}
 *  envelope (not a bare list), so this unwraps it rather than going through the
 *  generic list `load()`. Graceful-empty on any failure. Server-side only. */
export async function getStats(
  region: string = "na",
  timespan: string = "all",
): Promise<ApiResponse<StatLeader>> {
  try {
    const raw = await fetchUpstream(
      `/stats?region=${encodeURIComponent(region)}&timespan=${encodeURIComponent(timespan)}`,
    );
    const env =
      raw && typeof raw === "object" ? (raw as Record<string, unknown>) : {};
    return {
      data: normalizeStats(env.data),
      stale: env.stale === true,
      ...(env.error ? { error: String(env.error) } : {}),
    };
  } catch (err) {
    return { data: [], stale: true, error: String(err) };
  }
}

// /team/{id} 500s upstream for ids vlr.gg has no page for — the graceful-empty
// catch in load() turns that into { data: [], stale: true, error }.
// See frontend/OPEN-ITEM-team-detail-500.md.
export const getTeam = (id: string) =>
  load<TeamDetail>(`/team/${encodeURIComponent(id)}`, normalizeTeam);

export const getTeamTrend = (id: string, days = 90) =>
  load<TeamTrend>(
    `/trends/team/${encodeURIComponent(id)}?days=${days}`,
    normalizeTrend,
  );

// Phase 8: player rating/ACS trend over banked PlayerSnapshot history. No
// snapshots upstream → a clean 404 (load() catches it → graceful-empty); thin
// history → a valid trend with a young-history note. Server-side fetch only.
export const getPlayerTrend = (id: string, days = 90) =>
  load<PlayerTrend>(
    `/trends/player/${encodeURIComponent(id)}?days=${days}`,
    normalizePlayerTrend,
  );

// ---- dimension-split rating (Phase 13) -------------------------------------

/** Normalize one dimensions response object into the typed shape. */
export function normalizePlayerDimensions(raw: unknown): PlayerDimensions[] {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return [];
  const d = raw as Record<string, unknown>;
  return [
    {
      playerId: str(d.player_id),
      region: str(d.region),
      timespan: str(d.timespan),
      firepower: parseNumeric(d.firepower),
      entry: parseNumeric(d.entry),
      consistency: parseNumeric(d.consistency),
      clutch: parseNumeric(d.clutch),
      lowConfidence: Array.isArray(d.low_confidence)
        ? (d.low_confidence as unknown[]).map(String).filter(Boolean)
        : [],
    },
  ];
}

/** Fetch dimension scores for a player. Tries NA first, then EU, so a player
 *  is found regardless of which regional leaderboard they appear on. Empty
 *  envelope semantics: stale=false only when both regions answered (404 = not
 *  on that leaderboard); stale=true when a lookup actually failed. */
export async function getPlayerDimensions(
  id: string,
  timespan = "all",
): Promise<ApiResponse<PlayerDimensions>> {
  let stale = false;
  for (const region of ["na", "eu"] as const) {
    const result = await load<PlayerDimensions>(
      `/players/${encodeURIComponent(id)}/dimensions?region=${region}&timespan=${timespan}`,
      normalizePlayerDimensions,
    );
    if (result.data.length > 0) return result;
    // A 404 is the endpoint's clean "not in this cohort" answer, not
    // degradation (fetchUpstream's own error format, matched here). Anything
    // else — network down, 5xx — means we can't actually say, so the empty
    // envelope must read stale (RatingBreakdown hides rather than claiming
    // "not on any leaderboard").
    if (result.stale && !/-> 404$/.test(result.error ?? "")) stale = true;
  }
  return { data: [], stale };
}

// /match/{id} 404s upstream for ids vlr.gg has no page for (clean 404 from the
// Phase 7 endpoint) — load()'s catch turns that into { data: [], stale, error }.
export const getMatch = (id: string) =>
  load<MatchDetail>(`/match/${encodeURIComponent(id)}`, normalizeMatch);

// ---- stat ticker (broadcast lower-third) -----------------------------------
// A PRESENTATION layer over data we already serve — NO new scraping. buildTicker
// is a pure curator (tested against committed fixtures); getTicker does the
// bounded orchestration of the existing loaders. "Notable", not random: every
// emitted item clears an explicit threshold below.

/** Notability gates. Tuned for a broadcast feel — meaningful performances, not
 *  filler. Exported so tests can reason about the curation contract. */
export const ACS_NOTABLE = 250; // a standout map ACS (combined, all-maps)
export const TREND_RATING_NOTABLE = 15; // |rating_change| points over the window
export const RANK_MOVE_NOTABLE = 2; // positions climbed/dropped in the window
export const UPSET_RANK_GAP = 3; // winner ranked >= this many spots BELOW loser
/** How many entries the ticker tape carries (kept tight so it stays readable). */
export const TICKER_MAX = 12;
/** Bounds on the fan-out fetches getTicker makes off the match-center data. */
export const TICKER_MATCH_SAMPLE = 4; // recent results we pull detail for (ACS)
export const TICKER_TREND_SAMPLE = 6; // top-ranked teams we pull trends for

function fmtInt(n: number | null): string {
  return n === null ? "—" : String(Math.round(n));
}

function fmtSigned(n: number | null): string {
  if (n === null) return "—";
  const r = Math.round(n);
  return r > 0 ? `+${r}` : String(r); // -0 can't occur after round on an int
}

/** The top single-map ACS performance in one match. Prefers the all-maps
 *  aggregate (the headline number) and falls back to the first map. Returns the
 *  performer + value, or null when no numeric ACS is present. */
function topAcs(
  m: MatchDetail,
): { player: string; team: string | null; acs: number } | null {
  const teams = m.allMaps?.teams.length ? m.allMaps.teams : m.maps[0]?.teams ?? [];
  let best: { player: string; team: string | null; acs: number } | null = null;
  for (const t of teams) {
    for (const p of t.players) {
      const acs = p.stats["ACS"]?.value ?? null;
      if (acs === null || !p.player) continue; // null-not-NaN already guaranteed
      if (!best || acs > best.acs) best = { player: p.player, team: p.team, acs };
    }
  }
  return best;
}

function matchup(m: MatchDetail): string {
  const a = m.teams[0]?.name ?? "TBD";
  const b = m.teams[1]?.name ?? "TBD";
  return `${a} vs ${b}`;
}

/** Curate the notable-stats tape from already-normalized inputs. Pure: no
 *  network, no clock, no randomness — deterministic for a given snapshot, so the
 *  server render and any later poll agree (hydration-safe). Order is fixed
 *  (upsets → top ACS → movers/trends) and the tape is capped at TICKER_MAX. */
export function buildTicker(src: TickerSources): TickerItem[] {
  const upsets: TickerItem[] = [];
  const acs: TickerItem[] = [];
  const movers: TickerItem[] = [];

  // rank lookup by team name (single rankings snapshot → no movement here; the
  // movement signal comes from each team's trend window below).
  const rankByName = new Map<string, number>();
  for (const t of src.rankings) {
    if (t.team && t.rank !== null) rankByName.set(t.team, t.rank);
  }

  // ── upsets: a decided result where the WINNER is ranked well below the loser.
  for (const r of src.results) {
    if (r.score1 === null || r.score2 === null || r.score1 === r.score2) continue;
    const win1 = r.score1 > r.score2;
    const winner = win1 ? r.team1 : r.team2;
    const loser = win1 ? r.team2 : r.team1;
    const ws = win1 ? r.score1 : r.score2;
    const ls = win1 ? r.score2 : r.score1;
    if (!winner || !loser) continue;
    const wr = rankByName.get(winner);
    const lr = rankByName.get(loser);
    if (wr === undefined || lr === undefined) continue;
    if (wr - lr < UPSET_RANK_GAP) continue; // not an upset (favorite won / close)
    upsets.push({
      id: `upset:${r.id ?? `${winner}-${loser}`}`,
      kind: "upset",
      label: "UPSET",
      tone: "warn",
      primary: winner,
      detail: `def. ${loser} · #${wr} over #${lr}${r.event ? ` · ${r.event}` : ""}`,
      value: `${fmtInt(ws)}–${fmtInt(ls)}`,
    });
  }

  // ── top ACS: the headline performance from each sampled match detail.
  for (const m of src.matches) {
    const top = topAcs(m);
    if (!top || top.acs < ACS_NOTABLE) continue;
    acs.push({
      id: `acs:${m.id ?? matchup(m)}:${top.player}`,
      kind: "acs",
      label: "TOP ACS",
      tone: "accent",
      primary: top.player,
      detail: `${top.team ? `${top.team} · ` : ""}${matchup(m)}${m.event ? ` · ${m.event}` : ""}`,
      value: fmtInt(top.acs),
    });
  }

  // ── movers / trends: one item per team — the leaderboard climb/drop if the
  // rank moved enough, else a notable rating swing. (Prevents double-counting a
  // team that both moved and swung.)
  for (const tr of src.trends) {
    if (!tr.team) continue;
    const ranks = tr.ratingTrend
      .map((p) => p.rank)
      .filter((r): r is number => r !== null);
    const firstRank = ranks[0] ?? null;
    const lastRank = ranks[ranks.length - 1] ?? null;
    const rankMove =
      firstRank !== null && lastRank !== null ? firstRank - lastRank : null;

    if (rankMove !== null && Math.abs(rankMove) >= RANK_MOVE_NOTABLE) {
      const climbed = rankMove > 0; // lower rank number = better
      movers.push({
        id: `trend:${tr.teamId ?? tr.team}`,
        kind: "mover",
        label: "MOVER",
        tone: climbed ? "up" : "down",
        primary: tr.team,
        detail: `#${fmtInt(firstRank)} → #${fmtInt(lastRank)} · ${fmtInt(tr.windowDays)}D`,
        value: `${climbed ? "▲" : "▼"}${Math.abs(rankMove)}`,
      });
      continue;
    }

    const change = tr.ratingChange;
    if (change !== null && Math.abs(change) >= TREND_RATING_NOTABLE) {
      const up = change > 0;
      const now = tr.summary?.currentRating ?? null;
      movers.push({
        id: `trend:${tr.teamId ?? tr.team}`,
        kind: "trend",
        label: "TREND",
        tone: up ? "up" : "down",
        primary: tr.team,
        detail: `now ${fmtInt(now)} · ${fmtInt(tr.windowDays)}D`,
        value: fmtSigned(change),
      });
    }
  }

  // fixed priority, de-duped on id (source-derived → stable across renders).
  const seen = new Set<string>();
  const out: TickerItem[] = [];
  for (const item of [...upsets, ...acs, ...movers]) {
    if (seen.has(item.id)) continue;
    seen.add(item.id);
    out.push(item);
    if (out.length >= TICKER_MAX) break;
  }
  return out;
}


/** Aggregate the notable-stats tape. Server-side, force-dynamic via the route.
 *  Fans out (bounded) over the SAME loaders the match center already uses, so it
 *  adds no new upstream surface. Graceful-empty: any failure → empty tape, never
 *  a thrown page; an empty tape simply hides the ticker. */
export async function getTicker(): Promise<ApiResponse<TickerItem>> {
  try {
    const [results, rankings] = await Promise.all([getResults(), getRankings()]);

    // top-ACS source: detail for the most recent completed results (bounded).
    const matchIds = results.data
      .map((r) => r.id)
      .filter((id): id is string => Boolean(id))
      .slice(0, TICKER_MATCH_SAMPLE);
    const matchRes = await Promise.all(matchIds.map((id) => getMatch(id)));
    const matches = matchRes.flatMap((r) => r.data);

    // mover/trend source: trends for the top-ranked teams (bounded).
    const teamIds = rankings.data
      .map((t) => t.id)
      .filter((id): id is string => Boolean(id))
      .slice(0, TICKER_TREND_SAMPLE);
    const trendRes = await Promise.all(teamIds.map((id) => getTeamTrend(id)));
    const trends = trendRes.flatMap((r) => r.data);

    const data = buildTicker({
      results: results.data,
      rankings: rankings.data,
      matches,
      trends,
    });
    // stale if either headline source was stale (detail/trend gaps just thin the
    // tape — they don't mark the whole thing stale).
    return { data, stale: results.stale || rankings.stale };
  } catch (err) {
    return { data: [], stale: true, error: String(err) };
  }
}
