"use client";

import { useState } from "react";
import Link from "next/link";
import { cn } from "@/lib/cn";
import { Badge } from "@/components/Badge";
import type { TickerItem } from "@/types/vlr";

/**
 * TickerTape — the presentational broadcast lower-third marquee, driven by the
 * self-fetching StatTicker island in both its static and live modes.
 * It styles by `tone` and prints the strings verbatim (numbers are already
 * coerced + formatted upstream → dash, never NaN). The scroll is CSS-only
 * (`vlr-marquee` keyframes) — NO Date.now / Math.random in render, so it can't
 * reintroduce a hydration mismatch.
 *
 * `live` flips the chroma to LIVE: a pulsing red cap + red top rule (the locked
 * LIVE language — same red/pulse as LiveBadge), so the bar visibly shifts to
 * "now playing" when a match is on, and reverts to the calm accent cap otherwise.
 *
 * The shared shell opts into an honest empty tape; other callers can hide it.
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
      <span className="font-body text-[12px] text-mut">{item.detail}</span>
      {/* a hairline divider before the next entry */}
      <span className="pl-2.5 text-line" aria-hidden>
        /
      </span>
    </span>
  );
}

export function TickerTape({ items, live = false, showEmpty = false }: {
  items: TickerItem[];
  live?: boolean;
  showEmpty?: boolean;
}) {
  const [paused, setPaused] = useState(false);
  if (!items.length && !showEmpty) return null;
  const durationSeconds = Math.max(24, items.length * 6);
  return (
    <section aria-label={live ? "Live match stats" : "Notable stats"} className="vlr-ticker broadcast-ticker">
      <div className="ticker-label"><span className={live ? "ticker-dot is-live" : "ticker-dot"} aria-hidden />{live ? "LIVE WIRE" : "MATCH WIRE"}</div>
      {items.length ? <>
        <div className="ticker-viewport" tabIndex={0} role="region" aria-label="Ticker items, scroll horizontally when paused">
          <div className="vlr-ticker-track" style={{ animationDuration: `${durationSeconds}s`, animationPlayState: paused ? "paused" : undefined, animationName: paused ? "none" : undefined }}>
            <div className="ticker-copy">{items.map(item => <TickerEntry key={item.id} item={item} />)}</div>
            <div className="ticker-copy ticker-duplicate" aria-hidden>{items.map(item => <TickerEntry key={item.id} item={item} />)}</div>
          </div>
        </div>
        <button type="button" className="ticker-pause" aria-pressed={paused} onClick={() => setPaused(value => !value)}>{paused ? "Resume" : "Pause"}<span className="sr-only"> ticker motion</span></button>
      </> : <div className="ticker-empty"><span>No ticker data available.</span><Link href="/results">View results ↗</Link></div>}
    </section>
  );
}
