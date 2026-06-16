// @vitest-environment node
//
// Landing restructure guard: the home page (match center) is a compact SNAPSHOT
// capped at HOME_SNAPSHOT_LIMIT per section, while the dedicated /schedule and
// /results pages render the FULL upstream lists. We drive the real pages + real
// data layer through a mocked fetch (no network) and count rendered match cards
// by their /match/<id> links — upcoming ids are u*, results ids r*, so the two
// sections are countable independently.

import { afterEach, describe, expect, it, vi } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";

import MatchCenter from "@/app/page";
import SchedulePage from "@/app/schedule/page";
import ResultsPage from "@/app/results/page";
import NewsPage from "@/app/news/page";
import RankingsPage from "@/app/rankings/page";
import { HOME_SNAPSHOT_LIMIT } from "@/lib/vlr";

const FULL = 50;

// Upstream match-card shape (teams[]/scores[] indexing) — distinguishable by id.
const UPCOMING = Array.from({ length: FULL }, (_, i) => ({
  id: `u${i}`,
  teams: [`UA${i}`, `UB${i}`],
  scores: ["–", "–"],
  eta: "1h",
  series: "Swiss",
  event: "Masters",
  url: `https://www.vlr.gg/u${i}`,
}));
const RESULTS = Array.from({ length: FULL }, (_, i) => ({
  id: `r${i}`,
  teams: [`RA${i}`, `RB${i}`],
  scores: [2, 1],
  eta: "2h ago",
  series: "Swiss",
  event: "Masters",
  url: `https://www.vlr.gg/r${i}`,
}));

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

const SAMPLE_NEWS = [
  { title: "Top fragger transfer shakes up roster", description: "Details inside.", meta: "• June 2026 • by staff", url: "https://www.vlr.gg/news/1/stub" },
];
const SAMPLE_RANKINGS = [
  { team_id: "2", rank: "1", team: "Sentinels", country: "United States", rating: "1024" },
];

// 10 news items — landing should show exactly 5, /news full page all 10.
const NEWS_MANY = Array.from({ length: 10 }, (_, i) => ({
  title: `Breaking news item ${i}`,
  description: "desc",
  meta: `• June 2026 • by author${i}`,
  url: `https://www.vlr.gg/news/${i}`,
}));
// 7 EU teams (rank 1-7) + 7 NA teams (rank 1-7, rank resets = new region).
// Landing teaser should show 5 EU + 5 NA = 10; full page all 14.
const RANKINGS_MULTI = [
  ...Array.from({ length: 7 }, (_, i) => ({
    team_id: String(i + 1), rank: String(i + 1), team: `EU Team ${i + 1}`,
    country: "Germany", rating: String(2000 - i * 50),
  })),
  ...Array.from({ length: 7 }, (_, i) => ({
    team_id: String(i + 100), rank: String(i + 1), team: `NA Team ${i + 1}`,
    country: "United States", rating: String(1900 - i * 50),
  })),
];

/** Route the data layer's single fetch boundary: full upcoming/results, empty
 *  for everything else; ticker/streamer fan-out (match detail, trends) → 404 →
 *  graceful-empty, so only the upcoming/results cards appear. */
function mockFetch() {
  return vi.spyOn(globalThis, "fetch").mockImplementation((async (
    input: string | URL | Request,
  ) => {
    const url = String(input);
    if (url.includes("/matches/upcoming")) return jsonResponse(UPCOMING);
    if (url.includes("/matches/results")) return jsonResponse(RESULTS);
    if (url.includes("/matches/live")) return jsonResponse([]);
    if (url.includes("/rankings")) return jsonResponse([]);
    if (url.includes("/news")) return jsonResponse([]);
    return jsonResponse({}, 404); // match detail / trends fan-out → graceful
  }) as typeof fetch);
}

/** Returns multi-item news + multi-region rankings to exercise teaser caps. */
function mockFetchMulti() {
  return vi.spyOn(globalThis, "fetch").mockImplementation((async (
    input: string | URL | Request,
  ) => {
    const url = String(input);
    if (url.includes("/matches/upcoming")) return jsonResponse(UPCOMING);
    if (url.includes("/matches/results")) return jsonResponse(RESULTS);
    if (url.includes("/matches/live")) return jsonResponse([]);
    if (url.includes("/rankings")) return jsonResponse(RANKINGS_MULTI);
    if (url.includes("/news")) return jsonResponse(NEWS_MANY);
    return jsonResponse({}, 404);
  }) as typeof fetch);
}

/** Like mockFetch but returns sample news + rankings so see-all links render. */
function mockFetchFull() {
  return vi.spyOn(globalThis, "fetch").mockImplementation((async (
    input: string | URL | Request,
  ) => {
    const url = String(input);
    if (url.includes("/matches/upcoming")) return jsonResponse(UPCOMING);
    if (url.includes("/matches/results")) return jsonResponse(RESULTS);
    if (url.includes("/matches/live")) return jsonResponse([]);
    if (url.includes("/rankings")) return jsonResponse(SAMPLE_RANKINGS);
    if (url.includes("/news")) return jsonResponse(SAMPLE_NEWS);
    return jsonResponse({}, 404);
  }) as typeof fetch);
}

/** Count non-overlapping occurrences of a marker substring. */
function count(html: string, needle: string): number {
  return html.split(needle).length - 1;
}

afterEach(() => vi.restoreAllMocks());

describe("landing snapshot vs dedicated full-list pages", () => {
  it(`home caps Upcoming + Results at ${HOME_SNAPSHOT_LIMIT} each, with View-all links out`, async () => {
    mockFetch();
    const html = renderToStaticMarkup(await MatchCenter());

    expect(count(html, 'href="/match/u')).toBe(HOME_SNAPSHOT_LIMIT);
    expect(count(html, 'href="/match/r')).toBe(HOME_SNAPSHOT_LIMIT);
    // each snapshot's "view all" footer links to its dedicated full-list page
    // (labels are snapshot-specific, distinct from the always-present nav links)
    expect(html).toContain("Full schedule");
    expect(html).toContain("All results");
    expect(html).toContain('href="/schedule"');
    expect(html).toContain('href="/results"');
    // the real total is still surfaced in the heading count (50), not the cap
    expect(html).toContain(String(FULL));
  });

  it("/schedule renders the FULL upcoming list (all 50)", async () => {
    mockFetch();
    const html = renderToStaticMarkup(await SchedulePage());
    expect(count(html, 'href="/match/u')).toBe(FULL);
    // a dedicated full-list page is NOT a capped snapshot → no "view all" footer
    expect(html).not.toContain("Full schedule");
  });

  it("/results renders the FULL results list (all 50)", async () => {
    mockFetch();
    const html = renderToStaticMarkup(await ResultsPage());
    expect(count(html, 'href="/match/r')).toBe(FULL);
  });
});

describe("news + rankings full pages and see-all links", () => {
  it("home nav always includes News and Rankings links", async () => {
    mockFetch();
    const html = renderToStaticMarkup(await MatchCenter());
    expect(html).toContain('href="/news"');
    expect(html).toContain('href="/rankings"');
  });

  it("home shows All news and Full rankings see-all links when panels have data", async () => {
    mockFetchFull();
    const html = renderToStaticMarkup(await MatchCenter());
    expect(html).toContain("All news");
    expect(html).toContain("Full rankings");
  });

  it("/news full page renders the feed without a see-all footer", async () => {
    mockFetchFull();
    const html = renderToStaticMarkup(await NewsPage());
    expect(html).toContain("Top fragger transfer");
    expect(html).not.toContain("All news");
  });

  it("/rankings full page renders the table without a see-all footer", async () => {
    mockFetchFull();
    const html = renderToStaticMarkup(await RankingsPage());
    expect(html).toContain("Sentinels");
    expect(html).not.toContain("Full rankings");
  });
});

describe("teaser caps: news capped at 5, rankings capped per region", () => {
  it("landing news shows ≤5 items; /news full page shows all 10", async () => {
    mockFetchMulti();
    const landingHtml = renderToStaticMarkup(await MatchCenter());
    const newsHtml = renderToStaticMarkup(await NewsPage());
    // landing: only 5 of the 10 "Breaking news item N" headlines appear
    expect(count(landingHtml, "Breaking news item")).toBe(5);
    // full page: all 10 appear and there is no see-all footer
    expect(count(newsHtml, "Breaking news item")).toBe(10);
    expect(newsHtml).not.toContain("All news");
  });

  it("landing rankings teaser shows top of each region, not just the first region", async () => {
    mockFetchMulti();
    const html = renderToStaticMarkup(await MatchCenter());
    // both EU and NA representatives must appear
    expect(html).toContain("EU Team 1");
    expect(html).toContain("NA Team 1");
    // entries beyond the per-region cap (rank 6 and 7) must not appear
    expect(html).not.toContain("EU Team 6");
    expect(html).not.toContain("NA Team 6");
  });

  it("/rankings full page is uncapped — shows all 14 rows across both regions", async () => {
    mockFetchMulti();
    const html = renderToStaticMarkup(await RankingsPage());
    expect(html).toContain("EU Team 7");
    expect(html).toContain("NA Team 7");
    expect(html).not.toContain("Full rankings");
  });
});
