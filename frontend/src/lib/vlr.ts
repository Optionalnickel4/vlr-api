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
  PlayerMatch,
  RankedTeam,
  RatingPoint,
  ResultMatch,
  RosterMember,
  TeamDetail,
  TeamMatch,
  TeamTrend,
  TrendResult,
  UpcomingMatch,
} from "@/types/vlr";

export const VLR_API_BASE =
  process.env.VLR_API_BASE ?? "http://127.0.0.1:8000/api/v1";

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

/** Below this spread (max − min rating across the window) the trend is
 *  effectively flat: a straight line carries no signal and reads as a render
 *  bug, so the panel shows the honest thin-history note instead. NOT a data fix
 *  — a ceiling team genuinely holds rating; this is purely a presentation gate. */
export const FLAT_EPSILON = 0.5;

/** Whether a trend series has enough real, *moving* data to draw a sparkline.
 *  Two thin states collapse to "no line": fewer than 2 real ratings (history
 *  still young) OR ≥2 ratings with spread < FLAT_EPSILON (the degenerate flat
 *  case — e.g. a rank-1 team pinned at 2000). The honest-state decision lives
 *  here in the tested data layer, not inline in the component. */
export function shouldRenderTrendLine(points: RatingPoint[]): boolean {
  const ratings = points
    .map((p) => p.rating)
    .filter((r): r is number => r !== null);
  if (ratings.length < 2) return false;
  return Math.max(...ratings) - Math.min(...ratings) >= FLAT_EPSILON;
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
    },
  ];
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

// /match/{id} 404s upstream for ids vlr.gg has no page for (clean 404 from the
// Phase 7 endpoint) — load()'s catch turns that into { data: [], stale, error }.
export const getMatch = (id: string) =>
  load<MatchDetail>(`/match/${encodeURIComponent(id)}`, normalizeMatch);
