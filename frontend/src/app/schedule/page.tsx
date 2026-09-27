import "../match-listings.css";
import type { Metadata } from "next";
import { getUpcoming } from "@/lib/vlr";
import { ScheduleBoard } from "@/components/ScheduleBoard";
import { MatchListHeader } from "@/components/MatchListingParts";
import { PageContainer } from "@/components/PageContainer";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Schedule — valstats" };

export default async function SchedulePage() {
  const upcoming = await getUpcoming();
  const now = new Date();
  return <PageContainer width="home"><div className="match-listings">
    <MatchListHeader kind="schedule" count={upcoming.data.length} unavailable={upcoming.stale || Boolean(upcoming.error)} now={now} />
    <ScheduleBoard response={upcoming} now={now} />
  </div></PageContainer>;
}
