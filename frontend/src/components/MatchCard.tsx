import { cn } from "@/lib/cn";
import { Badge } from "@/components/Badge";
import { LiveBadge } from "@/components/LiveBadge";
import { ScoreDisplay } from "@/components/ScoreDisplay";

export type MatchState = "result" | "upcoming" | "live";

export interface MatchCardProps {
  state: MatchState;
  team1: string | null;
  team2: string | null;
  score1?: number | null;
  score2?: number | null;
  event?: string | null;
  series?: string | null;
  /** time (result) or eta/timeUntil (upcoming); unused for live. */
  label?: string | null;
  /** vlr.gg match URL — opens the source page (internal match detail is the
   *  Phase 7 stub, slice 6). */
  url?: string | null;
}

const TEAM = "font-display text-base font-semibold uppercase tracking-[0.04em] leading-tight";

function teamClass(
  state: MatchState,
  mine: number | null | undefined,
  other: number | null | undefined,
) {
  // winner lit green only on a decided result; otherwise full-ink, never dimmed
  if (state === "result" && mine != null && other != null) {
    if (mine > other) return cn(TEAM, "text-up");
    if (mine < other) return cn(TEAM, "text-mut");
  }
  return cn(TEAM, "text-ink");
}

/**
 * MatchCard — one broadcast scorebug row: TEAM A · score:score · TEAM B, with
 * the event/series above and a state marker (LIVE / countdown / final time) on
 * the right. The winning side lights green on finals. The whole row links out
 * to the vlr.gg source page.
 */
export function MatchCard({
  state,
  team1,
  team2,
  score1 = null,
  score2 = null,
  event,
  series,
  label,
  url,
}: MatchCardProps) {
  const inner = (
    <div className="flex flex-col gap-2 px-4 py-3">
      {/* meta row */}
      <div className="flex items-center gap-2 text-[11px]">
        <span className="truncate font-display uppercase tracking-[0.1em] text-mut">
          {event ?? "—"}
        </span>
        {series && (
          <span className="truncate font-body text-dim">· {series}</span>
        )}
        <span className="ml-auto shrink-0">
          {state === "live" ? (
            <LiveBadge />
          ) : state === "upcoming" ? (
            <Badge tone="warn">{label ?? "soon"}</Badge>
          ) : (
            <span className="font-mono text-dim">{label ?? "final"}</span>
          )}
        </span>
      </div>

      {/* scorebug row */}
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-3">
        <span className={cn(teamClass(state, score1, score2), "text-right")}>
          {team1 ?? "TBD"}
        </span>
        <ScoreDisplay
          score1={state === "upcoming" ? null : score1}
          score2={state === "upcoming" ? null : score2}
          decided={state === "result"}
          size="md"
        />
        <span className={cn(teamClass(state, score2, score1), "text-left")}>
          {team2 ?? "TBD"}
        </span>
      </div>
    </div>
  );

  const shell =
    "block border-b border-line/60 last:border-b-0 transition-colors hover:bg-ink/[0.03]";

  return url ? (
    <a href={url} target="_blank" rel="noopener noreferrer" className={shell}>
      {inner}
    </a>
  ) : (
    <div className={shell}>{inner}</div>
  );
}
