import { cn } from "@/lib/cn";
import { LiveBadge } from "@/components/LiveBadge";
import type { FeaturedStream } from "@/types/vlr";

/**
 * FeaturedStreamers — the top-of-match-center "watch live" band: Twitch channels
 * that are LIVE right now and streaming Valorant (event broadcasts pulled from
 * live matches ∪ the curated TWITCH_FEATURED handles). Server component; the
 * order is shuffled ONCE in the data layer (server-side, request-time), so this
 * renders the props verbatim — no Math.random / Date.now in render, nothing
 * client-only → hydration-safe.
 *
 * LOCKED chroma vocabulary: red is LIVE (same LiveBadge + red viewer count the
 * rest of the dashboard uses), teal accent on hover, dim for context. No new
 * design language.
 *
 * Graceful-empty: nobody live → render nothing (like the ticker). A "watch live"
 * bar with nothing live is just hidden — the honest neutral state.
 */

/** "1234" → "1.2K", "920" → "920", null → "—". Compact viewer count. */
function viewerLabel(n: number | null): string {
  if (n === null) return "—";
  if (n < 1000) return String(Math.round(n));
  const k = n / 1000;
  return `${k.toFixed(k < 10 ? 1 : 0)}K`;
}

function StreamCard({ s }: { s: FeaturedStream }) {
  const name = s.displayName ?? s.login;
  return (
    <a
      href={s.url}
      target="_blank"
      rel="noreferrer noopener"
      title={s.title ?? name}
      className={cn(
        "group flex w-[244px] shrink-0 items-center gap-2.5 rounded-md border border-line bg-panel px-3 py-2",
        "transition-colors hover:border-down/45 hover:bg-panel-2",
      )}
    >
      <LiveBadge className="shrink-0" />
      <span className="flex min-w-0 flex-col leading-tight">
        <span className="flex items-baseline gap-2">
          <span className="truncate font-display text-[13px] font-semibold uppercase tracking-[0.05em] text-ink transition-colors group-hover:text-accent">
            {name}
          </span>
          <span className="shrink-0 font-mono text-[11px] font-bold tabular-nums text-down">
            {viewerLabel(s.viewers)}
          </span>
        </span>
        {s.title && (
          <span className="truncate font-body text-[11px] text-dim">
            {s.title}
          </span>
        )}
      </span>
    </a>
  );
}

export function FeaturedStreamers({ streams }: { streams: FeaturedStream[] }) {
  // Nothing live → hide the band entirely (no empty shell, no error strip).
  if (streams.length === 0) return null;

  return (
    <section
      aria-label="Featured live streams"
      className="flex items-center gap-3 rounded-lg border border-line bg-gradient-to-b from-panel to-panel-2 px-4 py-3"
    >
      {/* label cap — same broadcast vocabulary as the stat-ticker cap */}
      <span className="flex shrink-0 items-center gap-2 font-display text-[11px] font-bold uppercase tracking-broadcast text-mut">
        <span className="h-1.5 w-1.5 rounded-full bg-down [animation:vlr-pulse_2s_infinite]" aria-hidden />
        Watch&nbsp;Live
      </span>

      {/* the channels — a horizontally scrollable row when there are many */}
      <div className="flex min-w-0 flex-1 items-center gap-2 overflow-x-auto pb-0.5">
        {streams.map((s) => (
          <StreamCard key={s.login} s={s} />
        ))}
      </div>
    </section>
  );
}
