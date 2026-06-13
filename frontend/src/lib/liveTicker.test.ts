// Live-ticker derivation tests. buildLiveTicker is a PURE function over the
// normalized Phase 7 match detail, so we assert the curation CONTRACT against the
// two banked live fixtures:
//   - partial (Dragon Ranger vs Xi Lai, Haven 1–0): ACS not yet computed →
//     performer FALLS BACK to K–D–A; streak/momentum below threshold (1 round).
//   - filled (Global Esports vs FULL SENSE, current map Breeze 6–5): all-maps ACS
//     present → ACS performer; a real streak + momentum off the round timeline.
// No network is touched.

import { describe, expect, it } from "vitest";

import { normalizeMatch } from "@/lib/vlr";
import {
  buildLiveTicker,
  pickLiveMatchId,
  seededOrder,
} from "@/lib/liveTicker";
import type { TickerItem } from "@/types/vlr";

import partialFixture from "@/lib/__fixtures__/match_live_partial.json";
import filledFixture from "@/lib/__fixtures__/match_live_filled.json";

const partial = normalizeMatch(partialFixture)[0];
const filled = normalizeMatch(filledFixture)[0];

function byId(items: TickerItem[]): Record<string, TickerItem> {
  return Object.fromEntries(items.map((i) => [i.id, i]));
}

const DASH = "–"; // en-dash used by the formatters

// ---------- filled fixture: the rich live state ----------
describe("buildLiveTicker — filled fixture (Breeze 6–5, ACS computed)", () => {
  const items = buildLiveTicker(filled);
  const m = byId(items);

  it("LIVE score = current map score + round, not a finished earlier map", () => {
    // Split (9–13) is DONE; the live map is Breeze (6–5) — the last with rounds.
    expect(m["live:score"]).toBeTruthy();
    expect(m["live:score"].value).toBe(`6${DASH}5`);
    expect(m["live:score"].detail).toContain("Breeze");
    expect(m["live:score"].tone).toBe("down"); // LIVE red
  });

  it("top performer uses live ACS when present (primmie, 335)", () => {
    expect(m["live:performer"].label).toBe("TOP ACS");
    expect(m["live:performer"].primary).toBe("primmie");
    expect(m["live:performer"].value).toBe("335");
  });

  it("streak = consecutive rounds won, off the round timeline", () => {
    // trailing winners …,1,1 → team1 (Global Esports) on a 2-round streak
    expect(m["live:streak"].primary).toBe("Global Esports");
    expect(m["live:streak"].value).toBe("2");
  });

  it("momentum = won X of last Y rounds", () => {
    // last 5 winners [1,2,2,1,1] → team1 won 3 of 5
    expect(m["live:momentum"].primary).toBe("Global Esports");
    expect(m["live:momentum"].value).toBe("3/5");
  });

  it("first-blood leader = max FK across both teams (primmie, 9)", () => {
    expect(m["live:fk"].primary).toBe("primmie");
    expect(m["live:fk"].value).toBe("9");
  });

  it("veto recap carries the decider map + the veto strip", () => {
    expect(m["live:veto"].value).toBe("Pearl"); // the decider
    expect(m["live:veto"].detail).toContain("ban");
  });

  it("emits exactly the six derivable live stats", () => {
    expect(new Set(items.map((i) => i.id))).toEqual(
      new Set([
        "live:score",
        "live:performer",
        "live:streak",
        "live:momentum",
        "live:fk",
        "live:veto",
      ]),
    );
  });
});

// ---------- partial fixture: early-live (ACS null → fallback) ----------
describe("buildLiveTicker — partial fixture (Haven 1–0, ACS not yet computed)", () => {
  const items = buildLiveTicker(partial);
  const m = byId(items);

  it("top performer FALLS BACK to K–D–A when ACS is null early-live", () => {
    expect(m["live:performer"].label).toBe("TOP FRAGGER");
    // WsLeo leads on kills (2–1–0) before ACS exists
    expect(m["live:performer"].primary).toBe("WsLeo");
    expect(m["live:performer"].value).toBe(`2${DASH}1${DASH}0`);
  });

  it("LIVE score reflects the freshly-started map", () => {
    expect(m["live:score"].value).toBe(`1${DASH}0`);
    expect(m["live:score"].detail).toContain("Haven");
  });

  it("first-blood leader still surfaces (Flex1n, 1)", () => {
    expect(m["live:fk"].primary).toBe("Flex1n");
    expect(m["live:fk"].value).toBe("1");
  });

  it("streak + momentum are gated OUT with only one round played", () => {
    expect(m["live:streak"]).toBeUndefined();
    expect(m["live:momentum"]).toBeUndefined();
  });

  it("every value is a string — dash never NaN", () => {
    for (const i of items) {
      expect(typeof i.value).toBe("string");
      expect(i.value).not.toContain("NaN");
    }
  });
});

// ---------- seeded order: stable per (id, seed), survives polls ----------
describe("seededOrder — deterministic, poll-stable (hydration-safe contract)", () => {
  const items = buildLiveTicker(filled);

  it("is reproducible for a given seed (same order → SSR == client)", () => {
    expect(seededOrder(items, 42)).toEqual(seededOrder(items, 42));
  });

  it("is a permutation (same item set, input untouched)", () => {
    const before = items.map((i) => i.id);
    const out = seededOrder(items, 7);
    expect(new Set(out.map((i) => i.id))).toEqual(new Set(before));
    expect(items.map((i) => i.id)).toEqual(before); // not mutated
  });

  it("order is fixed by id, not by value — so a poll's fresh values don't reshuffle", () => {
    // same ids, mutated values (a later poll) → identical ORDER under the same seed
    const next = items.map((i) => ({ ...i, value: "999", detail: "changed" }));
    expect(seededOrder(next, 7).map((i) => i.id)).toEqual(
      seededOrder(items, 7).map((i) => i.id),
    );
  });
});

// ---------- live-match pick (drives the live↔static switch) ----------
describe("pickLiveMatchId — the live↔static decision", () => {
  it("no live matches → null (→ static curated tape)", () => {
    expect(pickLiveMatchId([])).toBeNull();
  });

  it("picks the first live match with an id (→ live mode)", () => {
    expect(pickLiveMatchId([{ id: null }, { id: "684619" }])).toBe("684619");
  });
});
