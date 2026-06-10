import type { TrendResult } from "@/types/vlr";
import { MatchSection } from "@/components/MatchSection";
import { Badge } from "@/components/Badge";

/**
 * TeamResultsPanel — the "results join" half of the trend view: the team's
 * match results over the SAME window as the rating line, each tagged win/loss
 * with the broadcast color signal (green win / red loss). This is the array the
 * trend endpoint joins out of Phase 4/5; pairing it with the rating line is the
 * combined view vlr.gg structurally can't show.
 *
 * Empty is a valid state (out of season, or the fuzzy name-match resolved
 * nothing) — surfaced as graceful-empty, not an error. The score string ("2:1")
 * is shown verbatim; win/loss already comes resolved from upstream so we don't
 * re-derive a verdict from the raw score here.
 */
function ResultRow({ r, idx }: { r: TrendResult; idx: number }) {
  const tone = r.result === "win" ? "up" : r.result === "loss" ? "down" : "neutral";
  const url = r.vlrId ? `https://www.vlr.gg/${r.vlrId}` : null;

  const inner = (
    <div className="flex items-center gap-3 px-4 py-3">
      <Badge tone={tone} className="w-12 justify-center">
        {r.result === "win" ? "W" : r.result === "loss" ? "L" : "—"}
      </Badge>
      <div className="min-w-0 flex-1">
        <div className="truncate font-display text-base font-semibold uppercase tracking-[0.03em] text-ink">
          {r.opponent ?? "—"}
        </div>
        {r.event && (
          <div className="truncate font-body text-[12px] text-mut">{r.event}</div>
        )}
      </div>
      <span className="shrink-0 font-mono text-lg text-ink tabular-nums">
        {r.score ?? "–"}
      </span>
    </div>
  );

  const shell =
    "block border-b border-line/60 last:border-b-0 transition-colors hover:bg-ink/[0.03]";
  return url ? (
    <a
      key={r.vlrId ?? idx}
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className={shell}
    >
      {inner}
    </a>
  ) : (
    <div key={r.vlrId ?? idx} className={shell}>
      {inner}
    </div>
  );
}

export function TeamResultsPanel({ results }: { results: TrendResult[] }) {
  return (
    <MatchSection
      title="Results in Window"
      count={results.length}
      isEmpty={results.length === 0}
      emptyLabel="No results matched for this window."
    >
      {results.map((r, i) => (
        <ResultRow key={r.vlrId ?? i} r={r} idx={i} />
      ))}
    </MatchSection>
  );
}
