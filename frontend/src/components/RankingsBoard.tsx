import Link from "next/link";
import type { ApiResponse, RankedTeam } from "@/types/vlr";
import { TeamCrest } from "./TeamCrest";

// Matches the existing backend allow-list; country is not a ladder identifier.
export const RANKING_REGIONS: Record<string, string> = {
  all: "All regional ladders", "north-america": "North America", europe: "Europe", brazil: "Brazil",
  "asia-pacific": "Asia-Pacific", korea: "Korea", china: "China", japan: "Japan", "la-s": "Latin America South",
  "la-n": "Latin America North", oceania: "Oceania", gc: "Game Changers", mena: "MENA", collegiate: "Collegiate",
};
export function rankingGroups(rows: RankedTeam[]) {
  const groups: RankedTeam[][] = [];
  for (const row of rows) {
    const current = groups.at(-1);
    const previous = current?.at(-1)?.rank;
    if (!current || (row.rank !== null && previous != null && row.rank < previous)) groups.push([row]);
    else current.push(row);
  }
  return groups;
}
export function RankingsBoard({ rankings, region = "all" }: { rankings: ApiResponse<RankedTeam>; region?: string }) {
  const groups = rankingGroups(rankings.data);
  const unavailable = rankings.stale || Boolean(rankings.error);
  return <div className="ladder-page">
    <header className="ld-masthead"><p className="ld-kicker">Valorant / Team standings</p><h1>Rankings<span>.</span></h1><p>Regional competition. Team by team.</p><div className="ld-context">{RANKING_REGIONS[region]} · {rankings.data.length} listed teams · Capture time unavailable</div></header>
    <nav className="ld-regions" aria-label="Ranking regions">{Object.entries(RANKING_REGIONS).map(([key,label])=><Link key={key} prefetch={false} href={key==='all'?'/rankings':`/rankings?region=${key}`} aria-current={key===region?'page':undefined}>{label}</Link>)}</nav>
    <p className="ld-note">Ranks and ratings are shown in source order within each ladder, not a global ranking. Country / region is the source team label. No movement or match sample is supplied.{region==='all' && ' Ladder boundaries follow rank resets; their region names are not supplied. Choose a named region for a specific regional view.'}</p>
    {unavailable && <p className="ld-notice" role="status">{rankings.data.length?'Updates unavailable — showing last available rankings.':'Rankings unavailable — could not load this region.'}</p>}
    {!rankings.data.length && !unavailable && <p className="ld-notice">No rankings available.</p>}
    <div className="ld-ladders">{groups.map((rows,i)=><section className="ld-ladder" key={i} aria-labelledby={`ladder-${i}`}>
      <div className="ld-section-title"><h2 id={`ladder-${i}`}>{region==='all'?`Regional ladder ${i+1}`:RANKING_REGIONS[region]}</h2><span>{rows.length} listed teams</span></div>
      <div className="ld-scroll ld-ranking-scroll" role="region" aria-label={`${region==='all'?`Regional ladder ${i+1}`:RANKING_REGIONS[region]} table; scroll horizontally if needed`} tabIndex={0}>
        <table className="ld-table ld-rank-table"><thead><tr><th scope="col">Rank</th><th scope="col">Team / source country or region</th><th scope="col">Rating</th></tr></thead><tbody>{rows.map((t,j)=><tr key={`${t.id}-${j}`}><td>{t.rank??'—'}</td><th scope="row"><div className="ld-team"><TeamCrest name={t.team}/><div>{t.id?<Link href={`/team/${t.id}`}>{t.team??'Team unavailable'}</Link>:<span>{t.team??'Team unavailable'}</span>}<small>{t.country??'Country / region unavailable'}</small></div></div></th><td>{t.rating??'—'}</td></tr>)}</tbody></table>
      </div>
    </section>)}</div>
  </div>;
}
