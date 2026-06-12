import {
  getLive,
  getNews,
  getRankings,
  getResults,
  getTicker,
  getUpcoming,
} from "@/lib/vlr";
import { MatchCard } from "@/components/MatchCard";
import { MatchSection } from "@/components/MatchSection";
import { LiveMatches } from "@/components/LiveMatches";
import { RankingsPanel } from "@/components/RankingsPanel";
import { NewsPanel } from "@/components/NewsPanel";
import { StatTicker } from "@/components/StatTicker";

// Always fresh: the match center reflects vlr-api's current cache on each load.
export const dynamic = "force-dynamic";

export default async function MatchCenter() {
  const [results, upcoming, live, rankings, news, ticker] = await Promise.all([
    getResults(),
    getUpcoming(),
    getLive(),
    getRankings(),
    getNews(),
    getTicker(),
  ]);

  return (
    <main className="mx-auto w-full max-w-5xl px-6 py-10">
      <header className="mb-10 flex items-baseline gap-3">
        <span className="font-display text-2xl font-bold uppercase tracking-[0.04em] text-ink">
          valstats<span className="text-accent">.</span>
        </span>
        <span className="font-display text-[13px] font-semibold uppercase tracking-broadcast text-mut">
          match center
        </span>
        <span className="ml-auto font-mono text-xs text-dim">VLR.gg mirror</span>
      </header>

      <div className="flex flex-col gap-10">
        {/* live — the one polling island */}
        <LiveMatches initial={live} />

        {/* upcoming + results */}
        <div className="grid grid-cols-1 gap-10 lg:grid-cols-2">
          <MatchSection
            title="Upcoming"
            count={upcoming.data.length}
            stale={upcoming.stale}
            isEmpty={upcoming.data.length === 0}
            emptyLabel="No upcoming matches scheduled."
          >
            {upcoming.data.map((m, i) => (
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
          >
            {results.data.map((m, i) => (
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

        {/* rankings + news */}
        <div className="grid grid-cols-1 gap-10 lg:grid-cols-2">
          <RankingsPanel rankings={rankings} />
          <NewsPanel news={news} />
        </div>

        {/* broadcast lower-third: the curated notable-stats ticker. Hides itself
            when there's nothing notable to show (empty tape → null). */}
        <StatTicker items={ticker.data} />
      </div>
    </main>
  );
}
