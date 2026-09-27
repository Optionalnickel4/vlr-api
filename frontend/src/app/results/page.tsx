import "../match-listings.css";
import type { Metadata } from "next";
import { getResults } from "@/lib/vlr";
import { ResultsBoard } from "@/components/ResultsBoard";
import { MatchListHeader } from "@/components/MatchListingParts";
import { PageContainer } from "@/components/PageContainer";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Results — valstats" };

export default async function ResultsPage() {
  const results = await getResults();
  const now = new Date();
  return <PageContainer width="home"><div className="match-listings">
    <MatchListHeader kind="results" count={results.data.length} unavailable={results.stale || Boolean(results.error)} now={now} />
    <ResultsBoard response={results} now={now} />
  </div></PageContainer>;
}
