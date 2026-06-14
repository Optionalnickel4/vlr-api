// @vitest-environment happy-dom
//
// LiveMatchDetail — the match-detail poll island. Asserts the stat-ticker
// discipline applied to the match page: SSR-seeded first render matches the
// client (no hydration error), it polls /api/match/[id] every 30s WHILE live and
// re-renders with fresh data, STOPS polling once the match finals, and never
// polls a completed match.

import { afterEach, describe, expect, it, vi } from "vitest";
import { createElement as h, act } from "react";
import { renderToString } from "react-dom/server";
import { hydrateRoot } from "react-dom/client";

import { LiveMatchDetail } from "@/components/LiveMatchDetail";
import type { ApiResponse, MatchDetail } from "@/types/vlr";

(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT =
  true;

/** Minimal MatchDetail — status, series score, and one map's round score are all
 *  the scorebug/scoreboard read for these assertions. */
function mk(
  status: string | null,
  series: [number, number],
  mapScore: [number, number],
  won: [boolean, boolean] = [false, false],
): MatchDetail {
  return {
    id: "670473",
    event: "Masters",
    series: null,
    status,
    format: "BO3",
    url: null,
    veto: null,
    teams: [
      { name: "LEVIATÁN", id: "2359", score: series[0], won: won[0] },
      { name: "Team Heretics", id: "1001", score: series[1], won: won[1] },
    ],
    maps: [
      {
        gameId: "1",
        name: "Split",
        picked: false,
        decider: false,
        scores: mapScore,
        teams: [
          { name: "LEVIATÁN", score: mapScore[0], players: [] },
          { name: "Team Heretics", score: mapScore[1], players: [] },
        ],
        rounds: [],
      },
    ],
    allMaps: null,
    streams: [],
  };
}

const envelope = (m: MatchDetail): ApiResponse<MatchDetail> => ({
  data: [m],
  stale: false,
});

function jsonResp(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("LiveMatchDetail — poll while live, stop on final, hydration-safe", () => {
  it("SSR == hydrate on a live seed, zero hydration errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResp(envelope(mk("live", [0, 0], [9, 3]))),
    );
    const el = h(LiveMatchDetail, { initial: mk("live", [0, 0], [9, 3]) });
    const container = document.createElement("div");
    container.innerHTML = renderToString(el);

    const seen: string[] = [];
    const spy = vi
      .spyOn(console, "error")
      .mockImplementation((...a) => seen.push(a.map(String).join(" ")));
    const root = hydrateRoot(container, el, {
      onRecoverableError: (e) => seen.push(String(e)),
    });
    await act(async () => {});
    root.unmount();
    spy.mockRestore();

    expect(
      seen.filter((m) => /hydrat|did not match|didn't match|server rendered/i.test(m)),
    ).toEqual([]);
  });

  it("polls every 30s while live and updates the scorebug", async () => {
    vi.useFakeTimers();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResp(envelope(mk("live", [0, 0], [11, 5]))),
    );
    const el = h(LiveMatchDetail, { initial: mk("live", [0, 0], [9, 3]) });
    const container = document.createElement("div");
    container.innerHTML = renderToString(el);
    const root = hydrateRoot(container, el);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(container.innerHTML).toContain('aria-label="Score 9 to 3"'); // SSR seed

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000); // first poll
    });
    expect(container.innerHTML).toContain('aria-label="Score 11 to 5"'); // refreshed
    root.unmount();
  });

  it("stops polling once the match finals, showing the series score", async () => {
    vi.useFakeTimers();
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResp(envelope(mk("final", [2, 0], [13, 5], [true, false]))));
    const el = h(LiveMatchDetail, { initial: mk("live", [0, 0], [9, 3]) });
    const container = document.createElement("div");
    container.innerHTML = renderToString(el);
    const root = hydrateRoot(container, el);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0); // settle mount/hydration
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000); // poll → final
    });
    expect(container.innerHTML).toContain('aria-label="Score 2 to 0"'); // series score
    const callsAtFinal = fetchSpy.mock.calls.length;

    await act(async () => {
      await vi.advanceTimersByTimeAsync(120_000); // lots more time
    });
    expect(fetchSpy.mock.calls.length).toBe(callsAtFinal); // polling stopped
    root.unmount();
  });

  it("never polls a match that's already completed", async () => {
    vi.useFakeTimers();
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResp({}));
    const el = h(LiveMatchDetail, { initial: mk("final", [2, 1], [13, 9], [true, false]) });
    const container = document.createElement("div");
    container.innerHTML = renderToString(el);
    const root = hydrateRoot(container, el);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(120_000);
    });
    expect(fetchSpy).not.toHaveBeenCalled();
    root.unmount();
  });
});
