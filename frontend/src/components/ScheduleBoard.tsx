import type { ApiResponse, UpcomingMatch } from "@/types/vlr";
import { groupListing } from "@/lib/matchListings";
import { ListingTeam, MatchListLink, MatchListStatus } from "./MatchListingParts";

export function ScheduleBoard({ response, now }: { response: ApiResponse<UpcomingMatch>; now: Date }) {
  const unavailable = response.stale || Boolean(response.error);
  const groups = groupListing(response.data, m => m.timeUntil, 1, now, unavailable);
  return <div className="ml-board ml-schedule">
    <MatchListStatus kind="schedule" count={response.data.length} unavailable={unavailable} />
    {groups.map((group,i) => <section className="ml-group" key={`${group.key}-${i}`} aria-labelledby={`fixture-group-${i}`}>
      <div className="ml-group-heading"><p className="ml-day">{group.day.label}<span>{group.day.key === "unknown" ? "Start date not confirmed" : "Estimated date · UTC"}</span></p><h2 id={`fixture-group-${i}`}>{group.event ?? "Event unavailable"}</h2></div>
      <ol className="ml-fixtures">{group.matches.map((m,j) => <li className="ml-fixture" key={`${m.id}-${j}`}>
        <div className="ml-clock"><span className="ml-state">{m.timeUntil?.toLowerCase().includes("live") ? "Source says LIVE" : "Upcoming"}</span><strong>{m.startTime ?? "Time TBA"}</strong><span>{m.timeUntil ? `Source countdown: ${m.timeUntil}` : "Countdown unavailable"}</span></div>
        <div className="ml-fixture-match"><div className="ml-fixture-teams"><ListingTeam name={m.team1} id={m.team1Id} logo={m.team1Logo} /><span className="ml-vs">vs</span><ListingTeam name={m.team2} id={m.team2Id} logo={m.team2Logo} /></div><p className="ml-series">{m.series ?? "Stage unavailable"}</p></div>
        <MatchListLink id={m.id} team1={m.team1} team2={m.team2} />
      </li>)}</ol>
    </section>)}
  </div>;
}
