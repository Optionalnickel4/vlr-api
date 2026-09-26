import type { Metadata } from "next";
import { getResults } from "@/lib/vlr";
import { MatchCard } from "@/components/MatchCard";
import { MatchSection } from "@/components/MatchSection";
import { PageContainer } from "@/components/PageContainer";

// The full results list (the home page shows only a 5-row snapshot). Same data
// layer as the match center — no new API; the endpoint already serves the full
// list. force-dynamic so it reflects vlr-api's current cache on each load.
export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Results — valstats" };

/**
 * /results — the complete recent-results list, one readable column (same
 * MatchCard styling as the home snapshot; winner lit green on finals). Single
 * column reads cleanly on a phone; centered + width-capped on desktop.
 */
export default async function ResultsPage() {
  const results = await getResults();

  return (
    <PageContainer width="reading" title="Results">
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
    </PageContainer>
  );
}
