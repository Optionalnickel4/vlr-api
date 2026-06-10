import { cn } from "@/lib/cn";

/**
 * Sparkline — a minimal inline-SVG rating line for the trend panel. No charting
 * dependency: it's a pure server component that draws a polyline + a faint area
 * fill + a lit endpoint dot.
 *
 * Values arrive ALREADY numeric and ALREADY time-ordered from the data layer
 * (`normalizeTrend` coerces via parseNumeric and sorts on the real timestamp).
 * We only drop nulls and scale to the box — the min/max math runs on numbers,
 * so nothing here string-compares ratings (the Phase-4 trap). `tone` carries the
 * direction's meaning (green up / red down / dim flat); it is NOT decoration.
 */
export function Sparkline({
  values,
  tone = "flat",
  width = 260,
  height = 56,
  className,
}: {
  values: (number | null)[];
  tone?: "up" | "down" | "flat";
  width?: number;
  height?: number;
  className?: string;
}) {
  const pts = values.filter((v): v is number => v !== null);

  // Fewer than two points can't make a line — the caller usually swaps in a
  // "history still young" note, but degrade safely if it doesn't.
  if (pts.length < 2) {
    return (
      <div
        className={cn(
          "flex items-center justify-center font-body text-xs text-dim",
          className,
        )}
        style={{ height }}
      >
        not enough history for a line
      </div>
    );
  }

  const stroke =
    tone === "up"
      ? "var(--color-up)"
      : tone === "down"
        ? "var(--color-down)"
        : "var(--color-mut)";

  const pad = 4;
  const min = Math.min(...pts);
  const max = Math.max(...pts);
  const span = max - min || 1; // flat series → a centered horizontal line
  const stepX = (width - pad * 2) / (pts.length - 1);
  const y = (v: number) =>
    span === 0
      ? height / 2
      : pad + (height - pad * 2) * (1 - (v - min) / span);

  const coords = pts.map((v, i) => [pad + i * stepX, y(v)] as const);
  const line = coords
    .map(([x, yy], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${yy.toFixed(1)}`)
    .join(" ");
  const area = `${line} L${coords[coords.length - 1][0].toFixed(1)},${height} L${coords[0][0].toFixed(1)},${height} Z`;
  const [lastX, lastY] = coords[coords.length - 1];

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      height={height}
      preserveAspectRatio="none"
      role="img"
      aria-label={`Rating trend over ${pts.length} points`}
      className={cn("block", className)}
    >
      <path d={area} fill={stroke} fillOpacity={0.08} stroke="none" />
      <path
        d={line}
        fill="none"
        stroke={stroke}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
      <circle cx={lastX} cy={lastY} r={3} fill={stroke} />
    </svg>
  );
}
