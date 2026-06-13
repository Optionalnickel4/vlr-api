"use client";

import { useEffect, useRef, useState } from "react";
import { TickerTape } from "@/components/TickerTape";
import { buildLiveTicker, pickLiveMatchId, seededOrder } from "@/lib/liveTicker";
import type { ApiResponse, LiveMatch, MatchDetail, TickerItem } from "@/types/vlr";

/**
 * StatTicker — the persistent broadcast lower-third, now a SELF-FETCHING client
 * island. It lives once in the root layout (so the tape follows every page) but
 * the layout no longer fetches anything for it: the island owns its whole data
 * lifecycle, so every route renders at full speed with zero ticker-fetch
 * overhead on the server.
 *
 * Lifecycle (all client-side, all in effects — never during render):
 *   - static tape: GET /api/ticker on mount, then refresh every STATIC_REFRESH_MS
 *     so the curated tape no longer goes stale across a long session (the old
 *     layout-fetch version only refreshed on a full page reload);
 *   - live mode: on each LIVE_POLL_MS tick, discover a live match (GET
 *     /api/matches/live → pick id → GET /api/match/[id]) and, once live, re-poll
 *     that same match every 30s. Reverts to the static tape when the match goes
 *     final. Keep-last-good on any failed poll (never an error strip).
 *
 * HYDRATION: as a client island the first render uses empty initial state, so
 * SSR and the first client render are BOTH the empty tape (TickerTape → null) —
 * identical, zero hydration mismatch on any route. The order seed is rolled
 * inside the discovery effect (Math.random there, never in render), so it can't
 * reintroduce an SSR↔hydrate divergence. Content simply populates after mount —
 * acceptable for a persistent footer.
 *
 * Empty tape (no notable stats, no live match) → TickerTape renders null, so the
 * `.vlr-ticker` element is absent and `body:has(.vlr-ticker)` reserves no bottom
 * padding (globals.css) — the layout never needs to know the empty state.
 */

const STATIC_REFRESH_MS = 5 * 60_000; // re-pull the curated tape (5 min)
const LIVE_POLL_MS = 30_000; // discover / poll the live match (matches live TTL)

type LiveState = { matchId: string; seed: number; items: TickerItem[] } | null;

/** Fetch the curated static tape. null → transient failure → keep last-good. */
async function fetchStatic(): Promise<TickerItem[] | null> {
  try {
    const r = await fetch("/api/ticker", { cache: "no-store" });
    const res = (await r.json()) as ApiResponse<TickerItem>;
    return res.data;
  } catch {
    return null;
  }
}

/** Client mirror of the old server `getLiveTickerSeed`: find the live match,
 *  build its tape, fix the order with a FRESH client seed. Rolled here (in an
 *  effect, never in render) so the randomness can't diverge SSR↔hydrate. Returns
 *  null when nothing's live / no stat is derivable → the static tape shows. */
async function discoverLive(): Promise<LiveState> {
  try {
    const lr = await fetch("/api/matches/live", { cache: "no-store" });
    const live = (await lr.json()) as ApiResponse<LiveMatch>;
    const matchId = pickLiveMatchId(live.data);
    if (!matchId) return null;
    const mr = await fetch(`/api/match/${matchId}`, { cache: "no-store" });
    const md = (await mr.json()) as ApiResponse<MatchDetail>;
    const match = md.data[0];
    if (!match || match.status === "final") return null;
    const items = buildLiveTicker(match);
    if (!items.length) return null;
    const seed = (Math.random() * 0x100000000) >>> 0;
    return { matchId, seed, items: seededOrder(items, seed) };
  } catch {
    return null;
  }
}

export function StatTicker() {
  const [staticItems, setStaticItems] = useState<TickerItem[]>([]);
  const [live, setLive] = useState<LiveState>(null);

  // Mirror `live` into a ref so the polling tick reads the CURRENT mode without
  // re-subscribing the interval on every mode change.
  const liveRef = useRef<LiveState>(null);
  useEffect(() => {
    liveRef.current = live;
  }, [live]);

  // Static tape: fetch on mount, then refresh on its own slow interval so it
  // never goes stale across a session. Keep-last-good on a failed pull.
  useEffect(() => {
    let alive = true;
    const pull = async () => {
      const items = await fetchStatic();
      if (alive && items) setStaticItems(items);
    };
    pull();
    const id = setInterval(pull, STATIC_REFRESH_MS);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  // Live tape: one 30s tick that either DISCOVERS (when static) or RE-POLLS the
  // current live match (when live, reusing the SAME seed so the order never
  // jumps). Reverts to static when the match finals; keep-last-good otherwise.
  useEffect(() => {
    let alive = true;
    const tick = async () => {
      const cur = liveRef.current;
      if (!cur) {
        const found = await discoverLive();
        if (alive && found) setLive(found);
        return;
      }
      try {
        const mr = await fetch(`/api/match/${cur.matchId}`, {
          cache: "no-store",
        });
        const md = (await mr.json()) as ApiResponse<MatchDetail>;
        const match = md.data[0];
        if (!alive || !match) return; // no payload → keep last-good
        if (match.status === "final") {
          setLive(null); // game over → fall back to the static tape
          return;
        }
        const items = buildLiveTicker(match);
        // re-derive with the SAME seed so the tape order never jumps
        if (items.length) setLive({ ...cur, items: seededOrder(items, cur.seed) });
      } catch {
        /* transient poll failure — keep the last good payload */
      }
    };
    tick();
    const id = setInterval(tick, LIVE_POLL_MS);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  // Live mode wins when present; otherwise the curated static tape. Both hide
  // themselves (TickerTape → null) when empty.
  if (live) return <TickerTape items={live.items} live />;
  return <TickerTape items={staticItems} />;
}
