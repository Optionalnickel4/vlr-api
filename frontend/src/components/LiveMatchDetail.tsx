"use client";

import { useEffect, useState } from "react";
import type { ApiResponse, MatchDetail } from "@/types/vlr";
import { MatchHeader } from "@/components/MatchHeader";
import { MapTabs } from "@/components/MapTabs";

const POLL_MS = 30_000; // mirror the live cache TTL / the stat-ticker poll cadence

/**
 * LiveMatchDetail — the match-detail body as a self-updating island. While the
 * match is LIVE it polls /api/match/[id] every 30s and re-renders the scorebug,
 * scoreboard, and round timeline with fresh data; it keeps the last-good payload
 * on a failed poll and STOPS once the match finals (then it's just the static,
 * long-cached render). A match that's already completed never polls.
 *
 * Mirrors the stat-ticker island's discipline. HYDRATION-CRITICAL: state seeds
 * from `initial`, so SSR and the first client render are identical; data only
 * changes inside the post-mount effect — no SSR↔hydrate divergence. The map-tab
 * selection lives in MapTabs' own state, so a poll re-render never resets the tab.
 */
export function LiveMatchDetail({ initial, initialStale = false }: { initial: MatchDetail; initialStale?: boolean }) {
  const [match, setMatch] = useState<MatchDetail>(initial);
  const [stale, setStale] = useState(initialStale);

  useEffect(() => {
    // A completed (or status-less) match is immutable — never poll it.
    if (initial.status !== "live" || !initial.id) return;
    const id = initial.id;
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let active: AbortController | undefined;
    const tick = async () => {
      const controller = new AbortController();
      active = controller;
      const deadline = setTimeout(() => { controller.abort(); if (alive) setStale(true); }, 15_000);
      let finished = false;
      try {
        const r = await fetch(`/api/match/${id}`, { cache: "no-store", signal: controller.signal });
        if (!r.ok) throw new Error("Match refresh failed");
        const res = (await r.json()) as ApiResponse<MatchDetail>;
        const next = res.data?.[0];
        if (res.stale || res.error || !next || next.id !== id || !Array.isArray(next.teams) || !Array.isArray(next.maps)) {
          throw new Error("Match refresh unavailable");
        }
        if (!alive || controller.signal.aborted) return;
        setMatch(next);
        setStale(false);
        finished = next.status === "final";
      } catch {
        if (alive) setStale(true);
      } finally {
        clearTimeout(deadline);
        if (alive && !finished) timer = setTimeout(tick, POLL_MS);
      }
    };

    timer = setTimeout(tick, POLL_MS);
    return () => {
      alive = false;
      clearTimeout(timer);
      active?.abort();
    };
  }, [initial.id, initial.status]);

  return (
    <div className="match-detail">
      {stale && <p role="status" className="stale-note">Updates unavailable. Showing the last available match data; scores may be out of date.</p>}
      <MatchHeader match={match} />
      <MapTabs match={match} />
    </div>
  );
}
