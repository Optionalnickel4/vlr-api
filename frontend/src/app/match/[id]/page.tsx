import { getMatch } from "@/lib/vlr";
import { Panel } from "@/components/Panel";
import { Badge } from "@/components/Badge";
import { MatchHeader } from "@/components/MatchHeader";
import { MapTabs } from "@/components/MapTabs";

// Always fresh: reflects vlr-api's current cache on each load. Server-side fetch
// only — this server component reads the route param and calls getMatch, which
// returns the { data, stale, error } envelope and never throws. An upstream 404
// (id with no vlr page) arrives as graceful-empty.
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
          match
        </span>
        <a href="/" className="ml-auto font-mono text-xs text-dim hover:text-mut">
          ← match center
        </a>
      </header>
      {children}
    </main>
  );
}

export default async function MatchPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const res = await getMatch(id);
  const match = res.data[0] ?? null;

  // No match = the endpoint 404'd or errored. Render a page-level graceful state
  // (HTTP 200, not a crash, not a Next error boundary).
  if (!match) {
    return (
      <PageFrame>
        <Panel className="flex flex-col items-center gap-3 px-6 py-16 text-center">
          <Badge tone="down">unavailable</Badge>
          <h1 className="font-display text-2xl font-bold uppercase tracking-[0.04em] text-ink">
            Couldn&apos;t load this match
          </h1>
          <p className="max-w-md font-body text-sm text-dim">
            The data source didn&apos;t return a page for match{" "}
            <span className="font-mono text-mut">{id}</span>. It may not exist, or
            vlr-api couldn&apos;t reach it right now.
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

  return (
    <PageFrame>
      <div className="flex flex-col gap-8">
        <MatchHeader match={match} />
        <MapTabs match={match} />
      </div>
    </PageFrame>
  );
}
