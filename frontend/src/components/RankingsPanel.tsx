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
 *
 * The upstream list is REGION-GROUPED: rank resets to 1 at each region boundary
 * (Europe 1-10, Americas 1-10, …). On the landing teaser we show the top N per
 * region so every region is represented; the full /rankings page shows all rows.
 */

// Landing teaser: "regional kings" — the #1 team from every region only.
const RANKINGS_TEASER_PER_REGION = 1;

/**
 * Split a flat rank-ordered list into region groups (rank decreases = new region),
 * then return the first n rows from each group concatenated.
 */
function topPerRegion(rows: RankedTeam[], n: number): RankedTeam[] {
  if (!rows.length) return [];
  const groups: RankedTeam[][] = [];
  let current: RankedTeam[] = [];

  for (const row of rows) {
    const prev = current.at(-1)?.rank ?? null;
    // rank resets (e.g. 10 → 1) mark a region boundary
    if (current.length > 0 && row.rank !== null && prev !== null && row.rank < prev) {
      groups.push(current);
      current = [];
    }
    current.push(row);
  }
  if (current.length) groups.push(current);

  return groups.flatMap((g) => g.slice(0, n));
}

export function RankingsPanel({
  rankings,
  viewAllHref,
  viewAllLabel,
  broadcast = false,
}: {
  rankings: ApiResponse<RankedTeam>;
  viewAllHref?: string;
  viewAllLabel?: string;
  broadcast?: boolean;
}) {
  const allRows = rankings.data;
  // viewAllHref present ↔ landing teaser ("regional kings" — #1 per region only).
  const rows = viewAllHref ? topPerRegion(allRows, RANKINGS_TEASER_PER_REGION) : allRows;

  if (broadcast) return <section className="bc-rankings" aria-labelledby="rankings-heading">
    <div className="bc-section-heading"><div><span className="bc-kicker">The bigger picture</span><h2 id="rankings-heading">REGIONAL LEADERS</h2></div><a href="/rankings" className="bc-section-link">Full rankings ↗</a></div>
    {(rankings.stale || rankings.error) && <p role="status" className="bc-warning">Updates unavailable.</p>}
    {!rows.length && !rankings.stale && !rankings.error && <p className="bc-empty">No rankings available.</p>}
    <div className="bc-leaders">{rows.map((t, i) => <div className="bc-leader" key={t.id ?? i}>
      <span className="bc-rank">{t.rank !== null ? `#${t.rank}` : "—"}</span><div><h3>{t.id ? <a href={`/team/${t.id}`}>{t.team ?? "—"}</a> : t.team ?? "—"}</h3><span className="bc-micro">{t.country ?? "Region unavailable"}</span></div><div className="bc-rating"><strong>{t.rating ?? "—"}</strong><span className="bc-micro">Rating</span></div>
    </div>)}</div>
  </section>;
  return (
    <MatchSection
      title="Rankings"
      count={allRows.length}
      stale={rankings.stale}
      isEmpty={allRows.length === 0}
      emptyLabel="No rankings available."
      viewAllHref={viewAllHref}
      viewAllLabel={viewAllLabel}
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
