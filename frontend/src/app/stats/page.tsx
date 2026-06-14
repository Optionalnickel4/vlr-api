import { getStats } from "@/lib/vlr";
import { SiteHeader } from "@/components/SiteHeader";
import { StatsLeaderboard } from "@/components/StatsLeaderboard";

// The region-wide player leaderboard (Phase 12). The page server-fetches the
// default NA / all-time leaderboard to SSR-seed the island; the island owns the
// region/timespan toggles + client-side sorting from there. force-dynamic so it
// reflects vlr-api's current cache on each load.
export const dynamic = "force-dynamic";

const DEFAULT_REGION = "na";
const DEFAULT_TIMESPAN = "all";

/**
 * /stats — HLTV-style player rankings led by VLR's own R2.0 rating. The header +
 * single width-capped column read cleanly on a phone; the table scrolls
 * horizontally on narrow screens rather than cramping the stat columns.
 */
export default async function StatsPage() {
  const initial = await getStats(DEFAULT_REGION, DEFAULT_TIMESPAN);

  return (
    <main className="mx-auto w-full max-w-5xl px-4 py-8 sm:px-6 sm:py-10">
      <SiteHeader label="stats" active="stats" />
      <StatsLeaderboard
        initial={initial}
        initialRegion={DEFAULT_REGION}
        initialTimespan={DEFAULT_TIMESPAN}
      />
    </main>
  );
}
