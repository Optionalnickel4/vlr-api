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
