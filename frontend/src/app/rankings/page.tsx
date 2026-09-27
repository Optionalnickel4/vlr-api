import "../ladders.css";
import type { Metadata } from "next";
import { getRankings } from "@/lib/vlr";
import { RankingsBoard, RANKING_REGIONS } from "@/components/RankingsBoard";
import { PageContainer } from "@/components/PageContainer";
export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Rankings — valstats" };
export default async function RankingsPage({ searchParams }: { searchParams?: Promise<{ region?: string }> }) {
  const requested = (await searchParams)?.region ?? "all";
  const region = Object.hasOwn(RANKING_REGIONS, requested) ? requested : "all";
  const rankings = await getRankings(region);
  return <PageContainer width="home"><RankingsBoard rankings={rankings} region={region}/></PageContainer>;
}
