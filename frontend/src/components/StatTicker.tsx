"use client";

import { useEffect, useState } from "react";
import { TickerTape } from "@/components/TickerTape";
import type { ApiResponse, MatchWireItem } from "@/types/vlr";

const REFRESH_MS = 30_000;
const REQUEST_TIMEOUT_MS = 15_000;

/** One serial refresh loop. Failed, stale, malformed, or late responses keep
 * the last valid feed instead of blanking scores already on screen. */
export function StatTicker() {
  const [items, setItems] = useState<MatchWireItem[]>([]);
  const [stale, setStale] = useState(false);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let active: AbortController | undefined;
    let generation = 0;

    const tick = async () => {
      const requestGeneration = ++generation;
      const controller = new AbortController();
      active = controller;
      const deadline = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
      try {
        const response = await fetch("/api/ticker", { cache: "no-store", signal: controller.signal });
        if (!response.ok) throw new Error("Match Wire update unavailable");
        const body = await response.json() as ApiResponse<MatchWireItem>;
        if (!Array.isArray(body.data) || body.stale || body.error) throw new Error("Match Wire update unavailable");
        if (alive && !controller.signal.aborted && requestGeneration === generation) {
          setItems(body.data);
          setStale(false);
        }
      } catch {
        if (alive && requestGeneration === generation) setStale(true);
      } finally {
        clearTimeout(deadline);
        if (alive && requestGeneration === generation) {
          setReady(true);
          timer = setTimeout(tick, REFRESH_MS);
        }
      }
    };

    void tick();
    return () => {
      alive = false;
      generation += 1;
      clearTimeout(timer);
      active?.abort();
    };
  }, []);

  if (!ready) return null;
  return <TickerTape items={items} stale={stale} showEmpty />;
}
