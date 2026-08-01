import { getRankings } from "@/lib/vlr";
import { RankingsPanel } from "@/components/RankingsPanel";
import { SiteHeader } from "@/components/SiteHeader";

// force-dynamic so the ladder reflects vlr-api's current cache on each load.
export const dynamic = "force-dynamic";

/**
 * /rankings — the full team ladder (the home page shows a short panel of it).
 *
 * Deliberately the WORLD view (getRankings() defaults to region "all"): there is
 * no region picker here because the world layout is the only one that ranks every
 * team against each other. Note the trade — vlr's world table carries no W/L
 * record or earnings columns at all, so RankingsPanel renders only rank / team /
 * region / rating. See the RANK_* notes in app/scrapers/selectors.py.
 */
export default async function RankingsPage() {
  const rankings = await getRankings();

  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6 sm:py-10">
      <SiteHeader label="rankings" active="rankings" />
      <RankingsPanel rankings={rankings} />
    </main>
  );
}
