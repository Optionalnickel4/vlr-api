// @vitest-environment happy-dom
//
// Behavior + hydration guard for the SELF-FETCHING StatTicker island. The layout
// passes it NO data — it fetches on mount and owns its own static/live lifecycle.
// Because the first render uses empty initial state, SSR and the first client
// render are BOTH the empty tape (identical → zero hydration error on any route);
// content populates after mount. We drive the real island + real derivations
// through a mocked fetch (no network) and assert: SSR↔hydrate parity, fetch-on-
// mount of the static tape, live discovery + mode switch, revert-on-final, and
// static-tape interval refresh. The pure order/derivation logic is covered by
// liveTicker.test.ts; here we only test where it's invoked.

import { afterEach, describe, expect, it, vi } from "vitest";
import { createElement as h, act } from "react";
import { renderToString } from "react-dom/server";
import { hydrateRoot } from "react-dom/client";

import { StatTicker } from "@/components/StatTicker";
import { normalizeMatch } from "@/lib/vlr";
import { buildLiveTicker } from "@/lib/liveTicker";
import type { ApiResponse, MatchDetail, TickerItem } from "@/types/vlr";

import filledFixture from "@/lib/__fixtures__/match_live_filled.json";

// React needs this flag to run act() cleanly outside React Testing Library.
(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT =
  true;

// A normalized, in-progress match detail (status forced non-final so discovery
// keeps it) — the same fixture the derivations are proven against.
const liveMatch: MatchDetail = { ...normalizeMatch(filledFixture)[0], status: "live" };
// At least one live-derived stat must exist or discovery yields null.
const LIVE_STAT = buildLiveTicker(liveMatch)[0]?.primary ?? "";

const STATIC: TickerItem[] = [
  { id: "s1", kind: "acs", label: "TOP ACS", tone: "accent", primary: "Demon1", value: "301", detail: "G2 · all-events" },
];

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

/** Route the island's fetches. `live` toggles whether a match is on; `status`
 *  drives the match-detail payload (so a test can flip a live match to final). */
function mockFetch(opts: {
  ticker?: TickerItem[];
  live?: boolean;
  status?: () => string;
}) {
  const ticker = opts.ticker ?? [];
  return vi.spyOn(globalThis, "fetch").mockImplementation((async (
    input: string | URL | Request,
  ) => {
    const url = String(input);
    if (url.includes("/api/ticker")) {
      return json({ data: ticker, stale: false } satisfies ApiResponse<TickerItem>);
    }
    if (url.includes("/api/matches/live")) {
      return json({ data: opts.live ? [{ id: "684619" }] : [], stale: false });
    }
    if (url.includes("/api/match/")) {
      const status = opts.status?.() ?? "live";
      return json({ data: [{ ...liveMatch, status }], stale: false });
    }
    return json({ data: [], stale: false });
  }) as typeof fetch);
}

/** Render to string, hydrate, and run mount effects. Returns the live container
 *  + a root handle + any hydration-related console errors seen during hydrate. */
async function mountIsland() {
  const element = h(StatTicker);
  const ssrHtml = renderToString(element); // empty initial state → ""
  const container = document.createElement("div");
  container.innerHTML = ssrHtml;

  const seen: string[] = [];
  const spy = vi.spyOn(console, "error").mockImplementation((...args) => {
    seen.push(args.map(String).join(" "));
  });
  const root = hydrateRoot(container, element, {
    onRecoverableError: (e) => seen.push(String(e)),
  });
  // flush mount effects: discovery chains two fetches (live → match), so drain
  // the microtask queue across a couple of macrotask ticks (real timers here).
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0));
  });
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0));
  });
  spy.mockRestore();

  const hydrationErrors = seen.filter((m) =>
    /hydrat|did not match|didn't match|server rendered|server-rendered|attributes/i.test(m),
  );
  return { container, root, ssrHtml, hydrationErrors };
}

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("StatTicker island — SSR ↔ hydrate parity", () => {
  it("renders nothing on the server and hydrates with zero hydration errors", async () => {
    mockFetch({ ticker: [], live: false });
    const { ssrHtml, hydrationErrors, root } = await mountIsland();
    // empty initial state → no tape on the server (SSR-identical to first client
    // render), so there is nothing to mismatch on any route
    expect(ssrHtml).toBe("");
    expect(hydrationErrors).toEqual([]);
    root.unmount();
  });
});

describe("StatTicker island — static mode (fetch on mount)", () => {
  it("fetches /api/ticker on mount and renders the curated tape", async () => {
    mockFetch({ ticker: STATIC, live: false });
    const { container, root } = await mountIsland();
    expect(container.innerHTML).toContain("Notable stats"); // static aria-label
    expect(container.innerHTML).toContain("Demon1");
    expect(container.innerHTML).not.toContain("Live match stats");
    root.unmount();
  });

  it("refreshes the static tape on its interval (no full reload needed)", async () => {
    vi.useFakeTimers();
    let ticker: TickerItem[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((async (
      input: string | URL | Request,
    ) => {
      const url = String(input);
      if (url.includes("/api/ticker")) return json({ data: ticker, stale: false });
      if (url.includes("/api/matches/live")) return json({ data: [], stale: false });
      return json({ data: [], stale: false });
    }) as typeof fetch);

    const element = h(StatTicker);
    const container = document.createElement("div");
    container.innerHTML = renderToString(element);
    const root = hydrateRoot(container, element);
    await act(async () => {}); // mount: tape still empty upstream
    expect(container.innerHTML).not.toContain("Demon1");

    // upstream gains a stat; the next refresh tick pulls it in (no reload)
    ticker = STATIC;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(5 * 60_000);
    });
    expect(container.innerHTML).toContain("Demon1");
    root.unmount();
  });
});

describe("StatTicker island — live mode discovery + switch", () => {
  it("discovers a live match on mount and renders the LIVE tape", async () => {
    expect(LIVE_STAT).not.toBe(""); // fixture sanity: derivations produce a stat
    mockFetch({ ticker: STATIC, live: true });
    const { container, root } = await mountIsland();
    expect(container.innerHTML).toContain("Live match stats"); // live aria-label
    expect(container.innerHTML).toContain(LIVE_STAT);
    expect(container.innerHTML).not.toContain("Notable stats");
    root.unmount();
  });

  it("reverts to the static tape when a poll reports the match FINAL", async () => {
    vi.useFakeTimers();
    let status = "live";
    mockFetch({ ticker: STATIC, live: true, status: () => status });

    const element = h(StatTicker);
    const container = document.createElement("div");
    container.innerHTML = renderToString(element);
    const root = hydrateRoot(container, element);
    // mount discovery (live → match fetch chain) → live; drain microtasks
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(container.innerHTML).toContain("Live match stats");

    // the match finals; the next 30s poll reverts to the curated static tape
    status = "final";
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(container.innerHTML).toContain("Notable stats");
    expect(container.innerHTML).toContain("Demon1");
    expect(container.innerHTML).not.toContain("Live match stats");
    root.unmount();
  });
});
