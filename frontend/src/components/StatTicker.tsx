"use client";

import { useEffect, useState } from "react";
import { TickerTape } from "@/components/TickerTape";
import { buildLiveTicker, pickLiveMatchId, seededOrder } from "@/lib/liveTicker";
import type { ApiResponse, LiveMatch, MatchDetail, TickerItem } from "@/types/vlr";

/** One ticker owner and one serial polling loop. Static context refreshes
 * every five minutes; live context every 30s. Failed reads keep the last tape.
 * Initial empty state preserves SSR/hydration parity. */
const STATIC_REFRESH_MS = 5 * 60_000; // re-pull the curated tape (5 min)
const LIVE_POLL_MS = 30_000; // discover / poll the live match (matches live TTL)

type LiveState = { matchId: string; seed: number; items: TickerItem[] } | null;

/** Fetch the curated static tape. null → transient failure → keep last-good. */
async function fetchStatic(signal: AbortSignal): Promise<TickerItem[] | null> {
  try {
    const r = await fetch("/api/ticker", { cache: "no-store", signal });
    if (!r.ok) return null;
    const res = (await r.json()) as ApiResponse<TickerItem>;
    return !res.error && !res.stale && Array.isArray(res.data) ? res.data : null;
  } catch {
    return null;
  }
}

/** Client mirror of the old server `getLiveTickerSeed`: find the live match,
 *  build its tape, fix the order with a FRESH client seed. Rolled here (in an
 *  effect, never in render) so the randomness can't diverge SSR↔hydrate. Returns
 *  null when nothing's live / no stat is derivable → the static tape shows. */
async function discoverLive(signal: AbortSignal): Promise<LiveState> {
  try {
    const lr = await fetch("/api/matches/live", { cache: "no-store", signal });
    if (!lr.ok) return null;
    const live = (await lr.json()) as ApiResponse<LiveMatch>;
    if (live.stale || live.error || !Array.isArray(live.data)) return null;
    const matchId = pickLiveMatchId(live.data);
    if (!matchId) return null;
    const mr = await fetch(`/api/match/${matchId}`, { cache: "no-store", signal });
    if (!mr.ok) return null;
    const md = (await mr.json()) as ApiResponse<MatchDetail>;
    if (md.stale || md.error) return null;
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
  const [stale, setStale] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let alive = true;
    let current: LiveState = null;
    let lastStatic = -Infinity;
    let timer: ReturnType<typeof setTimeout>;
    let controller: AbortController | undefined;
    let deadline: ReturnType<typeof setTimeout>;
    const tick = async () => {
      const request = new AbortController();
      controller = request;
      deadline = setTimeout(() => { request.abort(); if (alive && current) setStale(true); }, 15_000);
      try {
        if (Date.now() - lastStatic >= STATIC_REFRESH_MS) {
          const items = await fetchStatic(request.signal);
          if (items && alive && !request.signal.aborted) setStaticItems(items);
          lastStatic = Date.now();
        }
        if (!alive || request.signal.aborted) return;
        if (!current) {
          const found = await discoverLive(request.signal);
          if (found && alive && !request.signal.aborted) { current = found; setLive(found); setStale(false); }
        } else {
          const r = await fetch(`/api/match/${current.matchId}`, { cache: "no-store", signal: request.signal });
          if (!r.ok) throw new Error("Ticker update unavailable");
          const md = await r.json() as ApiResponse<MatchDetail>;
          if (!alive || request.signal.aborted) return;
          if (md.error || md.stale || !md.data?.[0]) throw new Error("Ticker update unavailable");
          setStale(false);
          const match = md.data[0];
          if (match?.status === "final") { current = null; setLive(null); }
          else if (match) {
            const items = buildLiveTicker(match);
            if (items.length) { current = { ...current, items: seededOrder(items, current.seed) }; setLive(current); }
          }
        }
      } catch { if (alive && current) setStale(true); }
      finally {
        clearTimeout(deadline);
        if (alive) { setReady(true); timer = setTimeout(tick, LIVE_POLL_MS); }
      }
    };
    void tick();
    return () => { alive = false; clearTimeout(timer); clearTimeout(deadline); controller?.abort(); };
  }, []);

  if (!ready) return null;
  return <TickerTape items={live ? live.items : staticItems} live={Boolean(live)} stale={Boolean(live) && stale} showEmpty />;
}
