// Stat-ticker curation tests. buildTicker is a PURE aggregate over already-
// normalized domain inputs — so we assert the curation CONTRACT (notability
// gates, fixed order, one-item-per-team, dash-not-NaN, stable ids, empty-state)
// rather than volatile values that drift as the season moves. Real fixtures
// (match/results/rankings/trends) exercise the happy path; small synthetic
// inputs exercise the gates precisely. No network is touched in buildTicker;
// getTicker's graceful-empty is verified with a mocked fetch.

import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ACS_NOTABLE,
  RANK_MOVE_NOTABLE,
  TICKER_MAX,
  TREND_RATING_NOTABLE,
  buildTicker,
  getTicker,
  normalizeMatch,
  normalizeRankings,
  normalizeResult,
} from "@/lib/vlr";

import type {
  MatchDetail,
  RankedTeam,
  ResultMatch,
  TeamTrend,
  TickerSources,
} from "@/types/vlr";

import match from "@/lib/__fixtures__/match.json";
import results from "@/lib/__fixtures__/results.json";
import rankings from "@/lib/__fixtures__/rankings.json";

// ---- tiny synthetic builders (only the fields buildTicker reads) ------------

const EMPTY: TickerSources = { results: [], rankings: [], matches: [], trends: [] };

function mkResult(p: Partial<ResultMatch>): ResultMatch {
  return {
    id: "r1",
    team1: null,
    team2: null,
    score1: null,
    score2: null,
    time: null,
    series: null,
    event: null,
    url: null,
    ...p,
  };
}

function mkRanked(team: string, rank: number): RankedTeam {
  return { id: `${rank}`, rank, team, country: null, rating: null };
}

/** A match whose all-maps scoreboard carries one player per given ACS. */
function mkMatch(
  id: string,
  perfs: { player: string; team: string; acs: number | null }[],
): MatchDetail {
  return {
    id,
    event: "Test Event",
    series: null,
    status: "final",
    format: "BO3",
    url: null,
    veto: null,
    teams: [
      { name: "Alpha", id: "1", score: 2, won: true },
      { name: "Bravo", id: "2", score: 1, won: false },
    ],
    maps: [],
    streams: [],
    allMaps: {
      teams: [
        {
          name: null,
          score: null,
          players: perfs.map((pf) => ({
            player: pf.player,
            team: pf.team,
            playerId: null,
            country: null,
            agent: null,
            stats: { ACS: { value: pf.acs, both: null, t: null, ct: null } },
          })),
        },
      ],
    },
  };
}

function mkTrend(p: Partial<TeamTrend> & { team: string }): TeamTrend {
  return {
    teamId: p.teamId ?? "t1",
    team: p.team,
    windowDays: p.windowDays ?? 90,
    ratingTrend: p.ratingTrend ?? [],
    ratingChange: p.ratingChange ?? null,
    resultsInWindow: [],
    summary: p.summary ?? null,
  };
}

const ranksOf = (ranks: (number | null)[]) =>
  ranks.map((rank, i) => ({
    capturedAt: `2026-06-0${i + 1}T00:00:00Z`,
    rating: null,
    rank,
  }));

// ---- real-fixture happy path ------------------------------------------------

describe("buildTicker over real fixtures (invariants, not values)", () => {
  const out = buildTicker({
    results: normalizeResult(results),
    rankings: normalizeRankings(rankings),
    matches: normalizeMatch(match),
    trends: [],
  });

  it("emits render-ready items: every field a string, value never NaN", () => {
    expect(Array.isArray(out)).toBe(true);
    for (const item of out) {
      for (const v of [item.id, item.label, item.primary, item.detail, item.value]) {
        expect(typeof v).toBe("string");
      }
      expect(item.value).not.toContain("NaN");
      expect(["acs", "upset", "mover", "trend"]).toContain(item.kind);
      expect(["up", "down", "warn", "accent", "neutral"]).toContain(item.tone);
    }
  });

  it("surfaces the headline ACS performance from the match fixture", () => {
    const acs = out.filter((i) => i.kind === "acs");
    expect(acs.length).toBe(1); // one top performer per sampled match
    // every emitted ACS item clears the gate (curation, not raw dump)
    for (const i of acs) expect(Number(i.value)).toBeGreaterThanOrEqual(ACS_NOTABLE);
    expect(acs[0].tone).toBe("accent");
  });

  it("caps the tape and keeps ids unique", () => {
    expect(out.length).toBeLessThanOrEqual(TICKER_MAX);
    expect(new Set(out.map((i) => i.id)).size).toBe(out.length);
  });
});

// ---- ACS gate ---------------------------------------------------------------

describe("top-ACS curation", () => {
  it("picks the single highest performer and prints the rounded value", () => {
    const m = mkMatch("m1", [
      { player: "Sato", team: "LEV", acs: 244 },
      { player: "UdoTan", team: "GE", acs: 252.6 },
    ]);
    const out = buildTicker({ ...EMPTY, matches: [m] });
    expect(out.length).toBe(1);
    expect(out[0].kind).toBe("acs");
    expect(out[0].primary).toBe("UdoTan");
    expect(out[0].value).toBe("253"); // rounded, not "252.6", never NaN
  });

  it("drops a match whose best ACS is below the notability gate (filler)", () => {
    const m = mkMatch("m2", [{ player: "Mid", team: "X", acs: ACS_NOTABLE - 1 }]);
    expect(buildTicker({ ...EMPTY, matches: [m] })).toEqual([]);
  });

  it("a match with no numeric ACS is skipped, not rendered NaN", () => {
    const m = mkMatch("m3", [{ player: "NoData", team: "X", acs: null }]);
    expect(buildTicker({ ...EMPTY, matches: [m] })).toEqual([]);
  });
});

// ---- upset gate -------------------------------------------------------------

describe("upset curation (winner ranked well below loser)", () => {
  const rankingsSrc = [mkRanked("Heretics", 1), mkRanked("Underdog", 9)];

  it("flags a big-gap upset and orders it ahead of ACS items", () => {
    const acsMatch = mkMatch("am", [{ player: "Star", team: "X", acs: 300 }]);
    const out = buildTicker({
      ...EMPTY,
      rankings: rankingsSrc,
      matches: [acsMatch],
      results: [
        mkResult({
          id: "u1",
          team1: "Underdog",
          team2: "Heretics",
          score1: 2,
          score2: 1,
          event: "Masters",
        }),
      ],
    });
    expect(out[0].kind).toBe("upset"); // fixed priority: upsets first
    expect(out[0].primary).toBe("Underdog");
    expect(out[0].value).toBe("2–1");
    expect(out[0].detail).toContain("Heretics");
    expect(out.some((i) => i.kind === "acs")).toBe(true);
  });

  it("does NOT flag the favorite winning, nor an unranked matchup", () => {
    const favorite = buildTicker({
      ...EMPTY,
      rankings: rankingsSrc,
      results: [
        mkResult({ team1: "Heretics", team2: "Underdog", score1: 2, score2: 0 }),
      ],
    });
    const unranked = buildTicker({
      ...EMPTY,
      rankings: rankingsSrc,
      results: [
        mkResult({ team1: "Nobody", team2: "AlsoNobody", score1: 2, score2: 1 }),
      ],
    });
    expect(favorite).toEqual([]);
    expect(unranked).toEqual([]);
  });

  it("every emitted upset has the winner ranked numerically worse than the loser", () => {
    const out = buildTicker({
      ...EMPTY,
      rankings: rankingsSrc,
      results: [
        mkResult({ team1: "Underdog", team2: "Heretics", score1: 2, score2: 1 }),
      ],
    });
    for (const i of out.filter((x) => x.kind === "upset")) {
      // detail encodes "#<winner> over #<loser>"; the winner number must be larger
      const m = i.detail.match(/#(\d+) over #(\d+)/);
      expect(m).toBeTruthy();
      expect(Number(m![1])).toBeGreaterThan(Number(m![2]));
    }
  });
});

// ---- mover / trend gate (one item per team) ---------------------------------

describe("mover/trend curation", () => {
  it("a real rank climb becomes a MOVER (▲, up)", () => {
    const out = buildTicker({
      ...EMPTY,
      trends: [mkTrend({ team: "Risers", ratingTrend: ranksOf([7, 6, 4]) })],
    });
    expect(out.length).toBe(1);
    expect(out[0].kind).toBe("mover");
    expect(out[0].tone).toBe("up");
    expect(out[0].value).toBe("▲3");
    expect(out[0].detail).toContain("#7 → #4");
  });

  it("a rank drop is a down MOVER (▼)", () => {
    const out = buildTicker({
      ...EMPTY,
      trends: [mkTrend({ team: "Fallers", ratingTrend: ranksOf([3, 5, 6]) })],
    });
    expect(out[0].value).toBe("▼3");
    expect(out[0].tone).toBe("down");
  });

  it("flat rank + a notable rating swing becomes a TREND (signed)", () => {
    const out = buildTicker({
      ...EMPTY,
      trends: [
        mkTrend({
          team: "Steady",
          ratingTrend: ranksOf([5, 5, 5]),
          ratingChange: TREND_RATING_NOTABLE + 9,
          summary: { points: 0, wins: 0, losses: 0, currentRating: 1700, peakRating: 1700 },
        }),
      ],
    });
    expect(out[0].kind).toBe("trend");
    expect(out[0].value).toBe(`+${TREND_RATING_NOTABLE + 9}`);
    expect(out[0].tone).toBe("up");
  });

  it("emits at most ONE item per team (rank move preferred over rating swing)", () => {
    const out = buildTicker({
      ...EMPTY,
      trends: [
        mkTrend({
          team: "Both",
          teamId: "99",
          ratingTrend: ranksOf([8, 5, 3]), // a clear mover
          ratingChange: 40, // also a big swing — must NOT double-count
        }),
      ],
    });
    expect(out.length).toBe(1);
    expect(out[0].kind).toBe("mover");
  });

  it("below either gate → nothing (sub-threshold wobble is filler)", () => {
    const out = buildTicker({
      ...EMPTY,
      trends: [
        mkTrend({
          team: "Quiet",
          ratingTrend: ranksOf([5, 5, 5 - (RANK_MOVE_NOTABLE - 1)]),
          ratingChange: TREND_RATING_NOTABLE - 1,
        }),
      ],
    });
    expect(out).toEqual([]);
  });

  it("missing ranks/ratings don't crash or render NaN", () => {
    const out = buildTicker({
      ...EMPTY,
      trends: [mkTrend({ team: "Sparse", ratingTrend: ranksOf([null, null]), ratingChange: null })],
    });
    expect(out).toEqual([]);
  });
});

// ---- empty state + ordering -------------------------------------------------

describe("empty state and fixed ordering", () => {
  it("no notable stats → empty tape (ticker hides, never errors)", () => {
    expect(buildTicker(EMPTY)).toEqual([]);
  });

  it("order is upsets → ACS → movers/trends", () => {
    const out = buildTicker({
      results: [
        mkResult({ team1: "Low", team2: "High", score1: 2, score2: 0 }),
      ],
      rankings: [mkRanked("High", 1), mkRanked("Low", 8)],
      matches: [mkMatch("am", [{ player: "Star", team: "X", acs: 300 }])],
      trends: [mkTrend({ team: "Risers", ratingTrend: ranksOf([7, 4]) })],
    });
    expect(out.map((i) => i.kind)).toEqual(["upset", "acs", "mover"]);
  });
});

// ---- getTicker orchestration: graceful-empty --------------------------------

describe("getTicker (graceful-empty, never throws to the page)", () => {
  afterEach(() => vi.restoreAllMocks());

  it("returns { data: [], stale: true, error } when upstream is down", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("ECONNREFUSED"));
    const res = await getTicker();
    expect(res.data).toEqual([]);
    expect(res.stale).toBe(true);
  });
});
