import type { ApiResponse, PlayerTrend } from "@/types/vlr";
import { PLAYER_FLAT_EPSILON, shouldRenderTrendLine } from "@/lib/vlr";
import { Panel, SectionHeading } from "@/components/Panel";
import { Badge } from "@/components/Badge";
import { Sparkline } from "@/components/Sparkline";

/**
 * PlayerTrendPanel — the SECONDARY panel on the player page. It mirrors
 * TeamTrendPanel (same Sparkline + young/degenerate-flat honest-state handling),
 * but for the player's rounds-weighted rating + ACS over the banked snapshots.
 *
 * IMPORTANT: player snapshots only accumulate when player pages are fetched, so
 * for now MOST players have 1–2 points — the young-history note is the EXPECTED
 * state, not an error. The page deliberately leads with agent stats and treats
 * this as a fill-in-over-time surface; we never draw a fake flat line.
 *
 * Three graceful states (same as the team panel):
 *  - errored (stale + empty): the trend endpoint failed → "trend unavailable".
 *  - thin: <2 real ratings (young) OR ≥2 but spread < PLAYER_FLAT_EPSILON (flat)
 *    → the honest note instead of a meaningless line.
 *  - real series: rating sparkline + rating/ACS change · current · peak.
 *
 * The line-vs-note decision is `shouldRenderTrendLine` (tested), gated on the
 * PLAYER scale epsilon (a player rating moves in hundredths, not hundreds).
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

const fmtRating = (n: number | null) => (n == null ? "—" : n.toFixed(2));
const fmtAcs = (n: number | null) =>
  n == null ? "—" : Number.isInteger(n) ? String(n) : n.toFixed(1);
const signed = (n: number | null, fmt: (x: number | null) => string) =>
  n == null ? "—" : `${n > 0 ? "+" : ""}${fmt(n)}`;
const dir = (n: number | null) =>
  n == null || n === 0 ? "flat" : n > 0 ? "up" : "down";

export function PlayerTrendPanel({ trend }: { trend: ApiResponse<PlayerTrend> }) {
  const t = trend.data[0] ?? null;
  const errored = !t && trend.stale;

  const summary = t?.summary ?? null;
  const points = t?.ratingTrend ?? [];
  const ratingDir = dir(t?.ratingChange ?? null);
  const acsDir = dir(t?.acsChange ?? null);

  // Honest-state decision (tested helper), on the PLAYER flatness scale. The
  // young-vs-flat phrasing only needs to know whether there are ≥2 real points.
  const enoughPoints = points.filter((p) => p.rating !== null).length >= 2;
  const hasLine = shouldRenderTrendLine(points, PLAYER_FLAT_EPSILON);

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
            Trend unavailable — couldn&apos;t load this player&apos;s history.
          </p>
        ) : (
          <>
            {hasLine ? (
              <Sparkline values={points.map((p) => p.rating)} tone={ratingDir} />
            ) : (
              <p className="py-6 text-center font-body text-sm text-dim">
                {enoughPoints
                  ? "Rating held flat across this window — too little movement to chart."
                  : "History is still young — player snapshots accumulate as the page is viewed."}
              </p>
            )}

            <div className="grid grid-cols-3 gap-4 border-t border-line/60 pt-4 sm:grid-cols-6">
              <Stat
                label="Δ Rating"
                value={signed(t?.ratingChange ?? null, fmtRating)}
                tone={ratingDir === "up" ? "up" : ratingDir === "down" ? "down" : "mut"}
              />
              <Stat label="Rating" value={fmtRating(summary?.currentRating ?? null)} />
              <Stat label="Peak" value={fmtRating(summary?.peakRating ?? null)} tone="mut" />
              <Stat
                label="Δ ACS"
                value={signed(t?.acsChange ?? null, fmtAcs)}
                tone={acsDir === "up" ? "up" : acsDir === "down" ? "down" : "mut"}
              />
              <Stat label="ACS" value={fmtAcs(summary?.currentAcs ?? null)} />
              <Stat label="Peak ACS" value={fmtAcs(summary?.peakAcs ?? null)} tone="mut" />
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
