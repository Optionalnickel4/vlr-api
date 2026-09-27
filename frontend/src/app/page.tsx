import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { getLive, getNews, getRankings, getResults, getUpcoming } from "@/lib/vlr";
import { HomeLive, HomeNews, HomeRankings, UpcomingSnapshot, ResultsSnapshot, SectionLoading } from "@/components/HomeSections";
import { StreamersSection } from "@/components/StreamersSection";
import { PageContainer } from "@/components/PageContainer";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Match center — valstats" };

/** Start loads together, but let each section stream as soon as it is ready.
 * The same upcoming promise serves the snapshot and confirmed-empty fallback. */
export default async function MatchCenter() {
  const live = getLive();
  const upcoming = getUpcoming();
  const results = getResults();
  const news = getNews();
  const rankings = getRankings();

  return (
    <PageContainer width="home" title="Match center">
      <div className="grid min-w-0 grid-cols-1 gap-8 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] lg:gap-10">
        <section className="flex min-w-0 flex-col gap-8" aria-label="Match coverage">
          <Suspense fallback={<SectionLoading label="live matches" />}>
            <HomeLive live={live} upcoming={upcoming} />
          </Suspense>
          <div id="upcoming-snapshot">
            <Suspense fallback={<SectionLoading label="upcoming matches" />}><UpcomingSnapshot data={upcoming} /></Suspense>
          </div>
          <div id="results-snapshot">
            <Suspense fallback={<SectionLoading label="results" />}><ResultsSnapshot data={results} /></Suspense>
          </div>
        </section>
        <aside aria-label="News and rankings" className="flex min-w-0 flex-col gap-8">
          <Suspense fallback={<SectionLoading label="news" />}><HomeNews data={news} /></Suspense>
          <Suspense fallback={<SectionLoading label="rankings" />}><HomeRankings data={rankings} /></Suspense>
          <section aria-labelledby="stats-discovery" className="border-t border-line pt-5">
            <h2 id="stats-discovery" className="font-display text-xl font-semibold text-ink">Explore player stats</h2>
            <p className="mt-2 text-sm text-mut">Compare player ratings and performance on the stats leaderboard.</p>
            <Link href="/stats" className="mt-2 inline-flex min-h-11 items-center rounded text-sm text-accent">View player stats →</Link>
          </section>
        </aside>
      </div>
      <div className="mt-8 sm:mt-10">
        <Suspense fallback={null}><StreamersSection /></Suspense>
      </div>
    </PageContainer>
  );
}
