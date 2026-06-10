import type { MatchRound } from "@/types/vlr";
import { cn } from "@/lib/cn";

/**
 * RoundTimeline — the per-map round strip: two rows (one per team) of small
 * squares, green where that team won the round, dim-red where it lost, faint
 * where the round hasn't been played (live/early map). Real round data only
 * (winner/side/outcome from the Phase 7 endpoint) — never faked: if a map has no
 * rounds the caller omits this entirely.
 */
function Square({ won, title }: { won: boolean | null; title: string }) {
  return (
    <span
      title={title}
      className={cn(
        "h-3 w-3 shrink-0 rounded-[2px]",
        won === true && "bg-up",
        won === false && "bg-down/40",
        won === null && "bg-line",
      )}
    />
  );
}

function Row({
  label,
  team,
  rounds,
}: {
  label: string | null;
  team: 1 | 2;
  rounds: MatchRound[];
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-16 shrink-0 truncate font-display text-[11px] font-semibold uppercase tracking-[0.08em] text-mut">
        {label ?? (team === 1 ? "Team 1" : "Team 2")}
      </span>
      <div className="flex flex-wrap gap-1">
        {rounds.map((r, i) => {
          const won = r.winner === null ? null : r.winner === team;
          const meta = [
            r.side ? r.side.toUpperCase() : null,
            r.outcome,
            r.score,
          ]
            .filter(Boolean)
            .join(" · ");
          return (
            <Square
              key={r.round ?? i}
              won={won}
              title={`R${r.round ?? i + 1}${meta ? ` — ${meta}` : ""}`}
            />
          );
        })}
      </div>
    </div>
  );
}

export function RoundTimeline({
  rounds,
  team1,
  team2,
}: {
  rounds: MatchRound[];
  team1: string | null;
  team2: string | null;
}) {
  if (rounds.length === 0) return null; // omit gracefully — never fake it
  return (
    <div className="flex flex-col gap-2 px-4 py-3">
      <Row label={team1} team={1} rounds={rounds} />
      <Row label={team2} team={2} rounds={rounds} />
    </div>
  );
}
