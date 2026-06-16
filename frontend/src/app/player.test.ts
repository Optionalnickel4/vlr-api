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
import { normalizePlayer, normalizePlayerDimensions, playerOverall } from "@/lib/vlr";
import playerFixture from "@/lib/__fixtures__/player.json";

// Dimension scores for TenZ from the stats fixture cohort (hand-verified values
// computed by the backend: Firepower=100, Entry=75, Consistency=90, Clutch=65).
const DIMS_FIXTURE = {
  player_id: "9",
  region: "na",
  timespan: "all",
  firepower: 100.0,
  entry: 75.0,
  consistency: 90.0,
  clutch: 65.0,
  low_confidence: [],
};

const DIMS_LOW_CONFIDENCE = {
  ...DIMS_FIXTURE,
  clutch: 30.0,
  low_confidence: ["clutch"],
};

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

/** Route the data layer's single fetch boundary.
 *  - playerStatus: HTTP status for the /player/{id} endpoint (default 200).
 *  - dims: response for /players/{id}/dimensions (default null → 404 → no card).
 *  - trend: response for /trends/player/{id} (default YOUNG_TREND). */
function mockFetch(opts: {
  playerStatus?: number;
  trend?: unknown;
  dims?: unknown | null;
} = {}) {
  return vi.spyOn(globalThis, "fetch").mockImplementation((async (
    input: string | URL | Request,
  ) => {
    const url = String(input);
    if (url.includes("/trends/player/")) return jsonResponse(opts.trend ?? YOUNG_TREND);
    // dimensions endpoint: /players/{id}/dimensions (note: /players/ not /player/)
    if (url.includes("/players/") && url.includes("/dimensions")) {
      const d = opts.dims ?? null;
      return d ? jsonResponse(d) : jsonResponse({}, 404);
    }
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

  it("renders the player CARD header: weighted headline, signature chip, form", async () => {
    mockFetch();
    const html = await render();
    // headline label is "K/D" (slash) — distinct from the agent table's "K:D" (colon)
    expect(html).toContain("K/D");
    expect(html).toContain("ACS");
    // signature-agent chip ("Main" label) + recent-form strip ("Form" label)
    expect(html).toContain("Main");
    expect(html).toContain("Form");
    // the headline rating is a real weighted number, not a dash
    const overall = playerOverall(normalizePlayer(playerFixture)[0].agentStats);
    expect(overall.rating).not.toBeNull();
    expect(html).toContain((overall.rating as number).toFixed(2));
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

describe("player page — Phase 13 Rating Breakdown card", () => {
  it("renders the breakdown card below the player card when dims are available", async () => {
    mockFetch({ dims: DIMS_FIXTURE });
    const html = await render();
    expect(html).toContain("Rating Breakdown");
    // All four dimension labels must appear
    expect(html).toContain("Firepower");
    expect(html).toContain("Entry");
    expect(html).toContain("Consistency");
    expect(html).toContain("Clutch");
  });

  it("bars show the correct ordinal label with region (e.g. '75th in NA')", async () => {
    mockFetch({ dims: DIMS_FIXTURE });
    const html = await render();
    // DIMS_FIXTURE has firepower=100, entry=75, consistency=90, clutch=65
    expect(html).toContain("100th in NA");
    expect(html).toContain("75th in NA");
    expect(html).toContain("90th in NA");
    expect(html).toContain("65th in NA");
  });

  it("low_confidence dimension is marked with an asterisk", async () => {
    mockFetch({ dims: DIMS_LOW_CONFIDENCE });
    const html = await render();
    // The low-confidence "clutch" flag adds an asterisk next to CLUTCH
    expect(html).toContain("*"); // asterisk marker present
    // The tooltip text appears on the low-confidence element
    expect(html).toContain("Limited sample");
  });

  it("no breakdown card when player is not on any regional leaderboard", async () => {
    // dims=null → 404 from both na and eu → getPlayerDimensions returns empty → card hidden
    mockFetch({ dims: null });
    const html = await render();
    expect(html).not.toContain("Rating Breakdown");
    // The player card and stats table still render normally
    expect(html).toContain("TenZ");
    expect(html).toContain("Agent Stats");
  });

  it("normalizePlayerDimensions maps API response to typed shape", () => {
    const result = normalizePlayerDimensions(DIMS_FIXTURE);
    expect(result).toHaveLength(1);
    const d = result[0];
    expect(d.playerId).toBe("9");
    expect(d.region).toBe("na");
    expect(d.firepower).toBe(100.0);
    expect(d.entry).toBe(75.0);
    expect(d.consistency).toBe(90.0);
    expect(d.clutch).toBe(65.0);
    expect(d.lowConfidence).toEqual([]);
  });
});
