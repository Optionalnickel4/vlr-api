import Link from "next/link";
import type { MatchMapTeam } from "@/types/vlr";
import { TableShell } from "@/components/TableShell";

/**
 * PlayerStatsTable — one team's per-map scoreboard in the broadcast stat-table
 * idiom: PLAYER + the R/ACS/K/D/A/+−/KAST/ADR/HS%/FK/FD columns, mono and
 * right-aligned. Values are already coerced to numbers at the data layer
 * (parseNumeric, null-not-NaN); empty cells (R/ACS/ADR on a live/early map)
 * render as a dash, never NaN, never 0. KAST/HS% carry their % in display.
 */
interface Col {
  label: string;
  key: string; // stat key from the API
  pct?: boolean;
}

// the API stat keys: R, ACS, K, D, A, KD_+/-, KAST, ADR, HS%, FK, FD, FK_+/-
const COLS: Col[] = [
  { label: "R", key: "R" },
  { label: "ACS", key: "ACS" },
  { label: "K", key: "K" },
  { label: "D", key: "D" },
  { label: "A", key: "A" },
  { label: "+/−", key: "KD_+/-" },
  { label: "KAST", key: "KAST", pct: true },
  { label: "ADR", key: "ADR" },
  { label: "HS%", key: "HS%", pct: true },
  { label: "FK", key: "FK" },
  { label: "FD", key: "FD" },
];

function fmt(value: number | null | undefined, pct?: boolean): string {
  if (value === null || value === undefined) return "—"; // never NaN, never 0
  const n = Number.isInteger(value) ? String(value) : value.toFixed(2);
  return pct ? `${n}%` : n;
}

export function PlayerStatsTable({ team }: { team: MatchMapTeam }) {
  return (
    <TableShell
      columns={[
        { label: team.name ?? "—", className: "min-w-[8rem]" },
        ...COLS.map((c) => ({ label: c.label, align: "right" as const })),
      ]}
    >
      {team.players.map((p, i) => (
        <tr key={p.playerId ?? `${p.player}-${i}`}>
          <td>
            <span className="flex items-baseline gap-2">
              {p.playerId ? (
                <Link
                  href={`/player/${p.playerId}`}
                  className="font-display text-sm font-semibold uppercase tracking-[0.03em] text-ink transition-colors hover:text-accent"
                >
                  {p.player ?? "—"}
                </Link>
              ) : (
                <span className="font-display text-sm font-semibold uppercase tracking-[0.03em] text-ink">
                  {p.player ?? "—"}
                </span>
              )}
              {p.agent && (
                <span className="font-body text-[11px] uppercase tracking-wide text-dim">
                  {p.agent}
                </span>
              )}
            </span>
          </td>
          {COLS.map((c) => (
            <td
              key={c.key}
              className="text-right font-mono text-[13px] text-mut tabular-nums"
            >
              {fmt(p.stats[c.key]?.value, c.pct)}
            </td>
          ))}
        </tr>
      ))}
    </TableShell>
  );
}
