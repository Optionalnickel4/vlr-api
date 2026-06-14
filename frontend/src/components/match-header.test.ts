// @vitest-environment node
//
// MatchHeader scorebug — the live-in-progress fix. During a LIVE match whose
// series is still 0:0 (a map is being played but not yet awarded), the big
// scorebug must show the live MAP score (e.g. 9–3) with a "MAP n" caption, NOT
// the misleading 0:0 series score. Once a map is won (series 1:0+) or the match
// is final, the series score is what shows.

import { describe, expect, it } from "vitest";
import { createElement as h } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { MatchHeader } from "@/components/MatchHeader";
import type { MatchDetail } from "@/types/vlr";

function mk(
  status: string | null,
  seriesScores: [number, number],
  maps: { name: string; scores: [number, number] }[],
  won: [boolean, boolean] = [false, false],
): MatchDetail {
  return {
    id: "670473",
    event: "Masters",
    series: null,
    status,
    format: "BO3",
    url: null,
    veto: null,
    teams: [
      { name: "LEVIATÁN", id: "2359", score: seriesScores[0], won: won[0] },
      { name: "Team Heretics", id: "1001", score: seriesScores[1], won: won[1] },
    ],
    maps: maps.map((m) => ({
      gameId: null,
      name: m.name,
      picked: false,
      decider: false,
      scores: m.scores,
      teams: [],
      rounds: [],
    })),
    allMaps: null,
    streams: [],
  };
}

describe("MatchHeader scorebug", () => {
  it("live + series 0:0 + map at 9-3 → shows the live map score + caption, not 0:0", () => {
    const html = renderToStaticMarkup(
      h(MatchHeader, { match: mk("live", [0, 0], [{ name: "Split", scores: [9, 3] }]) }),
    );
    expect(html).toContain('aria-label="Score 9 to 3"'); // the live MAP score
    expect(html).not.toContain('aria-label="Score 0 to 0"'); // never the 0:0 series
    expect(html).toContain("Map 1"); // captioned as the current map
    expect(html).toContain("Split");
  });

  it("live + series 1:0 (a map won) → shows the series score, no map caption", () => {
    const html = renderToStaticMarkup(
      h(MatchHeader, {
        match: mk("live", [1, 0], [
          { name: "Split", scores: [13, 9] },
          { name: "Lotus", scores: [9, 3] },
        ]),
      }),
    );
    expect(html).toContain('aria-label="Score 1 to 0"'); // series score stays
    expect(html).not.toContain("Map 1 ·");
    expect(html).not.toContain("Map 2 ·");
  });

  it("final match → series score, winner shown", () => {
    const html = renderToStaticMarkup(
      h(MatchHeader, {
        match: mk("final", [2, 1], [{ name: "Split", scores: [13, 9] }], [true, false]),
      }),
    );
    expect(html).toContain('aria-label="Score 2 to 1"');
    expect(html).not.toContain("Map 1 ·");
  });
});
