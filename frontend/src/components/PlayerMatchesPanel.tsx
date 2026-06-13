import type { PlayerMatch } from "@/types/vlr";
import { MatchSection } from "@/components/MatchSection";
import { Badge } from "@/components/Badge";

/**
 * PlayerMatchesPanel — the player's recent matches, mirroring TeamResultsPanel's
 * idiom: a W/L badge with the broadcast color signal (green win / red loss), the
 * opponent + event, and the score lit per verdict. win/loss arrives resolved from
 * upstream — we don't re-derive a verdict from the raw score. Each row links out
 * to the match on vlr.gg (no internal match detail for these yet). Empty is a
 * valid graceful state, not an error.
 */
function MatchRow({ m, idx }: { m: PlayerMatch; idx: number }) {
  const tone = m.result === "win" ? "up" : m.result === "loss" ? "down" : "neutral";
  const scoreTone =
    m.result === "win" ? "text-up" : m.result === "loss" ? "text-down" : "text-dim";

  const inner = (
    <div className="flex items-center gap-3 px-4 py-3">
      <Badge tone={tone} className="w-12 justify-center">
        {m.result === "win" ? "W" : m.result === "loss" ? "L" : "—"}
      </Badge>
      <div className="min-w-0 flex-1">
        <div className="truncate font-display text-base font-semibold uppercase tracking-[0.03em] text-ink">
          {m.opponent ?? "—"}
        </div>
        {m.event && (
          <div className="truncate font-body text-[12px] text-mut">{m.event}</div>
        )}
      </div>
      <span
        className={`shrink-0 font-display text-xl font-bold tabular-nums ${scoreTone}`}
      >
        {m.score ?? "–"}
      </span>
    </div>
  );

  const shell =
    "block border-b border-line/60 last:border-b-0 transition-colors hover:bg-ink/[0.03]";
  return m.url ? (
    <a
      key={m.id ?? idx}
      href={m.url}
      target="_blank"
      rel="noopener noreferrer"
      className={shell}
    >
      {inner}
    </a>
  ) : (
    <div key={m.id ?? idx} className={shell}>
      {inner}
    </div>
  );
}

export function PlayerMatchesPanel({ matches }: { matches: PlayerMatch[] }) {
  return (
    <MatchSection
      title="Recent Matches"
      count={matches.length}
      isEmpty={matches.length === 0}
      emptyLabel="No recent matches listed."
    >
      {matches.map((m, i) => (
        <MatchRow key={m.id ?? i} m={m} idx={i} />
      ))}
    </MatchSection>
  );
}
