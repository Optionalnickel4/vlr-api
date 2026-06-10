import { getTeam, getTeamTrend } from "@/lib/vlr";
import { Panel } from "@/components/Panel";
import { Badge } from "@/components/Badge";
import { TeamRosterPanel } from "@/components/TeamRosterPanel";
import { TeamTrendPanel } from "@/components/TeamTrendPanel";
import { TeamResultsPanel } from "@/components/TeamResultsPanel";

// Always fresh: the team page reflects vlr-api's current cache on each load.
// Server-side fetch only — the browser never touches vlr-api directly; this
// server component reads the route param and calls the data-layer loaders,
// which already return the { data, stale, error } envelope and never throw.
export const dynamic = "force-dynamic";

function PageFrame({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto w-full max-w-5xl px-6 py-10">
      <header className="mb-8 flex items-baseline gap-3">
        <a
          href="/"
          className="font-display text-2xl font-bold uppercase tracking-[0.04em] text-ink"
        >
          valstats<span className="text-accent">.</span>
        </a>
        <span className="font-display text-[13px] font-semibold uppercase tracking-broadcast text-mut">
          team
        </span>
        <a href="/" className="ml-auto font-mono text-xs text-dim hover:text-mut">
          ← match center
        </a>
      </header>
      {children}
    </main>
  );
}

export default async function TeamPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  // Both endpoints 500 on certain ids (incl. some rank-1 teams reachable from
  // normal nav). The loaders catch that → { data: [], stale: true, error }.
  const [team, trend] = await Promise.all([getTeam(id), getTeamTrend(id)]);
  const detail = team.data[0] ?? null;

  // No team detail = the /team/{id} endpoint failed (or genuinely empty). We
  // can't even show a name, so render the page-level graceful error state — a
  // 500 reads as "couldn't load this team", same philosophy as graceful-empty
  // everywhere else. NOT a crash, NOT a Next.js error boundary.
  if (!detail) {
    return (
      <PageFrame>
        <Panel className="flex flex-col items-center gap-3 px-6 py-16 text-center">
          <Badge tone="down">unavailable</Badge>
          <h1 className="font-display text-2xl font-bold uppercase tracking-[0.04em] text-ink">
            Couldn&apos;t load this team
          </h1>
          <p className="max-w-md font-body text-sm text-dim">
            The data source didn&apos;t return a page for team{" "}
            <span className="font-mono text-mut">{id}</span>. It may not exist,
            or vlr-api couldn&apos;t reach it right now.
          </p>
          <a
            href="/"
            className="mt-2 font-display text-[13px] font-semibold uppercase tracking-[0.12em] text-accent"
          >
            ← back to match center
          </a>
        </Panel>
      </PageFrame>
    );
  }

  const trendData = trend.data[0] ?? null;

  return (
    <PageFrame>
      {/* team identity */}
      <div className="mb-10 flex flex-wrap items-baseline gap-x-4 gap-y-2">
        <h1 className="font-display text-4xl font-bold uppercase tracking-[0.03em] text-ink">
          {detail.name ?? "—"}
        </h1>
        {detail.tag && (
          <span className="font-mono text-lg text-dim">{detail.tag}</span>
        )}
        {detail.country && (
          <Badge tone="neutral" className="self-center">
            {detail.country}
          </Badge>
        )}
      </div>

      <div className="flex flex-col gap-10">
        {/* the differentiation surface: rating line over the banked history */}
        <TeamTrendPanel trend={trend} />

        {/* roster + the results join (same window as the rating line) */}
        <div className="grid grid-cols-1 gap-10 lg:grid-cols-2">
          <TeamRosterPanel roster={detail.roster} />
          <TeamResultsPanel results={trendData?.resultsInWindow ?? []} />
        </div>
      </div>
    </PageFrame>
  );
}
