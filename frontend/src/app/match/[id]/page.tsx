import "./match.css";
import type { Metadata } from "next";
import { PageContainer } from "@/components/PageContainer";
import { Breadcrumbs } from "@/components/Breadcrumbs";
import Link from "next/link";
import { getMatch } from "@/lib/vlr";
import { Panel } from "@/components/Panel";
import { Badge } from "@/components/Badge";
import { LiveMatchDetail } from "@/components/LiveMatchDetail";

// Always fresh: reflects vlr-api's current cache on each load. Server-side fetch
// only — this server component reads the route param and calls getMatch, which
// returns the { data, stale, error } envelope and never throws. An upstream 404
// (id with no vlr page) arrives as graceful-empty.
export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }): Promise<Metadata> {
  const { id } = await params;
  return { title: `Match ${id} — valstats` };
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
      <PageContainer width="home">
        <Breadcrumbs kind="match" label={`Match ${id}`} />
        <Panel className="match-unavailable flex flex-col items-center gap-3 px-6 py-16 text-center">
          <Badge tone="down">unavailable</Badge>
          <h1 className="font-display text-2xl font-bold uppercase tracking-[0.04em] text-ink">
            Couldn&apos;t load this match
          </h1>
          <p className="max-w-md font-body text-sm text-dim">
            The data source didn&apos;t return a page for match{" "}
            <span className="font-mono text-mut">{id}</span>. It may not exist, or
            vlr-api couldn&apos;t reach it right now.
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

  // The body is a self-updating island: it SSR-renders from `match` and, while the
  // match is live, polls /api/match/[id] every 30s to refresh the scorebug /
  // scoreboard / round timeline without a reload (stops when the match finals).
  return (
    <PageContainer width="home">
      <Breadcrumbs kind="match" label={`Match ${id}`} />
      <div className="match-masthead"><p>Valorant / Match coverage</p><h1>MATCH <span>REPORT.</span></h1></div>
      <LiveMatchDetail initial={match} initialStale={res.stale || Boolean(res.error)} />
    </PageContainer>
  );
}
