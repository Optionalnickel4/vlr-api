import { getUpcoming } from "@/lib/vlr";
import { MatchCard } from "@/components/MatchCard";
import { MatchSection } from "@/components/MatchSection";
import { SiteHeader } from "@/components/SiteHeader";

// The full upcoming list (the home page shows only a 5-row snapshot). Same data
// layer as the match center — no new API; the endpoint already serves the full
// list. force-dynamic so it reflects vlr-api's current cache on each load.
export const dynamic = "force-dynamic";

/**
 * /schedule — the complete upcoming-matches list, one readable column (same
 * MatchCard styling as the home snapshot). Single column reads cleanly on a
 * phone; centered + width-capped on desktop so rows don't stretch.
 */
export default async function SchedulePage() {
  const upcoming = await getUpcoming();

  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6 sm:py-10">
      <SiteHeader label="schedule" active="schedule" />
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
    </main>
  );
}
