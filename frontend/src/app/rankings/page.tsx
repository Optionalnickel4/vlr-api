import type { Metadata } from "next";
import { getRankings } from "@/lib/vlr";
import { RankingsPanel } from "@/components/RankingsPanel";
import { PageContainer } from "@/components/PageContainer";

// force-dynamic so the ladder reflects vlr-api's current cache on each load.
export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Rankings — valstats" };

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
    <PageContainer width="reading" title="Rankings">
      <RankingsPanel rankings={rankings} />
    </PageContainer>
  );
}
