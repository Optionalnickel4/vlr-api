// @vitest-environment happy-dom
//
// Hydration + mode-switch guard for the live ticker. The order is computed once
// on the server (seededOrder) and must carry into the FIRST client render
// unchanged — the island seeds useState with the server `items` and only
// re-derives inside the post-mount effect. If the order were rolled in render,
// SSR and hydrate would diverge and React would warn here (the match-page trap
// class). We also assert the live↔static visual switch.

import { afterEach, describe, expect, it, vi } from "vitest";
import { createElement as h, act } from "react";
import { renderToString } from "react-dom/server";
import { hydrateRoot } from "react-dom/client";

import { LiveStatTicker } from "@/components/LiveStatTicker";
import { StatTicker } from "@/components/StatTicker";
import { normalizeMatch } from "@/lib/vlr";
import { buildLiveTicker, seededOrder } from "@/lib/liveTicker";
import type { LiveTickerSeed, TickerItem } from "@/types/vlr";

import filledFixture from "@/lib/__fixtures__/match_live_filled.json";

// React needs this flag to run act() cleanly outside React Testing Library.
(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT =
  true;

const filled = normalizeMatch(filledFixture)[0];
const SEED = 12345;
const seededItems = seededOrder(buildLiveTicker(filled), SEED);
const initial: LiveTickerSeed = { matchId: "684619", seed: SEED, items: seededItems };

const STATIC: TickerItem[] = [
  { id: "s1", kind: "acs", label: "TOP ACS", tone: "accent", primary: "Demon1", value: "301", detail: "G2 · all-events" },
];

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

async function hydrationErrors(element: ReturnType<typeof h>): Promise<string[]> {
  const html = renderToString(element);
  const container = document.createElement("div");
  container.innerHTML = html;

  const seen: string[] = [];
  const spy = vi.spyOn(console, "error").mockImplementation((...args) => {
    seen.push(args.map(String).join(" "));
  });
  const root = hydrateRoot(container, element, {
    onRecoverableError: (e) => seen.push(String(e)),
  });
  await act(async () => {});
  root.unmount();
  spy.mockRestore();

  return seen.filter((mm) =>
    /hydrat|did not match|didn't match|server rendered|server-rendered|attributes/i.test(mm),
  );
}

describe("live ticker hydration (seeded order carries SSR → first client render)", () => {
  it("SSR == hydrate, zero hydration errors (no render-time reshuffle)", async () => {
    const errors = await hydrationErrors(
      h(LiveStatTicker, { initial, staticItems: STATIC }),
    );
    expect(errors).toEqual([]);
  });

  it("first paint renders the server-seeded order verbatim", () => {
    const html = renderToString(
      h(LiveStatTicker, { initial, staticItems: STATIC }),
    );
    // first occurrence of each item's (unique) label appears in the seeded order
    const positions = seededItems.map((i) => html.indexOf(`>${i.label}<`));
    expect(positions.every((p) => p >= 0)).toBe(true);
    const sorted = [...positions].sort((a, b) => a - b);
    expect(positions).toEqual(sorted);
  });
});

describe("live ↔ static mode switch", () => {
  it("live mode renders the LIVE 'now playing' tape", () => {
    const html = renderToString(
      h(LiveStatTicker, { initial, staticItems: STATIC }),
    );
    expect(html).toContain("Live match stats"); // live aria-label
    expect(html).toContain("primmie"); // a live-derived stat
    expect(html).not.toContain("Stat Ticker");
  });

  it("static mode (no live match) renders the curated tape", () => {
    const html = renderToString(h(StatTicker, { items: STATIC }));
    expect(html).toContain("Notable stats");
    expect(html).toContain("Demon1");
  });

  it("reverts to the static tape when a poll reports the match FINAL", async () => {
    vi.useFakeTimers();
    const finalMatch = { ...filledFixture, status: "final" };
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: [finalMatch], stale: false }), {
        status: 200,
      }),
    );

    const element = h(LiveStatTicker, { initial, staticItems: STATIC });
    const container = document.createElement("div");
    container.innerHTML = renderToString(element);
    const root = hydrateRoot(container, element);
    await act(async () => {});

    // live before the poll
    expect(container.innerHTML).toContain("Live match stats");

    // fire the 30s poll → final → revert to the static curated tape
    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });

    expect(container.innerHTML).toContain("Notable stats");
    expect(container.innerHTML).toContain("Demon1");
    expect(container.innerHTML).not.toContain("Live match stats");

    root.unmount();
  });
});
