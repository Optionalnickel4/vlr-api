import "./player.css";
import { PlayerTrendPanel } from "@/components/PlayerTrendPanel";
import type { Metadata } from "next";
import { PageContainer } from "@/components/PageContainer";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import Link from "next/link";
import { getPlayer, getPlayerDimensions, getPlayerTrend } from "@/lib/vlr";
import { Panel } from "@/components/Panel";
import { Badge } from "@/components/Badge";
import { PlayerCard } from "@/components/PlayerCard";
import { PlayerStatsPanel } from "@/components/PlayerStatsPanel";
import { PlayerMatchesPanel } from "@/components/PlayerMatchesPanel";
import { RatingBreakdown } from "@/components/RatingBreakdown";

// Always fresh: the player page reflects vlr-api's current cache on each load.
// Server-side fetch only — the browser never touches vlr-api directly; this
// server component reads the route param and calls the data-layer loaders,
// which already return the { data, stale, error } envelope and never throw.
export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  return { title: `Player ${id} — valstats` };
}

export default async function PlayerPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  // Fetch detail + trend + dimensions in parallel. All loaders catch upstream
  // 404/500 → { data: [], stale: true }. Dimensions are graceful-empty when the
  // player isn't on any regional leaderboard (e.g. a staff member).
  const [player, trend, dims] = await Promise.all([
    getPlayer(id, "page"),
    getPlayerTrend(id),
    getPlayerDimensions(id),
  ]);
  const detail = player.data[0] ?? null;

  // No player detail = the /player/{id} endpoint failed (or genuinely empty). We
  // can't even show a name, so render the page-level graceful error state — same
  // philosophy as the team page (a 500 reads as "couldn't load this player"). NOT
  // a crash, NOT a Next.js error boundary.
  if (!detail) {
    return (
      <PageContainer width="home">
        <Breadcrumbs kind="player" label={`Player ${id}`} />
        <Panel className="flex flex-col items-center gap-3 px-6 py-16 text-center">
          <Badge tone="down">unavailable</Badge>
          <h1 className="font-display text-2xl font-bold uppercase tracking-[0.04em] text-ink">
            Couldn&apos;t load this player
          </h1>
          <p className="max-w-md font-body text-sm text-dim">
            The data source didn&apos;t return a page for player{" "}
            <span className="font-mono text-mut">{id}</span>. It may not exist,
            or vlr-api couldn&apos;t reach it right now.
          </p>
          <Link
            href="/"
            className="mt-2 font-display text-[13px] font-semibold uppercase tracking-[0.12em] text-accent"
          >
            ← back to match center
          </Link>
        </Panel>
      </PageContainer>
    );
  }

  return (
    <PageContainer width="home">
      <Breadcrumbs kind="player" label={detail.alias ?? `Player ${id}`} />
      <div className="player-detail">
        <PlayerCard player={detail} />
        {player.stale && <p className="pd-notice" role="status">Player updates unavailable — showing last available data.</p>}
        <PlayerTrendPanel trend={trend} />

        <RatingBreakdown dims={dims} />

        <PlayerStatsPanel agentStats={detail.agentStats} />

        <PlayerMatchesPanel matches={detail.matches} />
      </div>
    </PageContainer>
  );
}
