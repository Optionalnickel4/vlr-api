import type { AgentStat } from "@/types/vlr";
import { TableShell } from "@/components/TableShell";

/**
 * PlayerStatsPanel — the detailed per-agent table below the player analysis.
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
    <section aria-labelledby="player-agents">
      <div className="pd-section-heading"><div><p className="pd-kicker">03 / Per-agent detail</p><h2 id="player-agents">Agent Stats</h2></div><p>{agentStats.length} agent rows · all-time source stats</p></div>
      <p className="pd-caption">Exact date boundaries and capture date are not supplied. Source columns and row order are preserved. RND is the round sample for each agent. Scroll horizontally to see all statistics.</p>
      {agentStats.length === 0 ? <p className="pd-empty">No agent stats available.</p> : <div className="pd-table-scroll pd-agent-scroll" tabIndex={0} role="region" aria-label="Agent statistics, scroll horizontally">
        <TableShell className="pd-table pd-agents"
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
      </div>}
    </section>
  );
}
