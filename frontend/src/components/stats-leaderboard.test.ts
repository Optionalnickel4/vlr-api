// @vitest-environment happy-dom
//
// Stats leaderboard (Phase 12) — data-layer + island behavior. Covers:
//   1. normalizeStats pure transform (snake→camel, parseNumeric null-not-NaN,
//      CL fraction passthrough).
//   2. sortLeaders NUMERIC correctness — the "998" < "1024" lexical-sort trap.
//   3. R2.0-descending default order (nulls sink).
//   4. SSR↔hydrate parity — zero hydration mismatch.
//   5. Region/timespan toggle refetches with the new params.
//   6. Empty + error render.
// No network in the pure tests; the island's fetch is mocked.

import { afterEach, describe, expect, it, vi } from "vitest";
import { createElement as h, act } from "react";
import { renderToString } from "react-dom/server";
import { hydrateRoot } from "react-dom/client";

import { StatsLeaderboard } from "@/components/StatsLeaderboard";
import {
  normalizeStats,
  sortLeaders,
  DEFAULT_STAT_SORT,
  DEFAULT_STAT_DIR,
} from "@/lib/vlr";
import type { ApiResponse, StatLeader } from "@/types/vlr";

import statsFixture from "@/lib/__fixtures__/stats.json";

(globalThis as unknown as { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT =
  true;

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

function envelope(data: StatLeader[]): ApiResponse<StatLeader> {
  return { data, stale: false };
}

async function mountIsland(initial: ApiResponse<StatLeader>) {
  const element = h(StatsLeaderboard, { initial, initialRegion: "na", initialTimespan: "all" });
  const ssrHtml = renderToString(element);
  const container = document.createElement("div");
  container.innerHTML = ssrHtml;

  const seen: string[] = [];
  const spy = vi.spyOn(console, "error").mockImplementation((...args) => {
    seen.push(args.map(String).join(" "));
  });
  const root = hydrateRoot(container, element, {
    onRecoverableError: (e) => seen.push(String(e)),
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

// ── pure transform ────────────────────────────────────────────────────────────

describe("normalizeStats", () => {
  const rows = normalizeStats(statsFixture);

  it("maps snake_case upstream keys to the camelCase StatLeader shape", () => {
    const a = rows[0];
    expect(a.player).toBe("Alpha");
    expect(a.playerId).toBe("1");
    expect(a.r2).toBe(1.05);
    expect(a.clWon).toBe(19);
    expect(a.clPlayed).toBe(104);
    expect(a.clutchPct).toBe(18);
  });

  it("keeps nulls as null, never NaN (parseNumeric contract)", () => {
    const c = rows[2];
    expect(c.r2).toBeNull();
    expect(c.hs).toBeNull();
    expect(c.clWon).toBeNull();
    for (const v of [c.r2, c.hs, c.clWon, c.kmax]) {
      expect(Number.isNaN(v as number)).toBe(false);
    }
  });

  it("returns [] for non-array input (graceful)", () => {
    expect(normalizeStats(null)).toEqual([]);
    expect(normalizeStats({})).toEqual([]);
  });
});

// ── numeric-sort correctness (the string-sort trap) ─────────────────────────────

describe("sortLeaders — numeric, never lexical", () => {
  const rows = normalizeStats(statsFixture); // ACS: 998, 1024, 1100

  it("sorts ACS descending as NUMBERS (1024 above 998, not lexical)", () => {
    const out = sortLeaders(rows, "acs", "desc");
    expect(out.map((r) => r.acs)).toEqual([1100, 1024, 998]);
    // lexical sort would order "1024" < "998" → the trap. Assert it didn't.
    const idx1024 = out.findIndex((r) => r.acs === 1024);
    const idx998 = out.findIndex((r) => r.acs === 998);
    expect(idx1024).toBeLessThan(idx998);
  });

  it("sorts ascending too", () => {
    const out = sortLeaders(rows, "acs", "asc");
    expect(out.map((r) => r.acs)).toEqual([998, 1024, 1100]);
  });

  it("survives raw STRING values via the parseNumeric boundary", () => {
    const raw = [
      { player: "X", acs: "998" },
      { player: "Y", acs: "1024" },
    ];
    const out = sortLeaders(normalizeStats(raw), "acs", "desc");
    expect(out.map((r) => r.player)).toEqual(["Y", "X"]); // 1024 > 998 numerically
  });

  it("R2.0 descending is the default, with nulls sinking to the bottom", () => {
    expect(DEFAULT_STAT_SORT).toBe("r2");
    expect(DEFAULT_STAT_DIR).toBe("desc");
    const out = sortLeaders(rows, DEFAULT_STAT_SORT, DEFAULT_STAT_DIR);
    expect(out.map((r) => r.r2)).toEqual([1.24, 1.05, null]); // null last
  });
});

// ── SSR ↔ hydrate parity ─────────────────────────────────────────────────────

describe("StatsLeaderboard island — SSR ↔ hydrate parity", () => {
  it("renders identically on server and client with zero hydration errors", async () => {
    const initial = envelope(normalizeStats(statsFixture));
    const { ssrHtml, hydrationErrors, root } = await mountIsland(initial);
    // default R2.0-desc order → Bravo (1.24) renders before Alpha (1.05)
    expect(ssrHtml.indexOf("Bravo")).toBeGreaterThan(-1);
    expect(ssrHtml.indexOf("Bravo")).toBeLessThan(ssrHtml.indexOf("Alpha"));
    expect(hydrationErrors).toEqual([]);
    root.unmount();
  });
});

// ── toggle refetch ──────────────────────────────────────────────────────────

describe("StatsLeaderboard island — region/timespan toggle refetch", () => {
  it("refetches /api/stats with the new region when EU is clicked", async () => {
    const initial = envelope(normalizeStats(statsFixture));
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(json(envelope([])));

    const { container, root } = await mountIsland(initial);
    // no fetch on the initial mount (server already seeded the data)
    expect(spy).not.toHaveBeenCalled();

    const euBtn = Array.from(container.querySelectorAll("button")).find(
      (b) => b.textContent?.trim() === "EU",
    )!;
    expect(euBtn).toBeTruthy();

    await act(async () => {
      euBtn.dispatchEvent(new Event("click", { bubbles: true }));
    });
    await act(async () => {
      await Promise.resolve();
    });

    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy).toHaveBeenCalledWith(
      expect.stringContaining("region=eu"),
      expect.anything(),
    );
    root.unmount();
  });

  it("refetches with the new timespan when 90D is clicked", async () => {
    const initial = envelope(normalizeStats(statsFixture));
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(json(envelope([])));

    const { container, root } = await mountIsland(initial);
    const btn = Array.from(container.querySelectorAll("button")).find(
      (b) => b.textContent?.trim() === "90D",
    )!;
    await act(async () => {
      btn.dispatchEvent(new Event("click", { bubbles: true }));
    });
    await act(async () => {
      await Promise.resolve();
    });
    expect(spy).toHaveBeenCalledWith(
      expect.stringContaining("timespan=90d"),
      expect.anything(),
    );
    root.unmount();
  });
});

// ── empty + error render ──────────────────────────────────────────────────────

describe("StatsLeaderboard island — empty + error states", () => {
  it("renders the empty state with no rows", async () => {
    const { container, root } = await mountIsland(envelope([]));
    expect(container.textContent).toContain("No leaderboard data");
    root.unmount();
  });

  it("renders the error from the seeded envelope", async () => {
    const { container, root } = await mountIsland({
      data: [],
      stale: true,
      error: "upstream timeout",
    });
    expect(container.textContent).toContain("upstream timeout");
    root.unmount();
  });
});
