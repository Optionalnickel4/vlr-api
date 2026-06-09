// Domain types for the broadcast dashboard.
//
// These are what UI components consume — they never see raw vlr-api JSON. All
// mapping from upstream shapes happens in `@/lib/vlr`. Numeric fields are
// `number | null` (parseNumeric returns null, never NaN). vlr-api URLs are
// already absolute; we carry them through verbatim.

/** Uniform envelope every route handler / data-layer call returns. */
export interface ApiResponse<T> {
  data: T[];
  stale: boolean;
  error?: string;
}

/** A completed match (from /matches/results). */
export interface ResultMatch {
  id: string | null;
  team1: string | null;
  team2: string | null;
  score1: number | null;
  score2: number | null;
  time: string | null; // eta || time (raw display string from upstream)
  series: string | null;
  event: string | null;
  url: string | null;
}

/** A scheduled match (from /matches/upcoming). No real timestamp upstream —
 *  the countdown is the eta display string only. */
export interface UpcomingMatch {
  id: string | null;
  team1: string | null;
  team2: string | null;
  timeUntil: string | null; // eta
  series: string | null;
  event: string | null;
  url: string | null;
}

/** A live match (from /matches/live). DEGRADED: no current-map / mapNumber /
 *  logos upstream, so those are intentionally absent. */
export interface LiveMatch {
  id: string | null;
  team1: string | null;
  team2: string | null;
  score1: number | null;
  score2: number | null;
  series: string | null;
  event: string | null;
  url: string | null;
}

/** A ranked team (from /rankings). record/earnings/logo are null/absent
 *  upstream and dropped; rating is carried (net vs the v5 shape). */
export interface RankedTeam {
  id: string | null; // team_id
  rank: number | null;
  team: string | null;
  country: string | null;
  rating: number | null;
}

/** A news article (from /news). meta is split into date + author, with a
 *  verbatim fallback when the split is fragile. */
export interface NewsArticle {
  title: string | null;
  description: string | null;
  date: string | null;
  author: string | null;
  url: string | null;
}

// ---- player detail (from /player/{id}) -------------------------------------

/** Per-agent stat row. `stats` keys are display-cased with colons ("K:D",
 *  "KAST") and are read VERBATIM — do not normalize or rename them. */
export interface AgentStat {
  agent: string | null;
  stats: Record<string, string>;
}

export interface PlayerMatch {
  id: string | null;
  url: string | null;
  opponent: string | null;
  result: "win" | "loss" | null;
  score: string | null;
  event: string | null;
}

export interface PlayerDetail {
  id: string | null;
  alias: string | null;
  realName: string | null;
  country: string | null;
  team: string | null;
  teamId: string | null;
  teamUrl: string | null;
  agentStats: AgentStat[];
  matches: PlayerMatch[];
}

// ---- team detail (from /team/{id}) -----------------------------------------
// ⚠️ /team/{id} 500s for ids vlr.gg has no page for (upstream 404 → unhandled
// raise_for_status). The data layer guards this to graceful-empty. See
// frontend/OPEN-ITEM-team-detail-500.md.

export interface RosterMember {
  alias: string | null;
  realName: string | null;
  role: string | null;
  country: string | null;
  playerId: string | null;
  url: string | null;
  isCaptain: boolean;
  isStaff: boolean;
}

export interface TeamMatch {
  id: string | null;
  url: string | null;
  opponent: string | null;
  opponentId: string | null;
  result: "win" | "loss" | null;
  score: string | null;
  event: string | null;
  date: string | null;
}

export interface TeamDetail {
  id: string | null;
  name: string | null;
  tag: string | null;
  country: string | null;
  countryCode: string | null;
  logo: string | null;
  roster: RosterMember[];
  results: TeamMatch[];
  upcoming: TeamMatch[];
}

// ---- team trends (from /trends/team/{id}) ----------------------------------
// Net-new vs v5: reads vlr-api's banked history. Upstream already coerces
// ratings to numbers; we keep parseNumeric defensively at the boundary anyway.

export interface RatingPoint {
  capturedAt: string | null;
  rating: number | null;
  rank: number | null;
}

export interface TrendResult {
  vlrId: string | null;
  opponent: string | null;
  result: "win" | "loss" | null;
  score: string | null;
  event: string | null;
  capturedAt: string | null;
}

export interface TrendSummary {
  points: number;
  wins: number;
  losses: number;
  currentRating: number | null;
  peakRating: number | null;
}

export interface TeamTrend {
  teamId: string | null;
  team: string | null;
  windowDays: number | null;
  ratingTrend: RatingPoint[];
  ratingChange: number | null;
  resultsInWindow: TrendResult[];
  summary: TrendSummary | null;
  note?: string;
}
