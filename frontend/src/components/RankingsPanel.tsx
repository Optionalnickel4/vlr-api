import type { ApiResponse, RankedTeam } from "@/types/vlr";
import { MatchSection } from "@/components/MatchSection";
import { TableShell } from "@/components/TableShell";

/**
 * RankingsPanel — the global ranking ladder as a tight broadcast stat table.
 *
 * Renders EXACTLY the four fields vlr-api serves: rank / team / region / rating.
 * No W/L, streak, or win-rate columns — those aren't in the rankings endpoint
 * (W/L is null via upstream selector drift; streak / win-rate% aren't scraped),
 * and the locked spec forbids rendering fields the API doesn't serve. See the
 * deferred API-side gaps logged in PROGRESS.md.
 *
 * rank + rating are already coerced to `number | null` in the data layer
 * (parseNumeric, null-not-NaN) — nothing here sorts on the raw upstream string
 * (the Phase 4 string-sort trap); the list arrives in upstream rank order.
 */
export function RankingsPanel({ rankings }: { rankings: ApiResponse<RankedTeam> }) {
  const rows = rankings.data;

  return (
    <MatchSection
      title="Rankings"
      count={rows.length}
      stale={rankings.stale}
      isEmpty={rows.length === 0}
      emptyLabel="No rankings available."
    >
      <TableShell
        columns={[
          { label: "#", align: "right", className: "w-10" },
          { label: "Team" },
          { label: "Region" },
          { label: "Rating", align: "right" },
        ]}
      >
        {rows.map((t, i) => (
          <tr key={t.id ?? `${t.team}-${i}`}>
            <td className="text-right font-mono text-dim tabular-nums">
              {t.rank ?? "—"}
            </td>
            <td className="font-display text-sm font-semibold uppercase tracking-[0.03em] text-ink">
              {t.id ? (
                // links to the internal team page (rating trend + results join).
                // Some ids 500 upstream — the team page renders that as a
                // graceful "couldn't load this team", so the link is safe.
                <a href={`/team/${t.id}`} className="text-ink hover:text-accent">
                  {t.team ?? "—"}
                </a>
              ) : (
                (t.team ?? "—")
              )}
            </td>
            <td className="font-body text-[13px] text-mut">{t.country ?? "—"}</td>
            <td className="text-right font-mono text-sm text-ink tabular-nums">
              {t.rating ?? "—"}
            </td>
          </tr>
        ))}
      </TableShell>
    </MatchSection>
  );
}
