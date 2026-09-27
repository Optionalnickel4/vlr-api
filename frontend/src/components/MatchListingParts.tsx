import Link from "next/link";
import { TeamCrest } from "./TeamCrest";

export function MatchListHeader({ kind, count, unavailable, now }: { kind: "schedule" | "results"; count: number; unavailable: boolean; now: Date }) {
  return <header className="ml-masthead">
    <div><p className="ml-kicker">Valorant / {kind === "schedule" ? "Upcoming coverage" : "Completed matches"}</p><h1>{kind === "schedule" ? "Schedule" : "Results"}<span>.</span></h1><p className="ml-deck">{kind === "schedule" ? "Know who plays next." : "The final word, match by match."}</p></div>
    <div className="ml-summary"><strong>{unavailable && !count ? "—" : count}</strong><span>{unavailable ? "last available matches" : kind === "schedule" ? "upcoming fixtures" : "completed results"}</span><Link href={kind === "schedule" ? "/results" : "/schedule"}>{kind === "schedule" ? "View results" : "View schedule"} <span aria-hidden>↗</span></Link></div>
    <p className="ml-timing">Date headings are estimates from relative source timings at page load ({now.toISOString().slice(0,16).replace("T"," ")} UTC), not confirmed match dates. Source age and clock timezone are unavailable. Feed order is preserved.</p>
  </header>;
}

export function MatchListStatus({ kind, count, unavailable }: { kind: "schedule" | "results"; count: number; unavailable: boolean }) {
  if (unavailable) return <p className="ml-notice" role="status">{count ? "Updates unavailable — showing last available matches. Estimated dates are withheld because source timings may be old." : `${kind === "schedule" ? "Schedule" : "Results"} unavailable — couldn't load the match feed.`}</p>;
  if (!count) return <p className="ml-empty">{kind === "schedule" ? "No upcoming matches scheduled." : "No recent results."}</p>;
  return null;
}

export function ListingTeam({ name }: { name: string | null }) {
  return <span className="ml-team"><TeamCrest name={name} /><span>{name ?? "Team TBD"}</span></span>;
}

export function MatchListLink({ id, team1, team2 }: { id: string | null; team1: string | null; team2: string | null }) {
  return id ? <Link className="ml-match-link" href={`/match/${id}`} aria-label={`Open match: ${team1 ?? "Team TBD"} vs ${team2 ?? "Team TBD"}`}>Open match <span aria-hidden>↗</span></Link> : <span className="ml-missing-link">Match link unavailable</span>;
}
