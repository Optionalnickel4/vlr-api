import { cn } from "@/lib/cn";
import type { ApiResponse, PlayerDimensions } from "@/types/vlr";
import { Panel } from "@/components/Panel";

/**
 * RatingBreakdown — Phase 13 dimension-split player rating card.
 *
 * Renders a four-axis radar chart (Firepower/Entry/Consistency/Clutch) plus
 * one labeled bar per dimension, shown as cohort percentiles. Supplements R2.0
 * — never replaces it. Hidden when dimensions aren't available (player not on
 * any regional leaderboard). Low-confidence dimensions are faded with an
 * asterisk tooltip "Limited sample — low confidence".
 */

function ordinal(n: number): string {
  const r = Math.round(n);
  const mod100 = r % 100;
  if (mod100 >= 11 && mod100 <= 13) return `${r}th`;
  const mod10 = r % 10;
  if (mod10 === 1) return `${r}st`;
  if (mod10 === 2) return `${r}nd`;
  if (mod10 === 3) return `${r}rd`;
  return `${r}th`;
}

// ---- Radar chart (SVG) -----------------------------------------------------

const CX = 120;
const CY = 120;
const MAX_R = 80;

function axisPoint(score: number, angle: "top" | "right" | "bottom" | "left"): [number, number] {
  const r = MAX_R * (score / 100);
  if (angle === "top") return [CX, CY - r];
  if (angle === "right") return [CX + r, CY];
  if (angle === "bottom") return [CX, CY + r];
  return [CX - r, CY];
}

function gridPoints(pct: number): string {
  const r = MAX_R * (pct / 100);
  return [
    `${CX},${CY - r}`,
    `${CX + r},${CY}`,
    `${CX},${CY + r}`,
    `${CX - r},${CY}`,
  ].join(" ");
}

function RadarChart({
  firepower,
  entry,
  consistency,
  clutch,
  lowConfidence,
}: {
  firepower: number;
  entry: number;
  consistency: number;
  clutch: number;
  lowConfidence: string[];
}) {
  const [fpx, fpy] = axisPoint(firepower, "top");
  const [enx, eny] = axisPoint(entry, "right");
  const [cox, coy] = axisPoint(consistency, "bottom");
  const [clx, cly] = axisPoint(clutch, "left");
  const polygon = `${fpx},${fpy} ${enx},${eny} ${cox},${coy} ${clx},${cly}`;

  return (
    <svg
      viewBox="0 0 240 240"
      width={200}
      height={200}
      aria-hidden="true"
      className="shrink-0"
      overflow="visible"
    >
      {/* axis lines */}
      <line x1={CX} y1={CY} x2={CX} y2={CY - MAX_R} stroke="currentColor" strokeOpacity={0.15} strokeWidth={1} />
      <line x1={CX} y1={CY} x2={CX + MAX_R} y2={CY} stroke="currentColor" strokeOpacity={0.15} strokeWidth={1} />
      <line x1={CX} y1={CY} x2={CX} y2={CY + MAX_R} stroke="currentColor" strokeOpacity={0.15} strokeWidth={1} />
      <line x1={CX} y1={CY} x2={CX - MAX_R} y2={CY} stroke="currentColor" strokeOpacity={0.15} strokeWidth={1} />

      {/* grid diamonds at 25 / 50 / 75 / 100 % */}
      {[25, 50, 75, 100].map((pct) => (
        <polygon
          key={pct}
          points={gridPoints(pct)}
          fill="none"
          stroke="currentColor"
          strokeOpacity={pct === 100 ? 0.2 : 0.1}
          strokeWidth={1}
        />
      ))}

      {/* player score polygon */}
      <polygon
        points={polygon}
        fill="hsl(174 60% 50% / 0.18)"
        stroke="hsl(174 60% 50%)"
        strokeWidth={2}
        strokeLinejoin="round"
      />

      {/* axis labels */}
      <text
        x={CX}
        y={CY - MAX_R - 14}
        textAnchor="middle"
        fontSize={9}
        fontFamily="'Saira Condensed', sans-serif"
        fontWeight={700}
        letterSpacing="0.12em"
        fill="currentColor"
        fillOpacity={lowConfidence.includes("all") ? 0.4 : 0.6}
      >
        FIREPOWER
        {lowConfidence.includes("all") ? " *" : ""}
      </text>
      <text
        x={CX + MAX_R + 14}
        y={CY + 4}
        textAnchor="start"
        fontSize={9}
        fontFamily="'Saira Condensed', sans-serif"
        fontWeight={700}
        letterSpacing="0.12em"
        fill="currentColor"
        fillOpacity={0.6}
      >
        ENTRY
      </text>
      <text
        x={CX}
        y={CY + MAX_R + 18}
        textAnchor="middle"
        fontSize={9}
        fontFamily="'Saira Condensed', sans-serif"
        fontWeight={700}
        letterSpacing="0.12em"
        fill="currentColor"
        fillOpacity={0.6}
      >
        CONSISTENCY
      </text>
      <text
        x={CX - MAX_R - 14}
        y={CY + 4}
        textAnchor="end"
        fontSize={9}
        fontFamily="'Saira Condensed', sans-serif"
        fontWeight={700}
        letterSpacing="0.12em"
        fill="currentColor"
        fillOpacity={lowConfidence.includes("clutch") ? 0.4 : 0.6}
      >
        CLUTCH
        {lowConfidence.includes("clutch") ? " *" : ""}
      </text>
    </svg>
  );
}

// ---- Dimension bar ----------------------------------------------------------

function DimensionBar({
  label,
  score,
  region,
  isLowConfidence,
}: {
  label: string;
  score: number;
  region: string;
  isLowConfidence: boolean;
}) {
  const regionLabel = region.toUpperCase();
  const pctLabel = ordinal(score);

  return (
    <div
      className={cn("flex flex-col gap-1", isLowConfidence && "opacity-50")}
      title={isLowConfidence ? "Limited sample — low confidence" : undefined}
      aria-label={`${label}: ${pctLabel} in ${regionLabel}${isLowConfidence ? " (limited sample)" : ""}`}
    >
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-display text-[10px] font-semibold uppercase tracking-[0.14em] text-dim">
          {label}
          {isLowConfidence && (
            <span
              className="ml-1 text-warn"
              title="Limited sample — low confidence"
              aria-hidden="true"
            >
              *
            </span>
          )}
        </span>
        <span className="font-mono text-[11px] tabular-nums text-mut">
          {pctLabel} in {regionLabel}
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-line/40">
        <div
          className={cn(
            "h-full rounded-full transition-none",
            isLowConfidence ? "bg-mut/50" : "bg-accent",
          )}
          style={{ width: `${Math.max(score, 2)}%` }}
          role="presentation"
        />
      </div>
    </div>
  );
}

// ---- Main component ---------------------------------------------------------

export function RatingBreakdown({
  dims,
}: {
  dims: ApiResponse<PlayerDimensions>;
}) {
  const d = dims.data[0] ?? null;

    // No dimensions row → either the player isn't in the cohort, OR both region
    // lookups failed. Either way, the honest user-facing answer is the same:
    // "rating breakdown unavailable — player isn't on a leaderboard we use".
    // Returning null here would make the card silently vanish, which reads as
    // "the page broke", so always show the explanatory panel.
    if (!d) {
      return (
        <Panel className="p-5 sm:p-6">
          <h2 className="mb-3 font-display text-[11px] font-semibold uppercase tracking-[0.18em] text-dim">
            Rating Breakdown
          </h2>
          <p className="font-body text-sm text-dim">
            Rating breakdown unavailable — this player isn&apos;t in the NA or EU leaderboard.
          </p>
        </Panel>
      );
    }

  const region = d.region ?? "na";
  const lc = d.lowConfidence;

  const fp = d.firepower ?? 0;
  const en = d.entry ?? 0;
  const co = d.consistency ?? 0;
  const cl = d.clutch ?? 0;

  return (
    <Panel className="p-5 sm:p-6">
      <h2 className="mb-5 font-display text-[11px] font-semibold uppercase tracking-[0.18em] text-dim">
        Rating Breakdown
      </h2>

      <div className="flex flex-wrap items-start gap-8">
        {/* radar */}
        <RadarChart
          firepower={fp}
          entry={en}
          consistency={co}
          clutch={cl}
          lowConfidence={lc}
        />

        {/* dimension bars */}
        <div className="flex min-w-[200px] flex-1 flex-col gap-4">
          <DimensionBar
            label="Firepower"
            score={fp}
            region={region}
            isLowConfidence={lc.includes("all")}
          />
          <DimensionBar
            label="Entry"
            score={en}
            region={region}
            isLowConfidence={lc.includes("all")}
          />
          <DimensionBar
            label="Consistency"
            score={co}
            region={region}
            isLowConfidence={lc.includes("all")}
          />
          <DimensionBar
            label="Clutch"
            score={cl}
            region={region}
            isLowConfidence={lc.includes("all") || lc.includes("clutch")}
          />
        </div>
      </div>
    </Panel>
  );
}
