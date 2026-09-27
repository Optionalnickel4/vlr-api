import type { ApiResponse, ResultMatch } from "@/types/vlr";
import { groupListing } from "@/lib/matchListings";
import { ListingTeam, MatchListLink, MatchListStatus } from "./MatchListingParts";

export function ResultsBoard({ response, now }: { response: ApiResponse<ResultMatch>; now: Date }) {
  const unavailable = response.stale || Boolean(response.error);
  const groups = groupListing(response.data, m => m.time, -1, now, unavailable);
  return <div className="ml-board ml-results">
    <MatchListStatus kind="results" count={response.data.length} unavailable={unavailable} />
    {groups.map((group,i) => <section className="ml-group" key={`${group.key}-${i}`} aria-labelledby={`result-group-${i}`}>
      <div className="ml-group-heading"><p className="ml-day">{group.day.label}<span>{group.day.key === "unknown" ? "Match date not supplied" : "Estimated date · UTC"}</span></p><h2 id={`result-group-${i}`}>{group.event ?? "Event unavailable"}</h2></div>
      <ol className="ml-result-grid">{group.matches.map((m,j) => <li className="ml-result" key={`${m.id}-${j}`}>
        <div className="ml-result-top"><span className="ml-state">Final</span><span>Source timing: {m.time ?? "Unavailable"}</span></div>
        <div className="ml-score-teams">{([{name:m.team1,score:m.score1,other:m.score2},{name:m.team2,score:m.score2,other:m.score1}]).map((team,k)=>{
          const won = team.score !== null && team.other !== null && team.score > team.other;
          return <div className="ml-score-row" data-winner={won} key={k}><ListingTeam name={team.name} /><span className="ml-team-result">{won ? "Winner" : ""}</span><strong aria-label={`${team.name ?? "Team TBD"} score ${team.score ?? "unavailable"}`}>{team.score ?? "—"}</strong></div>;
        })}</div>
        <p className="ml-series">{m.series ?? "Stage unavailable"}</p>
        <div className="ml-result-footer"><span>{m.score1 === null || m.score2 === null ? "Score incomplete" : m.score1 === m.score2 ? "Level score reported" : "Completed result"}</span><MatchListLink id={m.id} team1={m.team1} team2={m.team2} /></div>
      </li>)}</ol>
    </section>)}
  </div>;
}
