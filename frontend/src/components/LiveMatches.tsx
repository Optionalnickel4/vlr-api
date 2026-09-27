"use client";

import { useEffect, useState, type ReactNode } from "react";
import type { ApiResponse, LiveMatch } from "@/types/vlr";
import { MatchSection } from "@/components/MatchSection";
import { MatchCard } from "@/components/MatchCard";

const POLL_INTERVAL_MS = 30_000;
const POLL_TIMEOUT_MS = 15_000;

function isLiveResponse(value: unknown): value is ApiResponse<LiveMatch> {
  if (!value || typeof value !== "object") return false;
  const res = value as Record<string, unknown>;
  if (res.stale !== false || (res.error !== undefined && res.error !== "")) return false;
  if (!Array.isArray(res.data)) return false;
  return res.data.every((row: unknown) => {
    if (!row || typeof row !== "object") return false;
    const match = row as Record<string, unknown>;
    return ["id", "team1", "team2", "series", "event", "url"].every(
      key => match[key] === null || typeof match[key] === "string",
    ) && ["score1", "score2"].every(
      key => match[key] === null || (typeof match[key] === "number" && Number.isFinite(match[key])),
    );
  });
}

/**
 * LiveMatches — the one polling island on the page. Seeded with server-rendered
 * data, then polls 30s after each completed attempt. Failed/invalid updates keep
 * the last successful scores; only a valid empty response clears them.
 */
export function LiveMatches({ initial, confirmedEmptyFallback }: { initial: ApiResponse<LiveMatch>; confirmedEmptyFallback?: ReactNode }) {
  const [res, setRes] = useState(initial);

  useEffect(() => {
    let alive = true;
    let nextPoll: ReturnType<typeof setTimeout>;
    let deadline: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | undefined;
    const markFailed = () => {
      if (alive) setRes(previous => ({ ...previous, stale: true, error: "Live updates unavailable" }));
    };
    const tick = async () => {
      const request = new AbortController();
      controller = request;
      deadline = setTimeout(() => {
        request.abort();
        markFailed();
      }, POLL_TIMEOUT_MS);
      try {
        const r = await fetch("/api/matches/live", { cache: "no-store", signal: request.signal });
        if (!r.ok) throw new Error("Live update failed");
        const next: unknown = await r.json();
        if (request.signal.aborted || !isLiveResponse(next)) throw new Error("Invalid live update");
        if (alive) setRes(next);
      } catch {
        markFailed();
      } finally {
        clearTimeout(deadline);
        // Schedule only after settlement, including body parsing. Even a
        // transport that ignores abort cannot overlap or publish a late result.
        if (alive) nextPoll = setTimeout(tick, POLL_INTERVAL_MS);
      }
    };
    nextPoll = setTimeout(tick, POLL_INTERVAL_MS);
    return () => {
      alive = false;
      clearTimeout(nextPoll);
      clearTimeout(deadline);
      controller?.abort();
    };
  }, []);

  const matches = res.data;
  // An outage is not confirmation that live coverage has ended. Returning a
  // different view here leaves this component (and its single poller) mounted.
  if (matches.length === 0 && isLiveResponse(res) && confirmedEmptyFallback) {
    return <div className="flex flex-col gap-3">
      <p className="text-sm text-mut">No live matches right now.</p>
      {confirmedEmptyFallback}
    </div>;
  }
  return (
    <MatchSection
      title="Live"
      count={matches.length}
      stale={res.stale || Boolean(res.error)}
      staleLabel={matches.length ? "Live updates unavailable — showing last successful scores. Retrying automatically." : "Live updates unavailable. Retrying automatically."}
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
