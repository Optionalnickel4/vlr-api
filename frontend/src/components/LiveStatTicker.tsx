"use client";

import { useEffect, useState } from "react";
import { TickerTape } from "@/components/TickerTape";
import { buildLiveTicker, seededOrder } from "@/lib/liveTicker";
import type { ApiResponse, LiveTickerSeed, MatchDetail, TickerItem } from "@/types/vlr";

/**
 * LiveStatTicker — the live-match mode of the lower-third. The ONLY polling part
 * of the ticker (the static tape stays a server component). Mirrors the
 * LiveMatches island:
 *   - SSR-seeded with `initial.items` (no empty flash; the order is computed once
 *     on the server),
 *   - polls /api/match/[id] every 30s WHILE the match is live,
 *   - keeps last-good data on a failed poll (never an error strip),
 *   - reverts to the static curated tape when the match goes final.
 *
 * HYDRATION-CRITICAL: the first client render uses `initial.items` VERBATIM — the
 * seeded order is NOT recomputed on mount; buildLiveTicker/seededOrder run only
 * inside the post-mount effect. So SSR and the first hydrate render are identical
 * (the match-page hydration trap class).
 */
export function LiveStatTicker({
  initial,
  staticItems,
}: {
  initial: LiveTickerSeed;
  staticItems: TickerItem[];
}) {
  const [items, setItems] = useState<TickerItem[]>(initial.items);
  const [ended, setEnded] = useState(false);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const r = await fetch(`/api/match/${initial.matchId}`, {
          cache: "no-store",
        });
        const res = (await r.json()) as ApiResponse<MatchDetail>;
        const match = res.data[0];
        if (!alive || !match) return; // no payload → keep last-good
        if (match.status === "final") {
          setEnded(true); // game over → fall back to the static tape
          return;
        }
        // re-derive with the SAME seed so the tape order never jumps
        const next = seededOrder(buildLiveTicker(match), initial.seed);
        if (next.length) setItems(next); // empty derive → keep last-good
      } catch {
        /* transient poll failure — keep the last good payload */
      }
    };
    const id = setInterval(tick, 30_000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [initial.matchId, initial.seed]);

  // game ended mid-session → revert to the curated all-events tape
  if (ended) return <TickerTape items={staticItems} />;
  return <TickerTape items={items} live />;
}
