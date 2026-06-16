import {
  getLive,
  getNews,
  getRankings,
  getResults,
  getUpcoming,
  HOME_SNAPSHOT_LIMIT,
} from "@/lib/vlr";
import { MatchCard } from "@/components/MatchCard";
import { MatchSection } from "@/components/MatchSection";
import { LiveMatches } from "@/components/LiveMatches";
import { RankingsPanel } from "@/components/RankingsPanel";
import { NewsPanel } from "@/components/NewsPanel";
import { FeaturedStreamers } from "@/components/FeaturedStreamers";
import { SiteHeader } from "@/components/SiteHeader";
import { getFeaturedStreamers } from "@/lib/twitch";

// Always fresh: the match center reflects vlr-api's current cache on each load.
export const dynamic = "force-dynamic";

/**
 * Home (match center) — a compact, curated SNAPSHOT, not an endless dual-column
 * list. Order is preserved: streamers → live → Upcoming (next 5) → Results
 * (latest 5) → ticker. Each capped section links out to its dedicated full-list
 * page (/schedule, /results). Built to read top-to-bottom on a phone in ~1–2
 * scrolls; on desktop the two snapshots sit side by side.
 */
export default async function MatchCenter() {
  const [results, upcoming, live, rankings, news, streamers] =
    await Promise.all([
      getResults(),
      getUpcoming(),
      getLive(),
      getRankings(),
      getNews(),
      getFeaturedStreamers(),
    ]);

  // Snapshot: the next-5 upcoming + most-recent-5 results (the lists arrive
  // already ordered upstream). The full lists live on /schedule and /results.
  const upcomingSnapshot = upcoming.data.slice(0, HOME_SNAPSHOT_LIMIT);
  const resultsSnapshot = results.data.slice(0, HOME_SNAPSHOT_LIMIT);

  return (
    <main className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6 sm:py-10">
      <SiteHeader label="match center" />

      <div className="flex flex-col gap-8 sm:gap-10">
        {/* watch-live band: Twitch channels live now (event broadcasts ∪ featured
            handles), Valorant-only, server-shuffled once. Hides when none live. */}
        <FeaturedStreamers streams={streamers.data} />

        {/* live — the one polling island */}
        <LiveMatches initial={live} />

        {/* upcoming + results SNAPSHOTS — capped, each links to its full page.
            Two columns on desktop; stacks top-to-bottom on phone. */}
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-2 lg:gap-10">
          <MatchSection
            title="Upcoming"
            count={upcoming.data.length}
            stale={upcoming.stale}
            isEmpty={upcoming.data.length === 0}
            emptyLabel="No upcoming matches scheduled."
            viewAllHref="/schedule"
            viewAllLabel="Full schedule"
          >
            {upcomingSnapshot.map((m, i) => (
              <MatchCard
                key={m.id ?? `${m.team1}-${m.team2}-${i}`}
                state="upcoming"
                team1={m.team1}
                team2={m.team2}
                event={m.event}
                series={m.series}
                label={m.timeUntil}
                id={m.id}
              />
            ))}
          </MatchSection>

          <MatchSection
            title="Results"
            count={results.data.length}
            stale={results.stale}
            isEmpty={results.data.length === 0}
            emptyLabel="No recent results."
            viewAllHref="/results"
            viewAllLabel="All results"
          >
            {resultsSnapshot.map((m, i) => (
              <MatchCard
                key={m.id ?? `${m.team1}-${m.team2}-${i}`}
                state="result"
                team1={m.team1}
                team2={m.team2}
                score1={m.score1}
                score2={m.score2}
                event={m.event}
                series={m.series}
                label={m.time}
                id={m.id}
              />
            ))}
          </MatchSection>
        </div>

        {/* rankings + news — snapshotted panels link out to their full pages */}
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-2 lg:gap-10">
          <RankingsPanel rankings={rankings} viewAllHref="/rankings" viewAllLabel="Full rankings" />
          <NewsPanel news={news} viewAllHref="/news" viewAllLabel="All news" />
        </div>
      </div>
    </main>
  );
}
