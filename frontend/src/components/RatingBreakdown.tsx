import type { ApiResponse, PlayerDimensions } from "@/types/vlr";

/** Source cohort percentiles with visible sample limitations. Partial data
 * keeps individual bars but suppresses the radar rather than inventing zeroes. */
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
      viewBox="-40 -10 320 260"
      width={300}
      height={244}
      aria-hidden="true"
      className="pd-radar"
      overflow="hidden"
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
        fontSize={11}
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
        fontSize={11}
        fontFamily="'Saira Condensed', sans-serif"
        fontWeight={700}
        letterSpacing="0.12em"
        fill="currentColor"
        fillOpacity={0.9}
      >
        ENTRY
      </text>
      <text
        x={CX}
        y={CY + MAX_R + 18}
        textAnchor="middle"
        fontSize={11}
        fontFamily="'Saira Condensed', sans-serif"
        fontWeight={700}
        letterSpacing="0.12em"
        fill="currentColor"
        fillOpacity={0.9}
      >
        CONSISTENCY
      </text>
      <text
        x={CX - MAX_R - 14}
        y={CY + 4}
        textAnchor="end"
        fontSize={11}
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

// Percentiles remain source values; absent dimensions never become zero.
export function RatingBreakdown({ dims }: { dims: ApiResponse<PlayerDimensions> }) {
  const d = dims.data[0];
  const region = d?.region?.toUpperCase() ?? "region unavailable";
  const labels = ["Firepower", "Entry", "Consistency", "Clutch"] as const;
  const scores = d ? [d.firepower, d.entry, d.consistency, d.clutch] : [];
  const period = d?.timespan === "all" ? "All-time leaderboard" : d?.timespan ? `${d.timespan}-day leaderboard` : "Period unavailable";
  return <section aria-labelledby="player-dimensions">
    <div className="pd-section-heading"><div><p className="pd-kicker">02 / Cohort percentiles</p><h2 id="player-dimensions">Rating Breakdown</h2></div><p>{d ? `${region} · ${period}` : "Cohort unavailable"}</p></div>
    <div className="pd-dimensions">
      {!d ? <p className="pd-empty">{dims.stale ? "Rating breakdown unavailable — the leaderboard lookup failed." : "Rating breakdown unavailable — this player isn't in the NA or EU leaderboard."}</p> : <>
        {dims.stale && <p className="pd-notice" role="status">Dimension updates unavailable — showing last available data.</p>}
        <p className="pd-caption">Percentile within the source cohort, not a match rating. Cohort size and player round sample are not supplied for these dimensions.</p>
        <div className="pd-dimension-grid">
          {scores.every(score => score !== null) && <RadarChart firepower={d.firepower!} entry={d.entry!} consistency={d.consistency!} clutch={d.clutch!} lowConfidence={d.lowConfidence} />}
          <div className="pd-bars">{labels.map((label,i) => {
            const score = scores[i];
            const limited = d.lowConfidence.includes("all") || d.lowConfidence.includes(label.toLowerCase());
            return <div className="pd-dimension" key={label} aria-label={`${label}: ${score == null ? "unavailable" : `${ordinal(score)} in ${region}`}${limited ? " (limited sample)" : ""}`}>
              <div><span>{label}{limited ? " *" : ""}</span><strong>{score == null ? "Unavailable" : `${ordinal(score)} in ${region}`}</strong></div>
              {score !== null && <div className="pd-bar" aria-hidden><span style={{width:`${Math.max(0,Math.min(100,score))}%`}} /></div>}
              {limited && <p className="pd-caption">Limited sample — low confidence</p>}
            </div>;
          })}</div>
        </div>
      </>}
    </div>
  </section>;
}
