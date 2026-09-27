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
    <PageContainer width="home">
      <div className="home-broadcast">
        <div className="bc-masthead">
          <div><p className="bc-kicker">Valorant / Match coverage</p><h1>MATCH <span>CENTER.</span></h1></div>
          <p className="bc-deck">Every match. Every moment.<br />Live scores, fixtures & the stories that matter.</p>
        </div>
        <section className="bc-lead" aria-label="Featured match">
          <Suspense fallback={<SectionLoading label="live matches" />}><HomeLive live={live} upcoming={upcoming} /></Suspense>
        </section>
        <div className="bc-coverage-grid">
          <div className="bc-match-grid" aria-label="Match coverage">
            <div id="upcoming-snapshot"><Suspense fallback={<SectionLoading label="upcoming matches" />}><UpcomingSnapshot data={upcoming} /></Suspense></div>
            <div id="results-snapshot"><Suspense fallback={<SectionLoading label="results" />}><ResultsSnapshot data={results} /></Suspense></div>
          </div>
          <aside aria-label="Latest news"><Suspense fallback={<SectionLoading label="news" />}><HomeNews data={news} /></Suspense></aside>
        </div>
        <div className="bc-analysis-grid">
          <Suspense fallback={<SectionLoading label="rankings" />}><HomeRankings data={rankings} /></Suspense>
          <section className="bc-stats" aria-labelledby="stats-discovery">
            <span className="bc-kicker">Go beyond the scoreboard</span>
            <h2 id="stats-discovery">KNOW<br />THE NUMBERS.</h2>
            <p>Player ratings. Performance. Perspective.</p>
            <Link href="/stats" className="bc-action">View player stats <span aria-hidden>↗</span></Link>
          </section>
        </div>
        <div className="bc-watch"><Suspense fallback={null}><StreamersSection /></Suspense></div>
        <div className="bc-source"><span>VALSTATS / VALORANT COVERAGE</span><span>Match data & reporting via VLR.gg</span></div>
      </div>
    </PageContainer>
  );
}
