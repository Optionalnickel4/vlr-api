import Link from "next/link";
import type { MatchDetail, MatchTeam } from "@/types/vlr";
import { liveMapScore } from "@/lib/vlr";
import { ScoreDisplay } from "@/components/ScoreDisplay";
import { TeamCrest } from "@/components/TeamCrest";

function TeamIdentity({ team, side }: { team?: MatchTeam; side: number }) {
  const identity = <>
    <TeamCrest name={team?.name ?? null} logo={team?.logo} size="lg" />
    <span className="md-team-name">{team?.name ?? `Team ${side} TBD`}</span>
  </>;
  return <div className="md-team">
    {team?.id ? <Link className="md-team-identity" href={`/team/${team.id}`}>{identity}</Link> : <div className="md-team-identity">{identity}</div>}
    {team?.won && <span className="md-winner">Series winner</span>}
  </div>;
}

/** Keep the live-map scorebug behavior; always distinguish it from maps won. */
export function MatchHeader({ match }: { match: MatchDetail }) {
  const [t1, t2] = match.teams;
  const liveMap = liveMapScore(match);
  const status = match.status === "live" ? "Live coverage" : match.status === "final" ? "Final result" : match.status === "upcoming" ? "Upcoming match" : match.status ?? "Status unavailable";
  return <section className="md-header" aria-label="Match overview">
    <div className="md-header-context">
      <span className="md-status" data-live={match.status === "live"}>{status}</span>
      <div><p className="md-event">{match.event ?? "Event unavailable"}</p>{match.series && <p className="md-stage">{match.series}</p>}</div>
      <span className="md-format">{match.format ?? "Format unavailable"}</span>
    </div>
    <div className="md-versus">
      <TeamIdentity team={t1} side={1} />
      <div className="md-score-center">
        <span className="md-eyebrow">{liveMap ? `Map ${liveMap.mapNumber}${liveMap.name ? ` · ${liveMap.name}` : ""}` : "Series score"}</span>
        <ScoreDisplay score1={liveMap ? liveMap.score1 : t1?.score ?? null} score2={liveMap ? liveMap.score2 : t2?.score ?? null} decided={match.status === "final"} size="lg" className="md-score" />
        {liveMap ? <p className="md-series-score" aria-label={`Series score ${t1?.score ?? "unavailable"} to ${t2?.score ?? "unavailable"}`}><span>Series</span><span>{t1?.score ?? "–"} : {t2?.score ?? "–"}</span></p> : <p className="md-score-caption">Maps won</p>}
      </div>
      <TeamIdentity team={t2} side={2} />
    </div>
    <div className="md-header-footer">
      <div><span className="md-eyebrow">Map veto & picks</span><p>{match.veto ?? "Veto information unavailable."}</p></div>
      {match.url && <a className="md-source" href={match.url} target="_blank" rel="noopener noreferrer">Open on VLR.gg <span aria-hidden>↗</span><span className="sr-only"> (opens in a new tab)</span></a>}
    </div>
  </section>;
}
