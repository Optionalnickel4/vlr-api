import type { ApiResponse, TeamTrend } from "@/types/vlr";
import { shouldRenderTrendLine } from "@/lib/vlr";
import { Panel, SectionHeading } from "@/components/Panel";
import { Badge } from "@/components/Badge";
import { Sparkline } from "@/components/Sparkline";

/**
 * TeamTrendPanel — the differentiation surface. vlr.gg only ever shows a team's
 * *current* rating; this reads vlr-api's banked ranking_snapshots as a time
 * series (rating line) joined to the same window's W/L summary. The combined
 * view is what the public vlrggapi never served.
 *
 * Three states, all graceful:
 *  - errored (stale + empty): the trend endpoint 500'd → "trend unavailable".
 *  - thin history: either <2 points (cadence working, no line yet) OR enough
 *    points but zero variation across the window (a rank-1 ceiling sits flat at
 *    e.g. 2000 — real data, but a flat line reads like a bug). Both surface the
 *    honest "limited history" note instead of drawing a meaningless flat line.
 *  - real series: sparkline + rating delta + current/peak + W/L record.
 *
 * The line-vs-note decision is `shouldRenderTrendLine` in lib/vlr (tested).
 */
function Stat({
  label,
  value,
  tone = "ink",
}: {
  label: string;
  value: string;
  tone?: "ink" | "up" | "down" | "mut";
}) {
  const color =
    tone === "up"
      ? "text-up"
      : tone === "down"
        ? "text-down"
        : tone === "mut"
          ? "text-mut"
          : "text-ink";
  return (
    <div className="flex flex-col gap-1">
      <span className="font-display text-[10px] font-semibold uppercase tracking-[0.14em] text-dim">
        {label}
      </span>
      <span className={`font-mono text-lg tabular-nums ${color}`}>{value}</span>
    </div>
  );
}

export function TeamTrendPanel({ trend }: { trend: ApiResponse<TeamTrend> }) {
  const t = trend.data[0] ?? null;
  const errored = !t && trend.stale;

  const change = t?.ratingChange ?? null;
  const tone = change == null || change === 0 ? "flat" : change > 0 ? "up" : "down";
  const summary = t?.summary ?? null;
  const points = t?.ratingTrend ?? [];
  // The honest-state decision is a tested data-layer helper: a line needs ≥2
  // real ratings AND real movement (spread ≥ FLAT_EPSILON). `enoughPoints` is
  // kept only to phrase the two thin states (young vs. degenerate-flat).
  const enoughPoints =
    points.filter((p) => p.rating !== null).length >= 2;
  const hasLine = shouldRenderTrendLine(points);

  const fmt = (n: number | null) =>
    n == null ? "—" : Number.isInteger(n) ? String(n) : n.toFixed(1);
  const changeStr =
    change == null ? "—" : `${change > 0 ? "+" : ""}${fmt(change)}`;

  return (
    <section className="flex flex-col gap-3">
      <SectionHeading>
        Rating Trend
        {t?.windowDays != null && (
          <span className="font-mono text-[11px] font-normal tracking-normal text-dim">
            {t.windowDays}d
          </span>
        )}
      </SectionHeading>

      <Panel className="flex flex-col gap-4 border-t-2 border-t-accent/60 p-4">
        {errored ? (
          <p className="py-6 text-center font-body text-sm text-dim">
            Trend unavailable — couldn&apos;t load this team&apos;s history.
          </p>
        ) : (
          <>
            {hasLine ? (
              <Sparkline
                values={points.map((p) => p.rating)}
                tone={tone}
              />
            ) : (
              <p className="py-6 text-center font-body text-sm text-dim">
                {enoughPoints
                  ? "Rating held flat across this window — too little movement to chart."
                  : "History is still young — not enough snapshots for a line yet."}
              </p>
            )}

            <div className="grid grid-cols-2 gap-4 border-t border-line/60 pt-4 sm:grid-cols-4">
              <Stat
                label="Change"
                value={changeStr}
                tone={tone === "up" ? "up" : tone === "down" ? "down" : "mut"}
              />
              <Stat label="Current" value={fmt(summary?.currentRating ?? null)} />
              <Stat
                label="Peak"
                value={fmt(summary?.peakRating ?? null)}
                tone="mut"
              />
              <div className="flex flex-col gap-1">
                <span className="font-display text-[10px] font-semibold uppercase tracking-[0.14em] text-dim">
                  Window W/L
                </span>
                <span className="flex items-center gap-1.5 font-mono text-lg tabular-nums">
                  <span className="text-up">{summary?.wins ?? 0}</span>
                  <span className="text-dim">–</span>
                  <span className="text-down">{summary?.losses ?? 0}</span>
                </span>
              </div>
            </div>

            {t?.note && (
              <p className="font-body text-xs text-dim">
                <Badge tone="warn" className="mr-2">
                  note
                </Badge>
                {t.note}
              </p>
            )}
          </>
        )}
      </Panel>
    </section>
  );
}
