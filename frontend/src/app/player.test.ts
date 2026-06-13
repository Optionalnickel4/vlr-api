// @vitest-environment node
//
// Player detail page guard. We drive the REAL page + real data layer through a
// mocked fetch (no network), asserting the page contract: it LEADS with the rich
// per-agent stats (verbatim display-cased keys), shows the secondary trend's
// honest young-history note (never a fake flat line) when history is thin, and
// degrades to a page-level graceful error — HTTP 200, not a crash — when the
// detail endpoint fails. Mirrors the team page's behavior + landing.test.ts setup.

import { afterEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import PlayerPage from "@/app/player/[id]/page";
import playerFixture from "@/lib/__fixtures__/player.json";

// A deliberately THIN trend (one point) — the expected launch state for almost
// every player until snapshots accumulate. <2 points → young-history note.
const YOUNG_TREND = {
  player_id: "9",
  player: "TenZ",
  team: "Sentinels",
  window_days: 90,
  rating_trend: [
    { captured_at: "2026-06-08T12:00:00+00:00", rating: 1.15, acs: 251.8, rounds: 9298 },
  ],
  rating_change: null,
  acs_change: null,
  summary: { points: 1, current_rating: 1.15, peak_rating: 1.15, current_acs: 251.8, peak_acs: 251.8 },
  note: "no parseable rating in the window — thin/young history",
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

/** Route the data layer's single fetch boundary. `playerStatus` lets a test fail
 *  the detail endpoint (→ graceful error page); the trend defaults to YOUNG. */
function mockFetch(opts: { playerStatus?: number; trend?: unknown } = {}) {
  return vi.spyOn(globalThis, "fetch").mockImplementation((async (
    input: string | URL | Request,
  ) => {
    const url = String(input);
    if (url.includes("/trends/player/")) return jsonResponse(opts.trend ?? YOUNG_TREND);
    if (url.includes("/player/")) return jsonResponse(playerFixture, opts.playerStatus ?? 200);
    return jsonResponse({}, 404);
  }) as typeof fetch);
}

async function render(id = "9"): Promise<string> {
  return renderToStaticMarkup(await PlayerPage({ params: Promise.resolve({ id }) }));
}

afterEach(() => vi.restoreAllMocks());

describe("player detail page", () => {
  it("LEADS with identity + per-agent stats, VERBATIM display-cased keys", async () => {
    mockFetch();
    const html = await render();
    expect(html).toContain("TenZ"); // alias identity
    expect(html).toContain("Agent Stats");
    // upstream keys are rendered as column heads UNCHANGED (colons, casing)
    expect(html).toContain("K:D");
    expect(html).toContain("KAST");
    expect(html).toContain("Rating");
    // a verbatim agent-row value from the fixture (jett ACS)
    expect(html).toContain("263.8");
  });

  it("thin trend → honest young-history NOTE, not a fake sparkline line", async () => {
    mockFetch(); // YOUNG_TREND has a single point
    const html = await render();
    expect(html).toContain("History is still young");
    expect(html).not.toContain("<svg"); // Sparkline never drawn for <2 points
  });

  it("upstream detail failure → page-level graceful error (200, not a crash)", async () => {
    mockFetch({ playerStatus: 500 });
    const html = await render();
    expect(html).toContain("load this player"); // the graceful unavailable panel
    expect(html).toContain("unavailable");
    expect(html).not.toContain("Agent Stats"); // no detail rendered
  });
});
