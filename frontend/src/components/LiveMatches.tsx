"use client";

import { useEffect, useState } from "react";
import type { ApiResponse, LiveMatch } from "@/types/vlr";
import { MatchSection } from "@/components/MatchSection";
import { MatchCard } from "@/components/MatchCard";

/**
 * LiveMatches — the one polling island on the page. Seeded with server-rendered
 * data (no empty flash), then refetches /api/matches/live every 30s (matching
 * the upstream live TTL). A failed poll keeps the last good data rather than
 * blanking the section. Out of season this is simply empty — a valid state.
 */
export function LiveMatches({ initial }: { initial: ApiResponse<LiveMatch> }) {
  const [res, setRes] = useState(initial);

  useEffect(() => {
    let alive = true;
    const tick = async () => {
      try {
        const r = await fetch("/api/matches/live", { cache: "no-store" });
        const next = (await r.json()) as ApiResponse<LiveMatch>;
        if (alive) setRes(next);
      } catch {
        /* transient — keep the last good payload */
      }
    };
    const id = setInterval(tick, 30_000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const matches = res.data;
  return (
    <MatchSection
      title="Live"
      count={matches.length}
      stale={res.stale}
      isEmpty={matches.length === 0}
      emptyLabel="No live matches right now."
    >
      {matches.map((m, i) => (
        <MatchCard
          key={m.id ?? `${m.team1}-${m.team2}-${i}`}
          state="live"
          team1={m.team1}
          team2={m.team2}
          score1={m.score1}
          score2={m.score2}
          event={m.event}
          series={m.series}
          id={m.id}
        />
      ))}
    </MatchSection>
  );
}
