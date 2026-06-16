import { getRankings } from "@/lib/vlr";
import { RankingsPanel } from "@/components/RankingsPanel";
import { SiteHeader } from "@/components/SiteHeader";

export const dynamic = "force-dynamic";

export default async function RankingsPage() {
  const rankings = await getRankings();

  return (
    <main className="mx-auto w-full max-w-3xl px-4 py-8 sm:px-6 sm:py-10">
      <SiteHeader label="rankings" active="rankings" />
      <RankingsPanel rankings={rankings} />
    </main>
  );
}
