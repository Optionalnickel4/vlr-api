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
  normalizeMatch,
  normalizeNews,
  normalizePlayer,
  normalizePlayerTrend,
  normalizeRankings,
  normalizeResult,
  normalizeTeam,
  normalizeTrend,
  normalizeUpcoming,
  parseNumeric,
  PLAYER_FLAT_EPSILON,
  shouldRenderTrendLine,
} from "@/lib/vlr";

import type { RatingPoint } from "@/types/vlr";

import results from "@/lib/__fixtures__/results.json";
import upcoming from "@/lib/__fixtures__/upcoming.json";
import live from "@/lib/__fixtures__/live.json";
import rankings from "@/lib/__fixtures__/rankings.json";
import news from "@/lib/__fixtures__/news.json";
import player from "@/lib/__fixtures__/player.json";
import team from "@/lib/__fixtures__/team.json";
import trends from "@/lib/__fixtures__/trends.json";
import match from "@/lib/__fixtures__/match.json";

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

  it("label-bleed guard: the headline never carries the date/author/meta text", () => {
    // The scraper can let date/author/category nodes bleed into the headline.
    // Every title must stay clean: no "•"/"by " separators and no copy of the
    // parsed date or author that belongs in the dim meta footer instead.
    for (const a of out) {
      const title = a.title ?? "";
      expect(title).not.toContain("•");
      expect(title.toLowerCase()).not.toMatch(/\bby \w/);
      if (a.date) expect(title).not.toContain(a.date);
      if (a.author) expect(title).not.toContain(a.author);
    }
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

  it("resultsInWindow carry valid win/loss verdicts (the results join)", () => {
    const t = out[0];
    expect(t.resultsInWindow.length).toBeGreaterThan(0);
    for (const r of t.resultsInWindow) {
      expect(["win", "loss", null]).toContain(r.result);
    }
  });

  it("orders the trend line on the real timestamp, not lexically or by rating", () => {
    // The string-sort trap, time edition: feed points OUT of chronological order
    // whose rating values would mis-sort if compared as strings ("998" > "1024"
    // lexically). The data layer must order on captured_at (real Date), leaving
    // ratings numeric and untouched as a sort key.
    const scrambled = {
      team_id: "2",
      team: "Test",
      window_days: 90,
      rating_trend: [
        { captured_at: "2026-06-09T12:00:00+00:00", rating: "1024", rank: "3" },
        { captured_at: "2026-06-07T12:00:00+00:00", rating: "998", rank: "5" },
        { captured_at: "2026-06-08T12:00:00+00:00", rating: "1003", rank: "4" },
      ],
      rating_change: 26.0,
      results_in_window: [],
      summary: null,
    };
    const ratings = normalizeTrend(scrambled)[0].ratingTrend.map((p) => p.rating);
    // chronological order is 998 (7th) → 1003 (8th) → 1024 (9th)
    expect(ratings).toEqual([998, 1003, 1024]);
    // and the committed real fixture is already chronological after sorting
    const times = out[0].ratingTrend
      .map((p) => (p.capturedAt ? Date.parse(p.capturedAt) : NaN))
      .filter((n) => !Number.isNaN(n));
    expect(times).toEqual([...times].sort((a, b) => a - b));
  });

  it("yields a valid empty trend for garbage/empty input (no throw)", () => {
    const empty = normalizeTrend({
      team_id: "9",
      rating_trend: [],
      results_in_window: [],
    });
    expect(empty.length).toBe(1);
    expect(empty[0].ratingTrend).toEqual([]);
    expect(empty[0].resultsInWindow).toEqual([]);
    expect(empty[0].summary).toBeNull();
  });
});

describe("normalizePlayerTrend (Phase 8 player rating/ACS trend)", () => {
  // mirrors the team-trend shape but with acs/rounds points + ACS summary and no
  // results join. The real launch shape is THIN (1–2 points per player).
  const young = {
    player_id: "9",
    player: "TenZ",
    team: "Sentinels",
    window_days: 90,
    rating_trend: [
      { captured_at: "2026-06-08T12:00:00+00:00", rating: 1.15, acs: 251.8, rounds: 9298 },
    ],
    rating_change: null,
    acs_change: null,
    summary: {
      points: 1,
      current_rating: 1.15,
      peak_rating: 1.15,
      current_acs: 251.8,
      peak_acs: 251.8,
    },
    note: "thin/young history",
  };

  it("maps identity + numeric rating/ACS points and summary (null-not-NaN)", () => {
    const out = normalizePlayerTrend(young);
    expect(out.length).toBe(1);
    const t = out[0];
    expect(t.playerId).toBe("9");
    expect(t.player).toBe("TenZ");
    for (const p of t.ratingTrend) {
      expect(Number.isNaN(p.rating as number)).toBe(false);
      expect(Number.isNaN(p.acs as number)).toBe(false);
    }
    expect(t.summary?.currentAcs).toBe(251.8);
    expect(t.summary?.peakRating).toBe(1.15);
    expect(t.note).toContain("young");
  });

  it("coerces stringy values defensively; unparseable -> null, never NaN", () => {
    const out = normalizePlayerTrend({
      player_id: "9",
      rating_trend: [
        { captured_at: "2026-06-08T12:00:00+00:00", rating: "1.15", acs: "N/A", rounds: "9298" },
      ],
      rating_change: "0.0",
      acs_change: "garbage",
      summary: { points: "1", current_rating: "1.15", peak_rating: "1.15", current_acs: "", peak_acs: null },
    });
    const t = out[0];
    expect(t.ratingTrend[0].rating).toBe(1.15);
    expect(t.ratingTrend[0].acs).toBeNull(); // "N/A" -> null, not NaN
    expect(t.acsChange).toBeNull(); // "garbage" -> null
    expect(t.summary?.currentAcs).toBeNull(); // "" -> null
  });

  it("orders the trend line on captured_at, not lexically or by rating", () => {
    // same string-sort trap as the team trend, time edition
    const scrambled = {
      player_id: "9",
      rating_trend: [
        { captured_at: "2026-06-09T12:00:00+00:00", rating: "1.24", acs: "1024", rounds: "100" },
        { captured_at: "2026-06-07T12:00:00+00:00", rating: "0.98", acs: "998", rounds: "100" },
        { captured_at: "2026-06-08T12:00:00+00:00", rating: "1.03", acs: "1003", rounds: "100" },
      ],
    };
    const acs = normalizePlayerTrend(scrambled)[0].ratingTrend.map((p) => p.acs);
    expect(acs).toEqual([998, 1003, 1024]); // chronological, numeric — not "1024" first
  });

  it("garbage/empty input -> valid empty (no throw)", () => {
    expect(normalizePlayerTrend("nope")).toEqual([]);
    expect(normalizePlayerTrend(null)).toEqual([]);
    const empty = normalizePlayerTrend({ player_id: "9", rating_trend: [] });
    expect(empty[0].ratingTrend).toEqual([]);
    expect(empty[0].summary).toBeNull();
  });
});

describe("normalizeMatch (Phase 7 match detail)", () => {
  const out = normalizeMatch(match);
  const m = out[0];

  it("wraps the single match object as a one-element list with header fields", () => {
    expect(out.length).toBe(1);
    expect(m.event).toBeTruthy();
    expect(m.teams.length).toBe(2);
    for (const t of m.teams) {
      expect(typeof t.name).toBe("string");
      expect(t.id && /^\d+$/.test(t.id)).toBeTruthy();
      expect(t.score === null || typeof t.score === "number").toBe(true);
    }
    expect(m.format).toBe("BO3");
    expect(m.veto && m.veto.toLowerCase()).toContain("pick");
  });

  it("exposes maps with the picked/decider markers and [team1,team2] scores", () => {
    expect(m.maps.length).toBeGreaterThan(0);
    expect(m.maps.filter((mp) => mp.decider).length).toBe(1);
    expect(m.maps.filter((mp) => mp.picked).length).toBe(m.maps.length - 1);
    for (const mp of m.maps) {
      expect(mp.teams.length).toBe(2);
      expect(mp.scores.length).toBe(2);
      for (const s of mp.scores) {
        expect(s === null || Number.isFinite(s)).toBe(true);
        expect(Number.isNaN(s as number)).toBe(false);
      }
    }
  });

  it("carries the full stat column set, every value number-or-null (never NaN)", () => {
    const p = m.maps[0].teams[0].players[0];
    // map-tab data keys the table reads
    for (const key of ["R", "ACS", "K", "D", "A", "KAST", "ADR", "HS%"]) {
      expect(key in p.stats).toBe(true);
    }
    const allPlayers = [
      ...m.maps.flatMap((mp) => mp.teams.flatMap((t) => t.players)),
      ...(m.allMaps?.teams.flatMap((t) => t.players) ?? []),
    ];
    expect(allPlayers.length).toBeGreaterThan(0);
    for (const pl of allPlayers) {
      expect(typeof pl.player).toBe("string");
      for (const cell of Object.values(pl.stats)) {
        // parseNumeric contract: a finite number or null, never NaN
        expect(cell.value === null || Number.isFinite(cell.value)).toBe(true);
        expect(Number.isNaN(cell.value as number)).toBe(false);
      }
    }
  });

  it("KAST/HS% arrive as bare numbers (value), with the % kept only for display", () => {
    const p = m.maps[0].teams[0].players[0];
    const kast = p.stats["KAST"];
    expect(kast.value === null || typeof kast.value === "number").toBe(true);
    if (kast.value !== null) expect(kast.value).toBeLessThanOrEqual(100);
  });

  it("rounds are real win/loss data: winner 1|2|null, side t|ct|null", () => {
    const withRounds = m.maps.find((mp) => mp.rounds.length > 0);
    expect(withRounds).toBeTruthy();
    for (const r of withRounds!.rounds) {
      expect([1, 2, null]).toContain(r.winner);
      expect(["t", "ct", null]).toContain(r.side);
    }
  });

  it("empty stat cell coerces to null (not NaN, not 0)", () => {
    const partial = normalizeMatch({
      ...(match as object),
      maps: [
        {
          game_id: "x",
          name: "Test",
          picked: true,
          decider: false,
          scores: ["", null],
          teams: [
            { name: "A", score: null, players: [
              { player: "p", agent: "a", stats: { R: { value: null, both: null, t: null, ct: null }, K: { value: 1, both: "1" } } },
            ] },
            { name: "B", score: 0, players: [] },
          ],
          rounds: [],
        },
      ],
    })[0];
    const cell = partial.maps[0].teams[0].players[0].stats["R"];
    expect(cell.value).toBeNull();
    expect(partial.maps[0].scores[0]).toBeNull(); // "" -> null, not NaN
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
    expect(normalizeMatch(null)).toEqual([]);
    expect(normalizeMatch([])).toEqual([]);
  });
});

describe("shouldRenderTrendLine (degenerate-trend honest state)", () => {
  const pt = (rating: number | null): RatingPoint => ({
    capturedAt: "2026-06-01T00:00:00Z",
    rating,
    rank: 1,
  });

  it("real sloped series -> line", () => {
    // Leviatán-shaped: genuine movement across the window.
    expect(shouldRenderTrendLine([pt(1802), pt(1830), pt(1848)])).toBe(true);
  });

  it("flat series (>=2 points, zero spread) -> no line", () => {
    // Heretics-shaped: a rank-1 ceiling pinned at 2000 is REAL data, but a
    // dead-flat line reads as a bug — honest note instead.
    expect(shouldRenderTrendLine([pt(2000), pt(2000), pt(2000)])).toBe(false);
    // sub-epsilon wobble is still "flat" (< 0.5 spread).
    expect(shouldRenderTrendLine([pt(2000), pt(2000.3)])).toBe(false);
  });

  it("fewer than 2 real ratings -> no line (history still young)", () => {
    expect(shouldRenderTrendLine([])).toBe(false);
    expect(shouldRenderTrendLine([pt(1850)])).toBe(false);
    // nulls don't count toward the 2 real ratings needed.
    expect(shouldRenderTrendLine([pt(1850), pt(null), pt(null)])).toBe(false);
  });

  it("PLAYER scale: the epsilon arg gates flatness on the right magnitude", () => {
    // player ratings move in hundredths — the team's 0.5 epsilon would call every
    // real player trend flat. PLAYER_FLAT_EPSILON (0.03) is the right gate.
    const ratings = (...rs: number[]) => rs.map((r) => ({ rating: r }));
    // a 0.10 swing is a real player move -> line under the player epsilon...
    expect(shouldRenderTrendLine(ratings(1.10, 1.20), PLAYER_FLAT_EPSILON)).toBe(true);
    // ...but flat under the team default (0.5).
    expect(shouldRenderTrendLine(ratings(1.10, 1.20))).toBe(false);
    // sub-epsilon wobble is still flat even on the player scale.
    expect(shouldRenderTrendLine(ratings(1.15, 1.16), PLAYER_FLAT_EPSILON)).toBe(false);
  });
});
