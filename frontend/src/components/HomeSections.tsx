import { LiveMatches } from "./LiveMatches";
import Link from "next/link";
import { BroadcastMatch } from "./BroadcastMatch";
import { TeamCrest } from "./TeamCrest";
import { MatchSection } from "./MatchSection";
import { NewsPanel } from "./NewsPanel";
import { RankingsPanel } from "./RankingsPanel";
import { HOME_SNAPSHOT_LIMIT } from "@/lib/vlr";
import type { ApiResponse, LiveMatch, UpcomingMatch, ResultMatch, NewsArticle, RankedTeam } from "@/types/vlr";
import { Suspense } from "react";

export function SectionLoading({ label }: { label: string }) {
  return <div role="status" className="min-h-32 rounded-lg border border-line bg-panel p-4 text-sm text-mut">{`Loading ${label}…`}</div>;
}

async function NextMatch({ upcoming }: { upcoming: Promise<ApiResponse<UpcomingMatch>> }) {
  const response = await upcoming;
  const match = response.data[0];
  return match ? <>
    {(response.stale || response.error) && <p role="status" className="bc-warning">Upcoming updates unavailable — showing last available data.</p>}
    <BroadcastMatch match={match} />
  </> : <MatchSection title="Next up" stale={response.stale || Boolean(response.error)} isEmpty
    emptyLabel="No upcoming matches scheduled." viewAllHref="/schedule" viewAllLabel="Full schedule" />;
}

export async function HomeLive({ live, upcoming }: {
  live: Promise<ApiResponse<LiveMatch>>;
  upcoming: Promise<ApiResponse<UpcomingMatch>>;
}) {
  return <LiveMatches broadcast initial={await live} confirmedEmptyFallback={
    <Suspense fallback={<SectionLoading label="next match" />}><NextMatch upcoming={upcoming} /></Suspense>
  } />;
}

export async function UpcomingSnapshot({ data }: { data: Promise<ApiResponse<UpcomingMatch>> }) {
  const response = await data;
  return <section className="bc-upcoming" aria-labelledby="upcoming-heading">
    <div className="bc-section-heading"><div><span className="bc-kicker">The schedule</span><h2 id="upcoming-heading">UP NEXT<span className="sr-only"> — Upcoming</span></h2></div><span className="bc-total">{response.data.length} scheduled</span></div>
    {(response.stale || response.error) && <p role="status" className="bc-warning">Updates unavailable.</p>}
    {!response.data.length && !response.stale && !response.error && <p className="bc-empty">No upcoming matches scheduled.</p>}
    <div className="bc-upcoming-list">
      {response.data.slice(0, HOME_SNAPSHOT_LIMIT).map((m, i) => {
        const content = <><span className="bc-fixture-time">{m.timeUntil ?? m.startTime ?? "Time TBA"}</span><span className="bc-fixture-teams">{m.team1 ?? "TBD"}<span className="bc-micro">vs</span>{m.team2 ?? "TBD"}</span><span className="bc-fixture-event">{m.event ?? "Event unavailable"}</span><span className="bc-row-arrow" aria-hidden>↗</span></>;
        return m.id ? <Link key={m.id} className="bc-fixture" href={`/match/${m.id}`}>{content}</Link> : <div key={i} className="bc-fixture">{content}</div>;
      })}
    </div>
    <Link className="bc-section-link" href="/schedule">Full schedule <span aria-hidden>→</span></Link>
  </section>;
}

export async function ResultsSnapshot({ data }: { data: Promise<ApiResponse<ResultMatch>> }) {
  const response = await data;
  return <section className="bc-results" aria-labelledby="results-heading">
    <div className="bc-section-heading"><div><span className="bc-kicker">The final word</span><h2 id="results-heading">RESULTS</h2></div><span className="bc-total">{response.data.length} recent</span></div>
    {(response.stale || response.error) && <p role="status" className="bc-warning">Updates unavailable.</p>}
    {!response.data.length && !response.stale && !response.error && <p className="bc-empty">No recent results.</p>}
    <div className="bc-results-list">{response.data.slice(0, HOME_SNAPSHOT_LIMIT).map((m, i) => {
      const content = <><div className="bc-result-teams">{[[m.team1,m.score1,m.score2],[m.team2,m.score2,m.score1]].map(([name,score,other], n) => <div key={n} className={typeof score === "number" && typeof other === "number" && score > other ? "bc-winner" : ""}><TeamCrest name={name as string | null} /><span>{name ?? "TBD"}</span><strong>{score ?? "–"}</strong></div>)}</div><p className="bc-fixture-event">{m.event ?? "Event unavailable"} <span>· {m.time ?? "Final"}</span></p></>;
      return m.id ? <Link className="bc-result" key={m.id} href={`/match/${m.id}`}>{content}</Link> : <div className="bc-result" key={i}>{content}</div>;
    })}</div>
    <Link className="bc-section-link" href="/results">All results <span aria-hidden>→</span></Link>
  </section>;
}

export async function HomeNews({ data }: { data: Promise<ApiResponse<NewsArticle>> }) {
  return <NewsPanel news={await data} leadStory viewAllHref="/news" viewAllLabel="All news" />;
}

export async function HomeRankings({ data }: { data: Promise<ApiResponse<RankedTeam>> }) {
  return <RankingsPanel broadcast rankings={await data} viewAllHref="/rankings" viewAllLabel="Full rankings" />;
}
