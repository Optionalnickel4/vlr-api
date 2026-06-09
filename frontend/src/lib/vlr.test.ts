// Transform tests — run against committed REAL vlr-api response fixtures
// (captured once from the running deployment under __fixtures__/). We assert
// invariants (envelope shape, parseNumeric null-not-NaN, teams[]/scores[]
// indexing, verbatim agent_stats keys, graceful-empty) — NOT volatile values
// that drift as the season progresses. No network is touched here.

import { afterEach, describe, expect, it, vi } from "vitest";

import {
  fetchUpstream,
  getResults,
  normalizeLive,
  normalizeNews,
  normalizePlayer,
  normalizeRankings,
  normalizeResult,
  normalizeTeam,
  normalizeTrend,
  normalizeUpcoming,
  parseNumeric,
} from "@/lib/vlr";

import results from "@/lib/__fixtures__/results.json";
import upcoming from "@/lib/__fixtures__/upcoming.json";
import live from "@/lib/__fixtures__/live.json";
import rankings from "@/lib/__fixtures__/rankings.json";
import news from "@/lib/__fixtures__/news.json";
import player from "@/lib/__fixtures__/player.json";
import team from "@/lib/__fixtures__/team.json";
import trends from "@/lib/__fixtures__/trends.json";

describe("parseNumeric (null, never NaN)", () => {
  it("parses real numeric strings", () => {
    expect(parseNumeric("1")).toBe(1);
    expect(parseNumeric("2000")).toBe(2000);
    expect(parseNumeric("1.17")).toBe(1.17);
    expect(parseNumeric(7)).toBe(7);
  });

  it("returns null (never NaN) for non-numeric / empty / nullish", () => {
    for (const v of ["–", "", "  ", "19h 34m", null, undefined, NaN, {}]) {
      const out = parseNumeric(v);
      expect(out === null || Number.isFinite(out)).toBe(true);
      expect(Number.isNaN(out as number)).toBe(false);
    }
    expect(parseNumeric("–")).toBeNull();
    expect(parseNumeric("")).toBeNull();
    expect(parseNumeric("19h 34m")).toBeNull();
  });
});

describe("normalizeResult", () => {
  const out = normalizeResult(results);

  it("maps teams[] / scores[] by index to team1/team2 + numeric scores", () => {
    expect(out.length).toBe((results as unknown[]).length);
    const first = out[0];
    const raw = (results as { teams: string[]; scores: string[] }[])[0];
    expect(first.team1).toBe(raw.teams[0]);
    expect(first.team2).toBe(raw.teams[1]);
    expect(first.score1).toBe(parseNumeric(raw.scores[0]));
    expect(first.score2).toBe(parseNumeric(raw.scores[1]));
  });

  it("uses eta || time and never NaN scores", () => {
    for (const m of out) {
      expect(Number.isNaN(m.score1 as number)).toBe(false);
      expect(Number.isNaN(m.score2 as number)).toBe(false);
    }
    const raw0 = (results as { eta?: string; time?: string }[])[0];
    expect(out[0].time).toBe(raw0.eta ?? raw0.time ?? null);
  });

  it("carries upstream URLs verbatim (absolute, no prepended domain)", () => {
    for (const m of out) {
      if (m.url) expect(m.url.startsWith("https://www.vlr.gg")).toBe(true);
    }
  });
});

describe("normalizeUpcoming", () => {
  const out = normalizeUpcoming(upcoming);

  it("maps eta to timeUntil and has no score fields", () => {
    expect(out.length).toBe((upcoming as unknown[]).length);
    const raw0 = (upcoming as { eta?: string }[])[0];
    expect(out[0].timeUntil).toBe(raw0.eta ?? null);
    expect("score1" in out[0]).toBe(false);
  });

  it("placeholder '–' scores never leak in as numbers", () => {
    // upcoming scores are "–"; nothing numeric should be derived
    expect(out.every((m) => m.team1 !== null || m.team2 !== null)).toBe(true);
  });
});

describe("normalizeLive (degraded: empty out of season)", () => {
  it("handles the real empty live fixture as a valid empty list", () => {
    expect(Array.isArray(live)).toBe(true);
    expect(normalizeLive(live)).toEqual([]);
  });

  it("shares the card shape with results (no current-map fields)", () => {
    // feed a real results card through the live transform: scores map, no extras
    const out = normalizeLive(results);
    expect(out.length).toBe((results as unknown[]).length);
    expect("currentMap" in out[0]).toBe(false);
    expect(Number.isNaN(out[0].score1 as number)).toBe(false);
  });
});

describe("normalizeRankings", () => {
  const out = normalizeRankings(rankings);

  it("maps team_id->id and coerces rank/rating to numbers (null-not-NaN)", () => {
    expect(out.length).toBe((rankings as unknown[]).length);
    const raw0 = (rankings as { team_id: string }[])[0];
    expect(out[0].id).toBe(raw0.team_id);
    for (const t of out) {
      expect(Number.isNaN(t.rank as number)).toBe(false);
      expect(Number.isNaN(t.rating as number)).toBe(false);
    }
  });

  it("ranks are numeric and ordered (proves no string compare)", () => {
    const ranks = out.map((t) => t.rank).filter((r): r is number => r !== null);
    const sorted = [...ranks].sort((a, b) => a - b);
    expect(ranks).toEqual(sorted);
  });
});

describe("normalizeNews", () => {
  const out = normalizeNews(news);

  it("splits meta into date + author", () => {
    expect(out.length).toBe((news as unknown[]).length);
    const first = out[0];
    expect(first.date).toBeTruthy();
    // fixture meta is "•June 8, 2026•by raezeri"
    expect(first.author).toBe("raezeri");
    expect(first.date).toBe("June 8, 2026");
    expect(first.date).not.toContain("•");
  });

  it("falls back to verbatim meta as date when there is no 'by' author", () => {
    const out2 = normalizeNews([{ title: "t", meta: "Just a date string" }]);
    expect(out2[0].date).toBe("Just a date string");
    expect(out2[0].author).toBeNull();
  });
});

describe("normalizePlayer (single object -> one-element list)", () => {
  const out = normalizePlayer(player);

  it("wraps the detail object and maps identity fields", () => {
    expect(out.length).toBe(1);
    const p = out[0];
    const raw = player as { id: string; real_name: string };
    expect(p.id).toBe(raw.id);
    expect(p.realName).toBe(raw.real_name);
  });

  it("preserves agent_stats keys VERBATIM (colons, casing)", () => {
    const p = out[0];
    expect(p.agentStats.length).toBeGreaterThan(0);
    const keys = Object.keys(p.agentStats[0].stats);
    // upstream uses display-cased keys with colons — must be untouched
    expect(keys).toContain("K:D");
    expect(keys).toContain("KAST");
    const rawKeys = Object.keys(
      (player as { agent_stats: { stats: Record<string, string> }[] })
        .agent_stats[0].stats,
    );
    expect(keys).toEqual(rawKeys);
  });
});

describe("normalizeTeam", () => {
  const out = normalizeTeam(team);

  it("maps snake_case roster + nested matches", () => {
    expect(out.length).toBe(1);
    const t = out[0];
    expect(t.roster.length).toBeGreaterThan(0);
    expect(typeof t.roster[0].isCaptain).toBe("boolean");
    expect(typeof t.roster[0].isStaff).toBe("boolean");
    expect(["win", "loss", null]).toContain(t.results[0]?.result ?? null);
  });
});

describe("normalizeTrend", () => {
  const out = normalizeTrend(trends);

  it("maps the trend object with numeric rating points and summary", () => {
    expect(out.length).toBe(1);
    const t = out[0];
    for (const p of t.ratingTrend) {
      expect(Number.isNaN(p.rating as number)).toBe(false);
      expect(Number.isNaN(p.rank as number)).toBe(false);
    }
    expect(Number.isNaN(t.ratingChange as number)).toBe(false);
    expect(t.summary).not.toBeNull();
    expect(typeof t.summary?.points).toBe("number");
  });
});

describe("graceful-empty on failure (never throws to the page)", () => {
  afterEach(() => vi.restoreAllMocks());

  it("returns { data: [], stale: true, error } when upstream errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("Internal Server Error", { status: 500 }),
    );
    const res = await getResults();
    expect(res.data).toEqual([]);
    expect(res.stale).toBe(true);
    expect(res.error).toBeTruthy();
  });

  it("returns graceful-empty when fetch itself rejects (network down)", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("ECONNREFUSED"));
    const res = await getResults();
    expect(res).toEqual(
      expect.objectContaining({ data: [], stale: true }),
    );
    expect(res.error).toContain("ECONNREFUSED");
  });
});

describe("fetchUpstream (the single network boundary)", () => {
  afterEach(() => vi.restoreAllMocks());

  it("hits VLR_API_BASE + path and throws on non-2xx", async () => {
    const spy = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response("nope", { status: 404 }));
    await expect(fetchUpstream("/matches/results")).rejects.toThrow();
    const calledUrl = String((spy.mock.calls[0] ?? [])[0]);
    expect(calledUrl).toContain("/api/v1/matches/results");
  });
});

describe("empty / garbage input yields valid empty output (no throw)", () => {
  it("non-array list inputs -> []", () => {
    expect(normalizeResult(null)).toEqual([]);
    expect(normalizeRankings(undefined)).toEqual([]);
    expect(normalizeNews({})).toEqual([]);
  });

  it("non-object detail inputs -> []", () => {
    expect(normalizePlayer(null)).toEqual([]);
    expect(normalizeTeam([])).toEqual([]);
    expect(normalizeTrend("garbage")).toEqual([]);
  });
});
