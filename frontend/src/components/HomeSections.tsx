import { LiveMatches } from "./LiveMatches";
import { MatchCard } from "./MatchCard";
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
  return <MatchSection title="Next up" stale={response.stale || Boolean(response.error)} isEmpty={!match}
    emptyLabel="No upcoming matches scheduled." viewAllHref="/schedule" viewAllLabel="Full schedule">
    {match && <MatchCard state="upcoming" {...match} label={match.timeUntil} />}
  </MatchSection>;
}

export async function HomeLive({ live, upcoming }: {
  live: Promise<ApiResponse<LiveMatch>>;
  upcoming: Promise<ApiResponse<UpcomingMatch>>;
}) {
  return <LiveMatches initial={await live} confirmedEmptyFallback={
    <Suspense fallback={<SectionLoading label="next match" />}><NextMatch upcoming={upcoming} /></Suspense>
  } />;
}

export async function UpcomingSnapshot({ data }: { data: Promise<ApiResponse<UpcomingMatch>> }) {
  const response = await data;
  return <MatchSection title="Upcoming" count={response.data.length} stale={response.stale || Boolean(response.error)}
    isEmpty={!response.data.length} emptyLabel="No upcoming matches scheduled." viewAllHref="/schedule" viewAllLabel="Full schedule">
    {response.data.slice(0, HOME_SNAPSHOT_LIMIT).map((m, i) => <MatchCard key={m.id ?? i} state="upcoming" {...m} label={m.timeUntil} />)}
  </MatchSection>;
}

export async function ResultsSnapshot({ data }: { data: Promise<ApiResponse<ResultMatch>> }) {
  const response = await data;
  return <MatchSection title="Results" count={response.data.length} stale={response.stale || Boolean(response.error)}
    isEmpty={!response.data.length} emptyLabel="No recent results." viewAllHref="/results" viewAllLabel="All results">
    {response.data.slice(0, HOME_SNAPSHOT_LIMIT).map((m, i) => <MatchCard key={m.id ?? i} state="result" {...m} label={m.time} />)}
  </MatchSection>;
}

export async function HomeNews({ data }: { data: Promise<ApiResponse<NewsArticle>> }) {
  return <NewsPanel news={await data} leadStory viewAllHref="/news" viewAllLabel="All news" />;
}

export async function HomeRankings({ data }: { data: Promise<ApiResponse<RankedTeam>> }) {
  return <RankingsPanel rankings={await data} viewAllHref="/rankings" viewAllLabel="Full rankings" />;
}
