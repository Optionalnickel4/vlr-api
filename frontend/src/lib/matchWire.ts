import { teamInitials } from "./schedule";
import type {
  LiveMatch,
  MatchDetail,
  MatchWireItem,
  MatchWireSources,
  MatchWireTeam,
  RankedTeam,
  ResultMatch,
  TeamTrend,
  UpcomingMatch,
} from "@/types/vlr";

export const MATCH_WIRE_MAX = 12;
export const MATCH_WIRE_CAPS = { live: 4, upcoming: 4, final: 3, mover: 2 } as const;

type Card = LiveMatch | UpcomingMatch | ResultMatch;

function team(card: Card, side: 1 | 2): MatchWireTeam {
  const name = card[`team${side}`] ?? "TBD";
  return {
    id: card[`team${side}Id`] ?? null,
    name,
    shortName: card[`team${side}ShortName`] ?? teamInitials(name),
    logo: card[`team${side}Logo`] ?? null,
    score: "score1" in card ? card[`score${side}`] ?? null : null,
  };
}

function liveContext(detail: MatchDetail | undefined): string | null {
  if (!detail) return null;
  let current = detail.maps[0];
  for (const map of detail.maps) {
    if (map.rounds.some(round => round.winner !== null)) current = map;
  }
  if (!current) return detail.series;
  const decided = current.rounds.filter(round => round.winner !== null);
  const round = decided.at(-1)?.round;
  return [current.name, round != null ? `Round ${round + 1}` : null].filter(Boolean).join(" · ") || detail.series;
}

function liveItem(card: LiveMatch, details: Map<string, MatchDetail>): MatchWireItem | null {
  if (!card.id) return null;
  const detail = details.get(card.id);
  const teams: [MatchWireTeam, MatchWireTeam] = [team(card, 1), team(card, 2)];
  if (detail?.teams.length === 2) {
    detail.teams.forEach((source, index) => {
      teams[index] = {
        ...teams[index],
        id: source.id ?? teams[index].id,
        name: source.name ?? teams[index].name,
        shortName: teamInitials(source.name ?? teams[index].name),
        logo: source.logo ?? teams[index].logo,
      };
    });
  }
  return { id: `live:${card.id}`, kind: "live", href: `/match/${card.id}`, status: "LIVE", teams,
    event: card.event, context: liveContext(detail) ?? card.series, time: null, winnerId: null };
}

function upcomingItem(card: UpcomingMatch): MatchWireItem | null {
  if (!card.id) return null;
  return { id: `upcoming:${card.id}`, kind: "upcoming", href: `/match/${card.id}`, status: "UPCOMING",
    teams: [team(card, 1), team(card, 2)], event: card.event, context: card.series,
    time: card.startTime ?? card.timeUntil, winnerId: null };
}

function finalItem(card: ResultMatch): MatchWireItem | null {
  if (!card.id) return null;
  const teams: [MatchWireTeam, MatchWireTeam] = [team(card, 1), team(card, 2)];
  let winnerId: string | null = null;
  if (card.score1 !== null && card.score2 !== null && card.score1 !== card.score2) {
    const side = card.score1 > card.score2 ? 0 : 1;
    winnerId = teams[side].id ?? `side-${side + 1}`;
  }
  return { id: `final:${card.id}`, kind: "final", href: `/match/${card.id}`, status: "FINAL", teams,
    event: card.event, context: card.series, time: card.time, winnerId };
}

function moverItem(trend: TeamTrend, rankings: Map<string, RankedTeam>): MatchWireItem | null {
  if (!trend.teamId || !trend.team) return null;
  const ranks = trend.ratingTrend.map(point => point.rank).filter((rank): rank is number => rank !== null);
  if (ranks.length < 2) return null;
  const previousRank = ranks[0];
  const currentRank = ranks.at(-1)!;
  const delta = previousRank - currentRank;
  if (Math.abs(delta) < 2) return null;
  const ranked = rankings.get(trend.teamId);
  return {
    id: `mover:${trend.teamId}`, kind: "mover", href: `/team/${trend.teamId}`, status: "RANK",
    team: { id: trend.teamId, name: trend.team, shortName: teamInitials(trend.team),
      logo: trend.logo ?? ranked?.logo ?? null, score: null },
    direction: delta > 0 ? "up" : "down", positions: Math.abs(delta), previousRank, currentRank,
    context: ranked?.country ?? (trend.windowDays != null ? `${trend.windowDays}D ranking` : "Ranking movement"),
  };
}

/** Pure, deterministic curation. Category caps preserve breadth and fixed group
 * order keeps live coverage ahead of scheduled matches, finals, and movers. */
export function buildMatchWire(source: MatchWireSources): MatchWireItem[] {
  const details = new Map(source.liveDetails.flatMap(detail => detail.id ? [[detail.id, detail] as const] : []));
  const rankings = new Map(source.rankings.flatMap(row => row.id ? [[row.id, row] as const] : []));
  const live = source.live.map(card => liveItem(card, details)).filter((item): item is MatchWireItem => item !== null).slice(0, MATCH_WIRE_CAPS.live);
  const upcoming = source.upcoming.map(upcomingItem).filter((item): item is MatchWireItem => item !== null).slice(0, MATCH_WIRE_CAPS.upcoming);
  const finals = source.results.map(finalItem).filter((item): item is MatchWireItem => item !== null).slice(0, MATCH_WIRE_CAPS.final);
  const movers = source.trends.map(trend => moverItem(trend, rankings)).filter((item): item is MatchWireItem => item !== null).slice(0, MATCH_WIRE_CAPS.mover);
  return [...live, ...upcoming, ...finals, ...movers].slice(0, MATCH_WIRE_MAX);
}
