import Link from "next/link";
import { TeamCrest } from "./TeamCrest";
import type { LiveMatch, UpcomingMatch } from "@/types/vlr";

export function BroadcastMatch({ match, stale = false }: { match: LiveMatch | UpcomingMatch; stale?: boolean }) {
  const live = "score1" in match;
  return (
    <article className="bc-feature" data-next-feature={!live ? "true" : undefined}>
      <div className="bc-feature-top">
        <span className="bc-tag">{live ? "Live coverage" : "Next up"}</span>
        <span className="bc-event">{match.event ?? "Event unavailable"}</span>
      </div>
      {stale && <p role="status" className="bc-warning">Live updates unavailable — showing last successful scores. Retrying automatically.</p>}
      <div className="bc-versus">
        <div className="bc-team"><TeamCrest name={match.team1} logo={match.team1Logo} size="hero" /><h3>{match.team1 ?? "TBD"}</h3></div>
        <div className="bc-match-center">
          {live ? <div className="bc-score" aria-label={`Score ${match.score1 ?? "–"} to ${match.score2 ?? "–"}`}>
            <span>{match.score1 ?? "–"}</span><span className="bc-score-divider">:</span><span>{match.score2 ?? "–"}</span>
          </div> : <><span className="bc-vs">VS</span><p className="bc-start">{match.timeUntil ?? match.startTime ?? "Time TBA"}</p><span className="bc-micro">{match.timeUntil ? "Until match" : "Scheduled start"}</span></>}
          {live && <span className="bc-micro">{stale ? "Last available score" : "Match in progress"}</span>}
        </div>
        <div className="bc-team"><TeamCrest name={match.team2} logo={match.team2Logo} size="hero" /><h3>{match.team2 ?? "TBD"}</h3></div>
      </div>
      <div className="bc-feature-footer">
        <span>{match.series ?? "Match details"}</span>
        {match.id ? <Link className="bc-action" href={`/match/${match.id}`}>Open match <span aria-hidden>↗</span></Link> : <span className="bc-micro">Match link unavailable</span>}
      </div>
    </article>
  );
}
