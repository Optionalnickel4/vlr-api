// @vitest-environment happy-dom
//
// Reproduce the reported hydration mismatch on the match-detail page: SSR-render
// the MapTabs client island, mount that HTML into a container, then hydrateRoot
// the SAME element and assert React reports no hydration warning. Covers both a
// completed match (the committed fixture) and a synthetic LIVE match (empty
// R/ACS/ADR cells + unplayed rounds — the FUT-vs-NRG state the report hit).

import { afterEach, describe, expect, it, vi } from "vitest";
import { createElement as h } from "react";
import { renderToString } from "react-dom/server";
import { hydrateRoot } from "react-dom/client";

import { MapTabs } from "@/components/MapTabs";
import { normalizeMatch } from "@/lib/vlr";
import type { MatchDetail } from "@/types/vlr";
import matchFixture from "@/lib/__fixtures__/match.json";

afterEach(() => vi.restoreAllMocks());

/** SSR → hydrate the element; return any hydration-related console.error /
 *  recoverable-error messages React emits. */
async function hydrationErrors(element: ReturnType<typeof h>): Promise<string[]> {
  const html = renderToString(element);
  const container = document.createElement("div");
  container.innerHTML = html;

  const seen: string[] = [];
  const spy = vi.spyOn(console, "error").mockImplementation((...args) => {
    seen.push(args.map(String).join(" "));
  });
  const root = hydrateRoot(container, element, {
    onRecoverableError: (e) => seen.push(String(e)),
  });
  // let hydration + effects settle
  await new Promise((r) => setTimeout(r, 0));
  root.unmount();
  spy.mockRestore();

  return seen.filter((m) =>
    /hydrat|did not match|didn't match|server rendered|server-rendered|attributes/i.test(m),
  );
}

describe("match-detail hydration (MapTabs island)", () => {
  it("completed match (real fixture) hydrates with no warnings", async () => {
    const match = normalizeMatch(matchFixture)[0];
    expect(await hydrationErrors(h(MapTabs, { match }))).toEqual([]);
  });

  it("LIVE match (empty cells + unplayed rounds) hydrates with no warnings", async () => {
    const empty = { value: null, both: null, t: null, ct: null };
    const player = (name: string) => ({
      player: name,
      team: "FUT",
      playerId: null,
      country: "tr",
      agent: "jett",
      stats: {
        R: empty, // not yet computed -> dash
        ACS: empty,
        K: { value: 8, both: "8", t: "5", ct: "3" },
        D: { value: 7, both: "7", t: null, ct: null },
        A: { value: 2, both: "2", t: null, ct: null },
        KAST: { value: 69, both: "69%", t: "67%", ct: "100%" },
        ADR: empty,
        "HS%": { value: 21, both: "21%", t: null, ct: null },
        FK: { value: 1, both: "1", t: null, ct: null },
        FD: { value: 0, both: "0", t: null, ct: null },
      },
    });
    const live: MatchDetail = {
      id: "684619",
      event: "Valorant Masters London 2026",
      series: "Swiss Stage: Round 1",
      status: "live",
      format: "BO3",
      url: "https://www.vlr.gg/684619",
      veto: "FUT ban Bind; NRG ban Pearl; FUT pick Lotus; NRG pick Haven; decider Fracture",
      teams: [
        { name: "FUT Esports", id: "1184", score: 0, won: false },
        { name: "NRG", id: "1034", score: 0, won: false },
      ],
      maps: [
        {
          gameId: "1",
          name: "Lotus",
          picked: true,
          decider: false,
          scores: [7, 6],
          teams: [
            { name: "FUT Esports", score: 7, players: [player("aspas"), player("MrFaliN")] },
            { name: "NRG", score: 6, players: [player("Ethan"), player("Verno")] },
          ],
          // mid-map: first rounds played, the rest unplayed (winner null)
          rounds: Array.from({ length: 24 }, (_, i) => ({
            round: i + 1,
            winner: i < 13 ? (((i % 2) + 1) as 1 | 2) : null,
            side: i < 13 ? ("t" as const) : null,
            outcome: i < 13 ? "elim" : null,
            score: i < 13 ? `${i}-0` : null,
          })),
        },
        {
          gameId: "2",
          name: "Fracture",
          picked: false,
          decider: true,
          scores: [0, 0],
          teams: [
            { name: "FUT Esports", score: 0, players: [player("aspas")] },
            { name: "NRG", score: 0, players: [player("Ethan")] },
          ],
          rounds: [], // not started -> RoundTimeline omits gracefully
        },
      ],
      allMaps: {
        teams: [
          { name: "FUT Esports", score: null, players: [player("aspas")] },
          { name: "NRG", score: null, players: [player("Ethan")] },
        ],
      },
      streams: [],
    };
    expect(await hydrationErrors(h(MapTabs, { match: live }))).toEqual([]);
  });
});
