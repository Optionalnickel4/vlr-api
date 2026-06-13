import { TickerTape } from "@/components/TickerTape";
import type { TickerItem } from "@/types/vlr";

/**
 * StatTicker — the STATIC curated all-events tape (server component). The default
 * lower-third when no match is live: notable cross-event stats (top ACS, upsets,
 * leaderboard movers, rating-trend deltas) aggregated in the data layer
 * (`buildTicker`). Pure presentation over the shared `TickerTape`; no polling,
 * no client JS. When a match IS live the page swaps this for LiveStatTicker.
 *
 * Empty tape → render nothing (TickerTape returns null) — the honest neutral
 * state, never an error strip.
 */
export function StatTicker({ items }: { items: TickerItem[] }) {
  return <TickerTape items={items} />;
}
