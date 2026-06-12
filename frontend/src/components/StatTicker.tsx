import { cn } from "@/lib/cn";
import { Badge } from "@/components/Badge";
import type { TickerItem } from "@/types/vlr";

/**
 * StatTicker — the broadcast lower-third: a single horizontal marquee of curated
 * "notable" stats (top ACS, upsets, leaderboard movers, rating-trend deltas)
 * aggregated in the data layer (`buildTicker`) from endpoints we already serve.
 *
 * Pure server component. The scroll is CSS-only (`vlr-marquee` keyframes in
 * globals.css) — NO Date.now / Math.random in render, so it can't reintroduce a
 * hydration mismatch. Color carries meaning, never decoration: each item's
 * `tone` lights the metric the same way the rest of the dashboard does (green
 * up, red down, orange upset, teal performance).
 *
 * Empty tape → render nothing. A notable-stats ticker with no notable stats is
 * an empty bar; hiding it is the honest neutral state (never an error strip).
 */

/** The metric text is the one lit element; the tone maps to the shared chroma. */
const VALUE_TONE: Record<TickerItem["tone"], string> = {
  up: "text-up",
  down: "text-down",
  warn: "text-warn",
  accent: "text-accent",
  neutral: "text-mut",
};

function TickerEntry({ item }: { item: TickerItem }) {
  return (
    <span className="inline-flex items-center gap-2.5 px-5">
      <Badge tone={item.tone}>{item.label}</Badge>
      <span className="font-display text-[13px] font-semibold uppercase tracking-[0.06em] text-ink">
        {item.primary}
      </span>
      <span
        className={cn(
          "font-mono text-[13px] font-bold tabular-nums",
          VALUE_TONE[item.tone],
        )}
      >
        {item.value}
      </span>
      <span className="font-body text-[12px] text-dim">{item.detail}</span>
      {/* a hairline divider before the next entry */}
      <span className="pl-2.5 text-line" aria-hidden>
        /
      </span>
    </span>
  );
}

export function StatTicker({ items }: { items: TickerItem[] }) {
  if (items.length === 0) return null;

  // One full pass is rendered TWICE in the track; -50% translate (keyframes)
  // lands copy #2 where #1 began for a seamless loop. Duration scales with the
  // tape length so the scroll speed stays roughly constant — a deterministic
  // function of the data (identical on server + client → hydration-safe).
  const durationSeconds = Math.max(24, items.length * 6);

  return (
    <section
      aria-label="Notable stats"
      className="relative overflow-hidden rounded-[10px] border border-line bg-gradient-to-b from-panel to-panel-2"
    >
      {/* label cap — sits above the tape, masks the left edge of the scroll */}
      <span className="absolute left-0 top-0 z-10 flex h-full items-center gap-2 bg-panel-2/95 pl-4 pr-5 font-display text-[11px] font-bold uppercase tracking-broadcast text-mut shadow-[8px_0_12px_-4px_rgba(8,10,14,0.9)]">
        <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden />
        Stat&nbsp;Ticker
      </span>

      {/* the scrolling tape: hover pauses it for readability */}
      <div
        className="vlr-ticker-track flex w-max items-center py-2.5 [animation:vlr-marquee_linear_infinite] hover:[animation-play-state:paused]"
        style={{ animationDuration: `${durationSeconds}s` }}
      >
        {/* copy #1 — the real, screen-reader-visible content */}
        <div className="flex shrink-0 items-center">
          {items.map((item) => (
            <TickerEntry key={item.id} item={item} />
          ))}
        </div>
        {/* copy #2 — purely visual, hidden from assistive tech */}
        <div className="flex shrink-0 items-center" aria-hidden>
          {items.map((item) => (
            <TickerEntry key={`dup:${item.id}`} item={item} />
          ))}
        </div>
      </div>
    </section>
  );
}
