import { getUpcoming } from "@/lib/vlr";
import { buildSchedule } from "@/lib/schedule";
import { ScheduleBoard } from "@/components/ScheduleBoard";
import { SiteHeader } from "@/components/SiteHeader";
import { SectionHeading } from "@/components/Panel";

// Same data layer as the match center — no new API; the endpoint already serves
// the full upcoming list. force-dynamic so it reflects vlr-api's current cache
// on each load AND so the DERIVED match day (eta + now, see lib/schedule) is
// computed against a fresh "now" every request.
export const dynamic = "force-dynamic";

/**
 * /schedule — a broadcast-styled schedule: a "NEXT UP" hero for the soonest
 * match, then day sections (TODAY / TOMORROW / weekday) with matches sub-grouped
 * under a single event label each. Typographic crests stand in for logos (vlr's
 * match-list payload has no logo URLs). Width-capped + centered so rows don't
 * stretch on desktop; degrades to a single readable column on a phone.
 */
export default async function SchedulePage() {
  const upcoming = await getUpcoming();
  const board = buildSchedule(upcoming.data, new Date());

  return (
    <main className="mx-auto w-full max-w-4xl px-4 py-8 sm:px-6 sm:py-10">
      <SiteHeader label="schedule" active="schedule" />

      <SectionHeading className="mb-5">
        Schedule
        <span className="font-mono text-[11px] font-normal tracking-normal text-dim">
          {upcoming.data.length}
        </span>
        {upcoming.stale && (
          <span className="font-mono text-[10px] tracking-normal text-warn">
            stale
          </span>
        )}
      </SectionHeading>

      <ScheduleBoard
        board={board}
        count={upcoming.data.length}
        stale={upcoming.stale}
      />
    </main>
  );
}
