import type { AgentStat } from "@/types/vlr";
import { MatchSection } from "@/components/MatchSection";
import { TableShell } from "@/components/TableShell";

/**
 * PlayerStatsPanel — the headline of the player page: the per-agent stat table.
 * This is the RICH part (player history is thin; agent stats are not), so it
 * leads the page.
 *
 * The agent_stats keys are upstream's display-cased labels ("Rating", "ACS",
 * "K:D", "KAST", ...). We read them VERBATIM — the column order is taken from the
 * data itself (first row, then any keys later rows add), and each cell is indexed
 * by the exact upstream key. Nothing here renames, lowercases, or reorders a key;
 * a missing value renders as a dash, never blank or NaN. The table scrolls
 * horizontally on narrow screens rather than dropping columns.
 */

/** The ordered union of stat keys across the agent rows, preserving upstream
 *  order (first row wins; later rows only append keys they introduce). */
function statColumns(agentStats: AgentStat[]): string[] {
  const cols: string[] = [];
  const seen = new Set<string>();
  for (const row of agentStats) {
    for (const key of Object.keys(row.stats)) {
      if (!seen.has(key)) {
        seen.add(key);
        cols.push(key);
      }
    }
  }
  return cols;
}

export function PlayerStatsPanel({ agentStats }: { agentStats: AgentStat[] }) {
  const cols = statColumns(agentStats);

  return (
    <MatchSection
      title="Agent Stats"
      count={agentStats.length}
      isEmpty={agentStats.length === 0}
      emptyLabel="No agent stats available."
    >
      {/* wide stat table — scroll horizontally rather than drop columns */}
      <div className="overflow-x-auto">
        <TableShell
          columns={[
            { label: "Agent", className: "min-w-[6.5rem]" },
            ...cols.map((c) => ({ label: c, align: "right" as const })),
          ]}
        >
          {agentStats.map((row, i) => (
            <tr key={row.agent ?? `agent-${i}`}>
              <td>
                <span className="font-display text-sm font-semibold uppercase tracking-[0.03em] text-ink">
                  {row.agent ?? "—"}
                </span>
              </td>
              {cols.map((key) => (
                <td
                  key={key}
                  className="text-right font-mono text-[13px] text-mut tabular-nums"
                >
                  {row.stats[key] ?? "—"}
                </td>
              ))}
            </tr>
          ))}
        </TableShell>
      </div>
    </MatchSection>
  );
}
