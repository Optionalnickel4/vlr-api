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

// ---- player trends (from /trends/player/{id}, Phase 8) ---------------------
// The player analog of the team rating trend. NOTE: player history is THIN —
// snapshots only accumulate when a player page is fetched, so most players show
// the honest young-history note until captures build up. Each point is a
// rounds-weighted overall rating + ACS for that capture (the backend aggregates
// the per-agent rows). parseNumeric keeps values null-not-NaN at the boundary.

export interface PlayerRatingPoint {
  capturedAt: string | null;
  rating: number | null;
  acs: number | null;
  rounds: number | null;
}

export interface PlayerTrendSummary {
  points: number;
  currentRating: number | null;
  peakRating: number | null;
  currentAcs: number | null;
  peakAcs: number | null;
}

export interface PlayerTrend {
  playerId: string | null;
  player: string | null;
  team: string | null;
  windowDays: number | null;
  ratingTrend: PlayerRatingPoint[];
  ratingChange: number | null;
  acsChange: number | null;
  summary: PlayerTrendSummary | null;
  note?: string;
}

// ---- match detail (from /match/{id}, Phase 7) ------------------------------
// The API already coerces scoreboard values: each stat cell is { value, both,
// t, ct } where `value` is a number|null (KAST/HS% come through parse_percent as
// the bare number, e.g. 59, with `both` keeping the "59%" display string). The
// data layer re-coerces `value` defensively (parseNumeric, null-not-NaN).

/** One scoreboard stat cell. `value` is the combined (mod-both) number; `t`/`ct`
 *  keep the attack/defense side-split display strings. */
export interface MatchStatCell {
  value: number | null;
  both: string | null;
  t: string | null;
  ct: string | null;
}

export interface MatchPlayer {
  player: string | null;
  team: string | null;
  playerId: string | null;
  country: string | null;
  agent: string | null;
  stats: Record<string, MatchStatCell>;
}

export interface MatchMapTeam {
  name: string | null;
  score: number | null;
  players: MatchPlayer[];
}

/** One round in the timeline. `winner` is 1|2 (team index) or null (not played);
 *  `side` is the winner's attack/defense; `outcome` is elim|boom|defuse|time. */
export interface MatchRound {
  round: number | null;
  winner: 1 | 2 | null;
  side: "t" | "ct" | null;
  outcome: string | null;
  score: string | null; // cumulative "team1-team2"
}

export interface MatchMap {
  gameId: string | null;
  name: string | null;
  picked: boolean;
  decider: boolean;
  scores: (number | null)[]; // [team1, team2]
  teams: MatchMapTeam[];
  rounds: MatchRound[];
}

export interface MatchTeam {
  name: string | null;
  id: string | null;
  score: number | null; // series score (maps won)
  won: boolean;
}

export interface MatchDetail {
  id: string | null;
  event: string | null;
  series: string | null;
  status: string | null; // "final" | "live" | null
  format: string | null; // "BO3"
  url: string | null;
  veto: string | null;
  teams: MatchTeam[];
  maps: MatchMap[];
  allMaps: { teams: MatchMapTeam[] } | null;
  /** Twitch channel logins the match page lists (bare user_login, e.g.
   *  "valorant_br"); the featured-streamers bar unions these across live
   *  matches and queries Helix for who's actually live. Empty = none. */
  streams: string[];
}

// ---- featured streamers (Twitch Helix, server-side only) -------------------
// The project's first EXTERNAL API integration. The client secret never reaches
// the browser — all Twitch calls happen server-side in @/lib/twitch. A
// FeaturedStream is a channel that is LIVE right now and streaming Valorant.

export interface FeaturedStream {
  login: string; // twitch user_login (channel handle) — lowercased
  displayName: string | null; // user_name
  viewers: number | null; // viewer_count (parseNumeric, null-not-NaN)
  title: string | null;
  game: string | null; // game_name (filtered to Valorant before display)
  thumbnail: string | null; // thumbnail_url
  url: string; // https://www.twitch.tv/<login>
}

// ---- stat ticker (broadcast lower-third) -----------------------------------
// A PRESENTATION aggregate over endpoints we already serve — no new scraping.
// buildTicker() curates "notable" stats (top ACS, upsets, leaderboard movers,
// rating-trend deltas) into a flat, render-ready list. Every metric is a
// pre-formatted string (dash, never NaN); `tone` carries meaning, not decoration.

export type TickerKind =
  | "acs"
  | "upset"
  | "mover"
  | "trend"
  // live-match mode (in-game stats derived from the Phase 7 match detail)
  | "live-score"
  | "live-performer"
  | "live-streak"
  | "live-momentum"
  | "live-fk"
  | "live-veto";

/** One scrolling ticker entry. The component is dumb: it styles by `tone` and
 *  prints the strings verbatim. Numbers are already coerced + formatted in the
 *  data layer (null → "—"), so nothing here can render NaN. */
export interface TickerItem {
  id: string; // stable, source-derived key (no Math.random / Date.now)
  kind: TickerKind;
  label: string; // uppercase category cap, e.g. "TOP ACS" / "UPSET" / "MOVER"
  tone: "up" | "down" | "warn" | "accent" | "neutral"; // matches BadgeTone
  primary: string; // lead subject (player / team)
  detail: string; // context (matchup / event / rank move)
  value: string; // formatted metric ("252", "+24", "▲3"), "—" when null
}

/** Already-normalized inputs the curator aggregates. The route fetches these
 *  (bounded) via the existing loaders; buildTicker itself is pure + testable. */
export interface TickerSources {
  results: ResultMatch[];
  rankings: RankedTeam[];
  matches: MatchDetail[];
  trends: TeamTrend[];
}
