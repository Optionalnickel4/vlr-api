import Link from "next/link";
import type { ApiResponse, TeamDetail } from "@/types/vlr";
import { TeamCrest } from "./TeamCrest";

export function TeamOverview({ team }: { team: ApiResponse<TeamDetail> }) {
  const detail = team.data[0];
  const recent = detail.results.slice(0, 5);
  return <>
    <header className="td-identity">
      <div className="td-kicker">Valorant / Team dossier</div>
      <div className="td-identity-main">
        <TeamCrest name={detail.name} logo={detail.logo} size="hero" />
        <div><p className="td-meta">{detail.tag ?? "Team profile"} / {detail.country ?? "Country unavailable"}</p><h1>{detail.name ?? "Team name unavailable"}</h1></div>
      </div>
      <div className="td-summary"><span><strong>{detail.roster.filter(p => !p.isStaff).length}</strong> listed players</span><span><strong>{detail.roster.filter(p => p.isStaff).length}</strong> staff</span><span>Roster and results via VLR.gg</span></div>
    </header>
    {team.stale && <p className="td-notice" role="status">Team updates unavailable — showing last available data.</p>}
    <section aria-labelledby="team-form">
      <div className="td-section-heading"><div><p className="td-kicker">01 / Latest listed matches</p><h2 id="team-form">Recent form</h2></div><p>Up to five results · source order</p></div>
      {recent.length ? <><ol className="td-form">{recent.map((r, i) => <li key={r.id ?? i}>
        <span className="td-verdict" data-result={r.result ?? "unknown"}>{r.result === "win" ? "Win" : r.result === "loss" ? "Loss" : "Unknown"}</span>
        <span className="td-opponent"><TeamCrest name={r.opponent} logo={r.opponentLogo} size="table" />{r.opponentId ? <Link prefetch={false} href={`/team/${r.opponentId}`}>{r.opponent ?? "Opponent unavailable"}</Link> : <span>{r.opponent ?? "Opponent unavailable"}</span>}</span>
        {r.id ? <Link className="td-form-score" href={`/match/${r.id}`} aria-label={`Match against ${r.opponent ?? "unknown opponent"}, score ${r.score ?? "unavailable"}`}>{r.score ?? "—"} <span aria-hidden>↗</span></Link> : r.url ? <a className="td-form-score" href={r.url} target="_blank" rel="noopener noreferrer">{r.score ?? "—"} ↗</a> : <span className="td-form-score">{r.score ?? "—"}</span>}
        <span className="td-meta">{r.event ?? "Event unavailable"}</span>
        <span className="td-meta">{r.date ?? "Match date unavailable"}</span>
      </li>)}</ol><p className="td-caption">Scores and verdicts are supplied by the source; score order is unchanged. This list is separate from the history window below.</p></> : <p className="td-empty">{team.stale ? "Recent form unavailable." : "No recent results listed by the source."}</p>}
    </section>
  </>;
}
