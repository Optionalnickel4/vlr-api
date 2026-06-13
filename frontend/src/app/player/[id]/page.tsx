import Link from "next/link";
import { getPlayer, getPlayerTrend } from "@/lib/vlr";
import { Panel } from "@/components/Panel";
import { Badge } from "@/components/Badge";
import { PlayerStatsPanel } from "@/components/PlayerStatsPanel";
import { PlayerMatchesPanel } from "@/components/PlayerMatchesPanel";
import { PlayerTrendPanel } from "@/components/PlayerTrendPanel";

// Always fresh: the player page reflects vlr-api's current cache on each load.
// Server-side fetch only — the browser never touches vlr-api directly; this
// server component reads the route param and calls the data-layer loaders,
// which already return the { data, stale, error } envelope and never throw.
export const dynamic = "force-dynamic";

function PageFrame({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto w-full max-w-5xl px-6 py-10">
      <header className="mb-8 flex items-baseline gap-3">
        <Link
          href="/"
          className="font-display text-2xl font-bold uppercase tracking-[0.04em] text-ink"
        >
          valstats<span className="text-accent">.</span>
        </Link>
        <span className="font-display text-[13px] font-semibold uppercase tracking-broadcast text-mut">
          player
        </span>
        <Link href="/" className="ml-auto font-mono text-xs text-dim hover:text-mut">
          ← match center
        </Link>
      </header>
      {children}
    </main>
  );
}

export default async function PlayerPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  // Fetch detail (the rich, headline data) + trend (secondary, usually thin) in
  // parallel. Both loaders catch upstream 404/500 → { data: [], stale: true }.
  const [player, trend] = await Promise.all([getPlayer(id), getPlayerTrend(id)]);
  const detail = player.data[0] ?? null;

  // No player detail = the /player/{id} endpoint failed (or genuinely empty). We
  // can't even show a name, so render the page-level graceful error state — same
  // philosophy as the team page (a 500 reads as "couldn't load this player"). NOT
  // a crash, NOT a Next.js error boundary.
  if (!detail) {
    return (
      <PageFrame>
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
      </PageFrame>
    );
  }

  return (
    <PageFrame>
      {/* player identity — accent stripe (same brand-spark as the team page) */}
      <div className="mb-10 flex flex-wrap items-baseline gap-x-4 gap-y-2 border-l-[3px] border-accent pl-4">
        <h1 className="font-display text-4xl font-bold uppercase tracking-[0.03em] text-ink">
          {detail.alias ?? "—"}
        </h1>
        {detail.realName && (
          <span className="font-body text-lg text-mut">{detail.realName}</span>
        )}
        {detail.team &&
          (detail.teamId ? (
            <Link
              href={`/team/${detail.teamId}`}
              className="font-display text-sm font-semibold uppercase tracking-[0.08em] text-accent"
            >
              {detail.team}
            </Link>
          ) : (
            <span className="font-display text-sm font-semibold uppercase tracking-[0.08em] text-mut">
              {detail.team}
            </span>
          ))}
        {detail.country && (
          <Badge tone="neutral" className="self-center uppercase">
            {detail.country}
          </Badge>
        )}
      </div>

      <div className="flex flex-col gap-10">
        {/* LEAD with the rich part: per-agent stats carry the page */}
        <PlayerStatsPanel agentStats={detail.agentStats} />

        {/* recent matches + the secondary rating/ACS trend (usually young) */}
        <div className="grid grid-cols-1 gap-10 lg:grid-cols-2">
          <PlayerMatchesPanel matches={detail.matches} />
          <PlayerTrendPanel trend={trend} />
        </div>
      </div>
    </PageFrame>
  );
}
