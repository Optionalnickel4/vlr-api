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
    // default R2.0-desc: Bravo (1.24) is rank 1 — appears in both podium and table.
    expect(ssrHtml).toContain("Bravo");
    // In the table body specifically, R2.0-desc puts Bravo before Alpha.
    // (The podium renders silver/Alpha left of gold/Bravo, so the raw ssrHtml
    // indexOf order is now podium-driven — assert on the table body slice only.)
    const tableStart = ssrHtml.indexOf("<tbody");
    expect(ssrHtml.indexOf("Bravo", tableStart)).toBeLessThan(
      ssrHtml.indexOf("Alpha", tableStart),
    );
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

// ── podium island ─────────────────────────────────────────────────────────────
// Fixture: Alpha r2=1.05 acs=998, Bravo r2=1.24 acs=1024, Charlie r2=null acs=1100.
// Default sort: R2.0 desc → rank1=Bravo, rank2=Alpha, rank3=Charlie.

describe("StatsLeaderboard island — podium", () => {
  it("renders rank-1 player in the gold slot with R2.0 headline", async () => {
    const initial = envelope(normalizeStats(statsFixture));
    const { container, root } = await mountIsland(initial);
    const r1 = container.querySelector("[data-podium-rank='1']");
    expect(r1).not.toBeNull();
    expect(r1!.textContent).toContain("Bravo"); // top by R2.0
    expect(r1!.textContent).toContain("1.24"); // Bravo's R2.0
    root.unmount();
  });

  it("renders rank-2 and rank-3 players in the flanking slots", async () => {
    const initial = envelope(normalizeStats(statsFixture));
    const { container, root } = await mountIsland(initial);
    const r2 = container.querySelector("[data-podium-rank='2']");
    const r3 = container.querySelector("[data-podium-rank='3']");
    expect(r2).not.toBeNull();
    expect(r3).not.toBeNull();
    expect(r2!.textContent).toContain("Alpha"); // rank 2 by R2.0
    expect(r3!.textContent).toContain("Charlie"); // rank 3 (null r2, sinks last)
    root.unmount();
  });

  it("podium re-ranks when sort changes to ACS (Charlie rises to #1)", async () => {
    // ACS desc: Charlie=1100 → rank1, Bravo=1024 → rank2, Alpha=998 → rank3
    const initial = envelope(normalizeStats(statsFixture));
    const { container, root } = await mountIsland(initial);
    const acsHeader = Array.from(container.querySelectorAll("th")).find(
      (th) => th.textContent?.trim() === "ACS",
    )!;
    expect(acsHeader).toBeTruthy();
    await act(async () => {
      acsHeader.dispatchEvent(new Event("click", { bubbles: true }));
    });
    const r1 = container.querySelector("[data-podium-rank='1']");
    expect(r1!.textContent).toContain("Charlie");
    root.unmount();
  });

  it("podium updates after region toggle changes the data", async () => {
    const initial = envelope(normalizeStats(statsFixture));
    // EU response returns a single player — Bravo — as the only result
    const euBravo = envelope(normalizeStats([statsFixture[1]])); // Bravo only
    const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(json(euBravo));
    const { container, root } = await mountIsland(initial);

    const euBtn = Array.from(container.querySelectorAll("button")).find(
      (b) => b.textContent?.trim() === "EU",
    )!;
    await act(async () => {
      euBtn.dispatchEvent(new Event("click", { bubbles: true }));
    });
    await act(async () => { await Promise.resolve(); });

    expect(spy).toHaveBeenCalledWith(expect.stringContaining("region=eu"), expect.anything());
    const r1 = container.querySelector("[data-podium-rank='1']");
    expect(r1!.textContent).toContain("Bravo");
    root.unmount();
  });

  it("degrades gracefully with 1 player — only rank-1 block renders, no crash", async () => {
    const one = envelope(normalizeStats(statsFixture).slice(0, 1));
    const { container, root } = await mountIsland(one);
    expect(container.querySelector("[data-podium-rank='1']")).not.toBeNull();
    expect(container.querySelector("[data-podium-rank='2']")).toBeNull();
    expect(container.querySelector("[data-podium-rank='3']")).toBeNull();
    root.unmount();
  });

  it("degrades gracefully with 2 players — no crash on undefined data[2]", async () => {
    const two = envelope(normalizeStats(statsFixture).slice(0, 2));
    const { container, root } = await mountIsland(two);
    expect(container.querySelector("[data-podium-rank='1']")).not.toBeNull();
    expect(container.querySelector("[data-podium-rank='2']")).not.toBeNull();
    expect(container.querySelector("[data-podium-rank='3']")).toBeNull();
    root.unmount();
  });

  it("gold (#1) block carries the warn border class", async () => {
    const initial = envelope(normalizeStats(statsFixture));
    const { container, root } = await mountIsland(initial);
    const r1 = container.querySelector("[data-podium-rank='1']");
    expect(r1?.className).toContain("warn");
    root.unmount();
  });

  it("podium is absent when the leaderboard is empty (no crash)", async () => {
    const { container, root } = await mountIsland(envelope([]));
    expect(container.querySelector("[data-podium-rank='1']")).toBeNull();
    root.unmount();
  });
});
