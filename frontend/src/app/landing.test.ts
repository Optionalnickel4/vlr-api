// @vitest-environment node
//
// Landing restructure guard: the home page (match center) is a compact SNAPSHOT
// capped at HOME_SNAPSHOT_LIMIT per section, while the dedicated /schedule and
// /results pages render the FULL upstream lists. We drive the real pages + real
// data layer through a mocked fetch (no network) and count rendered match cards
// by their /match/<id> links — upcoming ids are u*, results ids r*, so the two
// sections are countable independently.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderToPipeableStream, renderToStaticMarkup } from "react-dom/server";
import { PassThrough } from "node:stream";
import * as twitch from "@/lib/twitch";
import type { ApiResponse, FeaturedStream } from "@/types/vlr";

import MatchCenter from "@/app/page";
import SchedulePage from "@/app/schedule/page";
import ResultsPage from "@/app/results/page";
import NewsPage from "@/app/news/page";
import RankingsPage from "@/app/rankings/page";
import { HOME_SNAPSHOT_LIMIT } from "@/lib/vlr";

const FULL = 50;

beforeEach(() => vi.spyOn(twitch, "getFeaturedStreamers").mockResolvedValue({ data: [], stale: false }));

async function renderHome() {
  const page = await MatchCenter();
  return new Promise<string>((resolve, reject) => {
    let html = "";
    const output = new PassThrough();
    output.on("data", chunk => { html += chunk.toString(); });
    output.on("end", () => resolve(html));
    output.on("error", reject);
    const stream = renderToPipeableStream(page, {
      onAllReady() { stream.pipe(output); },
      onError(error) { stream.abort(); reject(error); },
    });
  });
}

it("streams match coverage before delayed news, rankings, and Twitch settle", async () => {
  const fetcher = mockFetch();
  const normal = fetcher.getMockImplementation()!;
  let resolveNews!: (response: Response) => void;
  let resolveRankings!: (response: Response) => void;
  const news = new Promise<Response>(resolve => { resolveNews = resolve; });
  const rankings = new Promise<Response>(resolve => { resolveRankings = resolve; });
  fetcher.mockImplementation((input, options) => {
    if (String(input).includes("/news")) return news;
    if (String(input).includes("/rankings")) return rankings;
    return normal(input, options);
  });
  let resolveStreams!: (value: ApiResponse<FeaturedStream>) => void;
  const pending = new Promise<ApiResponse<FeaturedStream>>(resolve => { resolveStreams = resolve; });
  vi.spyOn(twitch, "getFeaturedStreamers").mockReturnValue(pending);
  const page = await MatchCenter(); // must not await optional work
  const output = new PassThrough();
  let html = "";
  let ready!: () => void;
  const coverage = new Promise<void>(resolve => { ready = resolve; });
  const finished = new Promise<void>((resolve, reject) => {
    output.on("data", chunk => {
      html += chunk.toString();
      if (html.includes('/match/u0')) ready();
    });
    output.on("end", resolve);
    output.on("error", reject);
  });
  const errors: unknown[] = [];
  const stream = renderToPipeableStream(page, {
    onShellReady() { stream.pipe(output); },
    onError(error) { errors.push(error); },
  });
  try {
    await coverage;
    expect(html).not.toContain("Delayed broadcast");
    expect(html).not.toContain(SAMPLE_NEWS[0].title);
    expect(html).not.toContain("Sentinels");
    expect(html).toContain("Loading news");
    expect(html).toContain("Loading rankings");
    expect(fetcher.mock.calls.filter(([url]) => String(url).includes("/matches/upcoming"))).toHaveLength(1);
    resolveNews(jsonResponse(SAMPLE_NEWS));
    resolveRankings(jsonResponse(SAMPLE_RANKINGS));
    resolveStreams({ data: [{
      login: "test", displayName: "Delayed broadcast", viewers: 10,
      title: null, game: "VALORANT", thumbnail: null, url: "https://twitch.tv/test",
    }], stale: false });
    await finished;
    expect(html).toContain("Delayed broadcast");
    expect(html).toContain(SAMPLE_NEWS[0].title);
    expect(html).toContain("Sentinels");
    expect(errors).toEqual([]);
  } finally {
    resolveNews(jsonResponse([]));
    resolveRankings(jsonResponse([]));
    resolveStreams({ data: [], stale: false });
    stream.abort();
  }
});

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
    const html = await renderHome();

    expect(count(html, 'href="/match/u')).toBe(HOME_SNAPSHOT_LIMIT + 1); // first match also featured
    expect(count(html, 'href="/match/u0"')).toBe(2);
    expect(Array.from(html.matchAll(/href="\/match\/(u\d+)"/g), m => m[1])).toEqual(["u0", "u0", "u1", "u2", "u3", "u4"]);
    expect(Array.from(html.matchAll(/href="\/match\/(r\d+)"/g), m => m[1])).toEqual(["r0", "r1", "r2", "r3", "r4"]);
    expect(html).not.toContain('href="/match/u5"');
    expect(html).not.toContain('href="/match/r5"');
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
  it("home owns one main landmark and heading; navigation belongs to the layout", async () => {
    mockFetch();
    const html = await renderHome();
    expect(count(html, 'id="main-content"')).toBe(1);
    expect(count(html, "<h1")).toBe(1);
    expect(html).not.toContain('aria-label="Primary"');
  });

  it("home shows All news and Full rankings see-all links when panels have data", async () => {
    mockFetchFull();
    const html = await renderHome();
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
    const html = renderToStaticMarkup(await RankingsPage({}));
    expect(html).toContain("Sentinels");
    expect(html).not.toContain("Full rankings");
  });
});

describe("teaser caps: news capped at 5, rankings capped per region", () => {
  it("landing news shows ≤5 items; /news full page shows all 10", async () => {
    mockFetchMulti();
    const landingHtml = await renderHome();
    const newsHtml = renderToStaticMarkup(await NewsPage());
    // landing: only 5 of the 10 "Breaking news item N" headlines appear
    expect(count(landingHtml, "Breaking news item")).toBe(5);
    // full page: all 10 appear and there is no see-all footer
    expect(count(newsHtml, "Breaking news item")).toBe(10);
    expect(newsHtml).not.toContain("All news");
  });

  it("landing rankings teaser is #1-per-region only: EU #1 and NA #1 appear, rank-2+ do not", async () => {
    mockFetchMulti();
    const html = await renderHome();
    // regional kings: #1 from every region must appear
    expect(html).toContain("EU Team 1");
    expect(html).toContain("NA Team 1");
    // rank-2+ from any region must NOT appear (proves #1-per-region, not 5-per-region)
    expect(html).not.toContain("EU Team 2");
    expect(html).not.toContain("NA Team 2");
  });

  it("/rankings full page is uncapped — shows all 14 rows across both regions", async () => {
    mockFetchMulti();
    const html = renderToStaticMarkup(await RankingsPage({}));
    expect(html).toContain("EU Team 7");
    expect(html).toContain("NA Team 7");
    expect(html).not.toContain("Full rankings");
  });
});


it("keeps discovery links and coverage when secondary content is unavailable", async () => {
  const fetcher = mockFetch();
  const normal = fetcher.getMockImplementation()!;
  fetcher.mockImplementation((input, options) => /\/(news|rankings)/.test(String(input))
    ? Promise.resolve(jsonResponse({}, 503)) : normal(input, options));
  vi.spyOn(twitch, "getFeaturedStreamers").mockResolvedValue({ data: [], stale: true, error: "offline" });
  const html = await renderHome();
  expect(html).toContain('href="/match/u0"');
  expect(html).toContain('href="/match/r0"');
  for (const route of ["news", "rankings", "stats", "schedule", "results"]) expect(html).toContain(`href="/${route}"`);
  expect(html).toContain("Updates unavailable.");
  expect(html).not.toContain("Latest headline");
  expect(html).not.toContain("Featured live streams");
});

it("promotes only the first real news story and preserves its metadata and destination", async () => {
  mockFetchMulti();
  const html = await renderHome();
  expect(count(html, "Latest headline")).toBe(1);
  expect(html.indexOf("Latest headline")).toBeLessThan(html.indexOf("Breaking news item 0"));
  expect(html.indexOf("Breaking news item 0")).toBeLessThan(html.indexOf("Breaking news item 1"));
  expect(html).toContain('href="https://www.vlr.gg/news/0"');
  expect(html).toContain("author0");
  expect(html).toContain('href="/stats"');
});

it("renders honest empty sections with their destinations", async () => {
  vi.spyOn(globalThis, "fetch").mockImplementation(async () => jsonResponse([]));
  const html = await renderHome();
  expect(html).toContain("No live matches right now.");
  expect(html).toContain("No upcoming matches scheduled.");
  expect(html).toContain("No recent results.");
  expect(html).toContain("No news right now.");
  expect(html).toContain("No rankings available.");
  expect(html).not.toContain("Updates unavailable");
  for (const route of ["news", "rankings", "stats", "schedule", "results"]) expect(html).toContain(`href="/${route}"`);
});

it("streams live scores without waiting for upcoming and reuses the single upcoming load", async () => {
  const fetcher = mockFetch();
  const normal = fetcher.getMockImplementation()!;
  let release!: (response: Response) => void;
  const pending = new Promise<Response>(resolve => { release = resolve; });
  fetcher.mockImplementation((input, options) => {
    if (String(input).includes("/matches/upcoming")) return pending;
    if (String(input).includes("/matches/live")) return Promise.resolve(jsonResponse([
      { id: "live-now", teams: ["Live Alpha", "Live Bravo"], scores: [3, 2], event: "Masters", series: "Final", url: null },
    ]));
    return normal(input, options);
  });
  const page = await MatchCenter();
  let html = "";
  let ready!: () => void;
  const liveReady = new Promise<void>(resolve => { ready = resolve; });
  const output = new PassThrough();
  const finished = new Promise<void>((resolve, reject) => {
    output.on("data", chunk => {
      html += chunk.toString();
      if (html.includes('href="/match/live-now"')) ready();
    });
    output.on("end", resolve);
    output.on("error", reject);
  });
  const errors: unknown[] = [];
  const stream = renderToPipeableStream(page, {
    onShellReady() { stream.pipe(output); },
    onError(error) { errors.push(error); },
  });
  try {
    await liveReady;
    expect(html).toContain('aria-label="Score 3 to 2"');
    expect(html).not.toContain('href="/match/u0"');
    release(jsonResponse(UPCOMING));
    await finished;
    expect(count(html, 'href="/match/u')).toBe(HOME_SNAPSHOT_LIMIT);
    expect(fetcher.mock.calls.filter(([url]) => String(url).includes("/matches/upcoming"))).toHaveLength(1);
    expect(errors).toEqual([]);
  } finally {
    release(jsonResponse([]));
    stream.abort();
  }
});
