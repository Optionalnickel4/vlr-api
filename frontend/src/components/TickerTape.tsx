import { cn } from "@/lib/cn";
import { Badge } from "@/components/Badge";
import type { TickerItem } from "@/types/vlr";

/**
 * TickerTape — the presentational broadcast lower-third marquee, shared by the
 * static curated tape (StatTicker) and the live in-game tape (LiveStatTicker).
 * Pure: it styles by `tone` and prints the strings verbatim (numbers are already
 * coerced + formatted upstream → dash, never NaN). The scroll is CSS-only
 * (`vlr-marquee` keyframes) — NO Date.now / Math.random in render, so it can't
 * reintroduce a hydration mismatch.
 *
 * `live` flips the chroma to LIVE: a pulsing red cap + red top rule (the locked
 * LIVE language — same red/pulse as LiveBadge), so the bar visibly shifts to
 * "now playing" when a match is on, and reverts to the calm accent cap otherwise.
 *
 * Empty tape → render nothing (the honest neutral state, never an error strip).
 */
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
      {item.value && (
        <span
          className={cn(
            "font-mono text-[13px] font-bold tabular-nums",
            VALUE_TONE[item.tone],
          )}
        >
          {item.value}
        </span>
      )}
      <span className="font-body text-[12px] text-dim">{item.detail}</span>
      {/* a hairline divider before the next entry */}
      <span className="pl-2.5 text-line" aria-hidden>
        /
      </span>
    </span>
  );
}

export function TickerTape({
  items,
  live = false,
}: {
  items: TickerItem[];
  live?: boolean;
}) {
  if (items.length === 0) return null;

  // One full pass is rendered TWICE in the track; -50% translate (keyframes)
  // lands copy #2 where #1 began for a seamless loop. Duration scales with the
  // tape length so the scroll speed stays roughly constant — a deterministic
  // function of the data (identical on server + client → hydration-safe).
  const durationSeconds = Math.max(24, items.length * 6);

  return (
    // Broadcast lower-third: pinned to the bottom of the viewport, full width,
    // always visible. Live mode swaps the top rule to LIVE red.
    <section
      aria-label={live ? "Live match stats" : "Notable stats"}
      className={cn(
        "vlr-ticker fixed inset-x-0 bottom-0 z-40 h-[var(--ticker-h)] overflow-hidden border-t bg-gradient-to-b from-panel to-panel-2",
        live ? "border-down/60" : "border-line",
      )}
    >
      {/* label cap — sits above the tape, masks the left edge of the scroll */}
      <span
        className={cn(
          "absolute left-0 top-0 z-10 flex h-full items-center gap-2 bg-panel-2/95 pl-4 pr-5 font-display text-[11px] font-bold uppercase tracking-broadcast shadow-[8px_0_12px_-4px_rgba(8,10,14,0.9)]",
          live ? "text-down" : "text-mut",
        )}
      >
        {live ? (
          <>
            <span
              className="h-1.5 w-1.5 rounded-full bg-down [animation:vlr-pulse_2s_infinite]"
              aria-hidden
            />
            Live&nbsp;·&nbsp;Now&nbsp;Playing
          </>
        ) : (
          <>
            <span className="h-1.5 w-1.5 rounded-full bg-accent" aria-hidden />
            Stat&nbsp;Ticker
          </>
        )}
      </span>

      {/* the scrolling tape: hover pauses it for readability */}
      <div
        className="vlr-ticker-track flex h-full w-max items-center [animation:vlr-marquee_linear_infinite] hover:[animation-play-state:paused]"
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
