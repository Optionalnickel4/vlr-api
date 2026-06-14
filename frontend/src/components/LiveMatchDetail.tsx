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
export function LiveMatchDetail({ initial }: { initial: MatchDetail }) {
  const [match, setMatch] = useState<MatchDetail>(initial);

  useEffect(() => {
    // A completed (or status-less) match is immutable — never poll it.
    if (initial.status !== "live" || !initial.id) return;
    const id = initial.id;
    let alive = true;
    let timer: ReturnType<typeof setInterval> | undefined;

    const tick = async () => {
      try {
        const r = await fetch(`/api/match/${id}`, { cache: "no-store" });
        const res = (await r.json()) as ApiResponse<MatchDetail>;
        const next = res.data[0];
        if (!alive || !next) return; // empty / failed → keep last-good
        setMatch(next);
        if (next.status === "final" && timer) {
          clearInterval(timer); // game over → stop polling; revert to static render
          timer = undefined;
        }
      } catch {
        /* transient network blip — keep the last good payload */
      }
    };

    timer = setInterval(tick, POLL_MS);
    return () => {
      alive = false;
      if (timer) clearInterval(timer);
    };
  }, [initial.id, initial.status]);

  return (
    <div className="flex flex-col gap-8">
      <MatchHeader match={match} />
      <MapTabs match={match} />
    </div>
  );
}
